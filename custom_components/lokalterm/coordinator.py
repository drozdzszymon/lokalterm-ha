from __future__ import annotations

import asyncio
import json
import logging
import secrets
import string
import time
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from typing import Any

from homeassistant.core import HomeAssistant

from .const import (
    INTER_FIELD_DELAY_SECONDS,
    MAX_LINE_BYTES,
    PENDING_TIMEOUT_SECONDS,
    SEND_DEBOUNCE_SECONDS,
)
from .entity import values_match

_LOGGER = logging.getLogger(__name__)

_MASK_KEYS: frozenset[str] = frozenset({"vId", "vPin"})


def _mask_sensitive(d: dict[str, Any]) -> dict[str, Any]:
    """Kopia słownika do logów maskująca pola wrażliwe."""
    out = dict(d)
    for k in _MASK_KEYS:
        if k in out:
            out[k] = "***"
    return out


def _rand_token(n: int = 7) -> str:
    return "".join(secrets.choice(string.ascii_uppercase) for _ in range(n))


def _decode_json_line(line: bytes) -> dict[str, Any] | None:
    """Dekoduje linię JSON odpornie na zakłócenia UART/RS-485 (np. wiodące 0xFF/0x00)."""
    text = line.decode("ascii", "ignore").strip(" \t\r\n\x00")
    if not text:
        return None
    try:
        obj = json.loads(text)
    except ValueError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end <= start:
            return None
        try:
            obj = json.loads(text[start : end + 1])
        except ValueError:
            return None
    return obj if isinstance(obj, dict) else None


@dataclass(frozen=True)
class EltermLocalCfg:
    listen_host: str
    listen_port: int
    devid: str
    devpin: str


