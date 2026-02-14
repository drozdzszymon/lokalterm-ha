from __future__ import annotations

import asyncio
import json
import logging
import random
import string
import time
from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)

_MASK_KEYS: set[str] = {"vId", "vPin"}


def _mask_sensitive(d: dict[str, Any]) -> dict[str, Any]:
    """Kopia słownika do logów – maskuje pola wrażliwe."""
    out = dict(d)
    for k in _MASK_KEYS:
        if k in out:
            out[k] = "***"
    return out


def _rand_token(n: int = 7) -> str:
    return "".join(random.choice(string.ascii_uppercase) for _ in range(n))


@dataclass
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
        on_status: Callable[[dict[str, Any]], None],
    ) -> None:
        self.hass = hass
        self.cfg = cfg
        self.on_status = on_status
        self._server: asyncio.Server | None = None
        self._client_writer: asyncio.StreamWriter | None = None

        self._last_obj: dict[str, Any] = {}
        self._pending_fields: dict[str, Any] | None = None
        self._pending_token: str | None = None
        self._lock = asyncio.Lock()
        self._last_send_time: float = 0

    async def start(self) -> None:
        self._server = await asyncio.start_server(
            self._handle_connection,
            self.cfg.listen_host,
            self.cfg.listen_port,
        )
        _LOGGER.info(
            "LokalTerm: serwer nasłuchuje na %s:%d",
            self.cfg.listen_host,
            self.cfg.listen_port,
        )

    async def stop(self) -> None:
        if self._server:
            self._server.close()
            await self._server.wait_closed()

    async def send_data_to_send(self, fields: dict[str, Any], **kwargs) -> None:
        """Wywoływane natychmiast po kliknięciu w UI Home Assistanta."""
        async with self._lock:
            self._pending_fields = fields
            self._pending_token = _rand_token()
            self._last_send_time = time.monotonic()

            _LOGGER.info("LokalTerm: kliknięcie w UI [%s] -> %s", self._pending_token, fields)

            # 1. NATYCHMIAST informujemy HA o nowej wartości (Optimistic UI)
            if self._last_obj:
                fake_obj = dict(self._last_obj)
                fake_obj.update(fields)
                self.on_status(fake_obj)

            # 2. NATYCHMIAST wysyłamy do pieca (nie czekamy na ramkę statusu)
            self.hass.async_create_task(self._send_minimal_command())

    async def _handle_connection(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        peer = writer.get_extra_info("peername")
        _LOGGER.info("LokalTerm: piec podłączony z %s", peer)
        self._client_writer = writer

        try:
            while True:
                line = await reader.readline()
                if not line:
                    break

                try:
                    obj = json.loads(line.decode("ascii", "ignore"))
                except Exception:
                    continue

                if obj.get("FrameType") == "SkzpData":
                    self._last_obj = obj
                    display_obj = dict(obj)

                    if self._pending_fields:
                        match = True
                        for k, v in self._pending_fields.items():
                            if str(obj.get(k)) != str(v):
                                match = False
                                display_obj[k] = v  # Nadpisujemy, by suwak stał w miejscu

                        if match:
                            _LOGGER.info("LokalTerm: potwierdzone przez piec [%s]", self._pending_token)
                            self._pending_fields = None
                            self._pending_token = None
                        else:
                            # Piec jeszcze nie zmienił – ponawiamy wysyłkę
                            self.hass.async_create_task(self._send_minimal_command())

                            if time.monotonic() - self._last_send_time > 20:
                                _LOGGER.warning(
                                    "LokalTerm: timeout – piec nie przyjął zmian (token=%s).",
                                    self._pending_token,
                                )
                                self._pending_fields = None

                    self.on_status(display_obj)

        finally:
            _LOGGER.info("LokalTerm: piec rozłączony")
            self._client_writer = None

    async def _send_minimal_command(self) -> None:
        """Sama wysyłka fizyczna."""
        # Bardzo krótka pauza, żeby nie zalać bufora pieca przy szybkich kliknięciach
        await asyncio.sleep(0.1)

        async with self._lock:
            if not self._pending_fields or not self._client_writer:
                return

            frame: dict[str, Any] = {
                "FrameType": "DataToSend",
                "vId": str(self.cfg.devid),
                "vPin": str(self.cfg.devpin),
            }
            for k, v in self._pending_fields.items():
                frame[k] = str(v)
            frame["vToken"] = str(self._pending_token)

            try:
                payload = json.dumps(frame, separators=(",", ":"))
                self._client_writer.write(payload.encode("ascii") + b"\r\n")
                await self._client_writer.drain()

                # INFO: nie logujemy sekretów ani pełnego payloadu
                _LOGGER.info(
                    "LokalTerm: wysłano komendę do pieca [%s] (pola=%s)",
                    self._pending_token,
                    list(self._pending_fields.keys()),
                )
                # DEBUG: szczegóły (zamaskowane)
                _LOGGER.debug("LokalTerm: payload [%s] -> %s", self._pending_token, _mask_sensitive(frame))

            except Exception as e:
                _LOGGER.error("LokalTerm: wysyłka nie powiodła się: %s", e)