class EltermLocalServer:
    def __init__(
        self,
        hass: HomeAssistant,
        cfg: EltermLocalCfg,
        on_status: Callable[..., None],
        get_current_state: Callable[[], dict[str, Any] | None] | None = None,
    ) -> None:
        self.hass = hass
        self.cfg = cfg
        self.on_status = on_status
        self._get_current_state = get_current_state
        self._server: asyncio.Server | None = None
        self._client_writer: asyncio.StreamWriter | None = None
        self._active_writers: set[asyncio.StreamWriter] = set()

        self._last_obj: dict[str, Any] = {}
        # field -> (wire_value, token, sent_at_monotonic)
        self._pending: dict[str, tuple[str, str, float]] = {}
        self._lock = asyncio.Lock()
        self._send_task: asyncio.Task[None] | None = None
        self._send_sleeping: bool = False
        self._resend_requested: bool = False
        self._stopping: bool = False

    def _emit_status(self, obj: dict[str, Any], *, immediate: bool = False) -> None:
        try:
            self.on_status(obj, immediate=immediate)
        except TypeError:
            self.on_status(obj)

    async def start(self) -> None:
        self._stopping = False
        self._server = await asyncio.start_server(
            self._handle_connection,
            self.cfg.listen_host,
            self.cfg.listen_port,
            limit=MAX_LINE_BYTES,
        )
        _LOGGER.info(
            "LokalTerm: serwer nasłuchuje na %s:%d",
            self.cfg.listen_host,
            self.cfg.listen_port,
        )

    async def stop(self) -> None:
        self._stopping = True

        if self._send_task and not self._send_task.done():
            self._send_task.cancel()
            try:
                await self._send_task
            except asyncio.CancelledError:
                pass
        self._send_task = None

        if self._server is not None:
            self._server.close()

        writers = list(self._active_writers)
        self._active_writers.clear()
        self._client_writer = None

        for writer in writers:
            with suppress(OSError, RuntimeError):
                writer.close()

        if writers:
            await asyncio.gather(
                *(w.wait_closed() for w in writers),
                return_exceptions=True,
            )

        if self._server is not None:
            await self._server.wait_closed()
            self._server = None

        _LOGGER.info("LokalTerm: serwer TCP zatrzymany")

    async def send_data_to_send(self, fields: dict[str, Any], **kwargs: Any) -> None:
        """Kolejkuje pola do wysłania, aktualizuje Optimistic UI i planuje minimalną wysyłkę."""
        if not fields or self._stopping:
            return

        normalized = {str(k): str(v) for k, v in fields.items()}
        optimistic: dict[str, Any] | None = None

        async with self._lock:
            now = time.monotonic()
            for k, v in normalized.items():
                token = _rand_token()
                self._pending[k] = (v, token, now)
                _LOGGER.info("LokalTerm: kliknięcie w UI [%s] -> {%s: %s}", token, k, v)

            base_state = self._last_obj or (
                self._get_current_state() if self._get_current_state is not None else None
            ) or kwargs.get("base_state")
            if isinstance(base_state, dict) and base_state:
                optimistic = dict(base_state)
                for pk, (pv, _, _) in self._pending.items():
                    optimistic[pk] = pv

            self._schedule_send_locked(SEND_DEBOUNCE_SECONDS)

        if optimistic is not None:
            self._emit_status(optimistic, immediate=True)

    def _schedule_send_locked(self, delay: float) -> None:
        if self._stopping:
            return
        if self._send_task is None or self._send_task.done():
            self._resend_requested = False
            self._send_task = self.hass.async_create_task(self._send_minimal_command(delay))
        elif self._send_sleeping:
            self._resend_requested = False
            self._send_task.cancel()
            self._send_task = self.hass.async_create_task(self._send_minimal_command(delay))
        else:
            self._resend_requested = True

    async def _close_writer_quietly(self, writer: asyncio.StreamWriter) -> None:
        with suppress(OSError, RuntimeError, asyncio.CancelledError):
            writer.close()
            await writer.wait_closed()

    async def _handle_connection(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        peer = writer.get_extra_info("peername")
        _LOGGER.info("LokalTerm: piec podłączony z %s", peer)
        self._active_writers.add(writer)

        if self._client_writer is None:
            self._client_writer = writer

        try:
            while not self._stopping:
                try:
                    line = await reader.readline()
                except (asyncio.LimitOverrunError, ValueError):
                    _LOGGER.warning("LokalTerm: odrzucono zbyt długą ramkę z %s", peer)
                    try:
                        await reader.read(MAX_LINE_BYTES)
                    except OSError:
                        break
                    continue
                except (OSError, asyncio.CancelledError):
                    break

                if not line:
                    break

                obj = _decode_json_line(line)
                if obj is None or obj.get("FrameType") != "SkzpData":
                    continue

                if _LOGGER.isEnabledFor(logging.DEBUG):
                    _LOGGER.debug(
                        "LokalTerm: odebrano status -> %s",
                        _mask_sensitive(obj),
                    )

                stale_writer: asyncio.StreamWriter | None = None
                if self._client_writer is not writer:
                    stale_writer = self._client_writer
                    self._client_writer = writer

                if stale_writer is not None:
                    self._active_writers.discard(stale_writer)
                    self.hass.async_create_task(self._close_writer_quietly(stale_writer))

                immediate_publish = False
                async with self._lock:
                    self._last_obj = obj
                    display_obj = dict(obj)

                    if self._pending:
                        now = time.monotonic()
                        for k, (expected_val, token, sent_at) in list(self._pending.items()):
                            if values_match(obj.get(k), expected_val):
                                _LOGGER.info(
                                    "LokalTerm: potwierdzone przez piec [%s] (%s=%s)",
                                    token,
                                    k,
                                    expected_val,
                                )
                                del self._pending[k]
                                immediate_publish = True
                            elif now - sent_at > PENDING_TIMEOUT_SECONDS:
                                _LOGGER.warning(
                                    "LokalTerm: timeout - piec nie przyjął zmiany (token=%s, %s=%s).",
                                    token,
                                    k,
                                    expected_val,
                                )
                                del self._pending[k]
                                immediate_publish = True
                            else:
                                display_obj[k] = expected_val

                        if self._pending:
                            self._schedule_send_locked(SEND_DEBOUNCE_SECONDS)

                self._emit_status(display_obj, immediate=immediate_publish)

        finally:
            self._active_writers.discard(writer)
            if self._client_writer is writer:
                self._client_writer = None
            await self._close_writer_quietly(writer)
            _LOGGER.info("LokalTerm: piec rozłączony (%s)", peer)

    async def _send_minimal_command(self, delay: float = SEND_DEBOUNCE_SECONDS) -> None:
        """Wysyła minimalne jednoparametrowe ramki DataToSend identyczne z protokołem SKZP."""
        current_delay = delay
        while not self._stopping:
            if current_delay > 0:
                self._send_sleeping = True
                try:
                    await asyncio.sleep(current_delay)
                finally:
                    self._send_sleeping = False

            async with self._lock:
                self._resend_requested = False
                if self._stopping or not self._pending or self._client_writer is None:
                    return
                items = list(self._pending.items())

            for idx, (field_key, _) in enumerate(items):
                if idx > 0:
                    await asyncio.sleep(INTER_FIELD_DELAY_SECONDS)

                async with self._lock:
                    if self._stopping or self._client_writer is None:
                        return
                    current = self._pending.get(field_key)
                    if current is None:
                        continue
                    field_val, token, _ = current
                    writer = self._client_writer

                    frame: dict[str, str] = {
                        "FrameType": "DataToSend",
                        "vId": str(self.cfg.devid),
                        "vPin": str(self.cfg.devpin),
                        field_key: str(field_val),
                        "vToken": str(token),
                    }

                    try:
                        payload = json.dumps(frame, separators=(",", ":"), ensure_ascii=True)
                        writer.write(payload.encode("ascii") + b"\r\n")
                        await writer.drain()

                        _LOGGER.info(
                            "LokalTerm: wysłano komendę do pieca [%s] (pola=[%r])",
                            token,
                            field_key,
                        )
                        if _LOGGER.isEnabledFor(logging.DEBUG):
                            _LOGGER.debug(
                                "LokalTerm: payload [%s] -> %s",
                                token,
                                _mask_sensitive(frame),
                            )
                    except (OSError, ConnectionError, RuntimeError) as err:
                        _LOGGER.error("LokalTerm: wysyłka nie powiodła się: %s", err)
                        if self._client_writer is writer:
                            self._client_writer = None
                        self._active_writers.discard(writer)
                        self.hass.async_create_task(self._close_writer_quietly(writer))
                        return

            async with self._lock:
                if not self._resend_requested or not self._pending or self._stopping:
                    return
                self._resend_requested = False
                current_delay = SEND_DEBOUNCE_SECONDS

