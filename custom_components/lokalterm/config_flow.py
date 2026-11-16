from __future__ import annotations

import asyncio
import ipaddress
import re
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import (
    CONF_DEVID,
    CONF_DEVPIN,
    CONF_LISTEN_HOST,
    CONF_LISTEN_PORT,
    DEFAULT_LISTEN_HOST,
    DEFAULT_LISTEN_PORT,
    DOMAIN,
)

_HOSTNAME_RE = re.compile(
    r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)*$"
)
_WILDCARD_HOSTS = frozenset({"0.0.0.0", "::", ""})


def _is_valid_host(host: str) -> bool:
    if not host or any(ch.isspace() for ch in host):
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return len(host) <= 253 and bool(_HOSTNAME_RE.match(host))


def _hosts_overlap(host_a: str, host_b: str) -> bool:
    norm_a = host_a.strip().lower()
    norm_b = host_b.strip().lower()
    if norm_a in _WILDCARD_HOSTS or norm_b in _WILDCARD_HOSTS:
        return True
    return norm_a == norm_b


async def _probe_bind(host: str, port: int) -> bool:
    try:
        srv = await asyncio.start_server(lambda _r, _w: None, host, port)
    except OSError:
        return False
    srv.close()
    await srv.wait_closed()
    return True


async def _validate_network_and_auth(
    hass: HomeAssistant,
    user_input: dict[str, Any],
    *,
    require_devid: bool,
    current_entry: config_entries.ConfigEntry | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    cleaned: dict[str, Any] = {}
    errors: dict[str, str] = {}

    if CONF_NAME in user_input:
        name = str(user_input.get(CONF_NAME, "")).strip()
        cleaned[CONF_NAME] = name or "LokalTerm"

    if require_devid:
        devid = str(user_input.get(CONF_DEVID, "")).strip()
        if not devid:
            errors[CONF_DEVID] = "empty_devid"
        cleaned[CONF_DEVID] = devid

    devpin = str(user_input.get(CONF_DEVPIN, "")).strip()
    if not devpin:
        errors[CONF_DEVPIN] = "empty_devpin"
    cleaned[CONF_DEVPIN] = devpin

    host = str(user_input.get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST)).strip()
    if not _is_valid_host(host):
        errors[CONF_LISTEN_HOST] = "invalid_host"
    cleaned[CONF_LISTEN_HOST] = host

    raw_port = user_input.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT)
    port: int | None = None
    if isinstance(raw_port, bool):
        errors[CONF_LISTEN_PORT] = "invalid_port"
    else:
        try:
            port_f = float(raw_port)
            if not port_f.is_integer():
                errors[CONF_LISTEN_PORT] = "invalid_port"
            else:
                port_i = int(port_f)
                if 1 <= port_i <= 65535:
                    port = port_i
                    cleaned[CONF_LISTEN_PORT] = port_i
                else:
                    errors[CONF_LISTEN_PORT] = "invalid_port"
        except (ValueError, TypeError, OverflowError):
            errors[CONF_LISTEN_PORT] = "invalid_port"

    if not errors.get(CONF_LISTEN_HOST) and port is not None:
        for existing in hass.config_entries.async_entries(DOMAIN):
            if current_entry is not None and existing.entry_id == current_entry.entry_id:
                continue
            existing_cfg = {**existing.data, **existing.options}
            existing_port = int(existing_cfg.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT))
            existing_host = str(existing_cfg.get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST))
            if existing_port == port and _hosts_overlap(existing_host, host):
                errors[CONF_LISTEN_PORT] = "port_in_use"
                break

    if not errors.get(CONF_LISTEN_HOST) and not errors.get(CONF_LISTEN_PORT) and port is not None:
        same_running_socket = False
        if current_entry is not None:
            cur_cfg = {**current_entry.data, **current_entry.options}
            cur_host = str(cur_cfg.get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST)).strip()
            cur_port = int(cur_cfg.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT))
            if cur_host == host and cur_port == port:
                same_running_socket = True

        if not same_running_socket and not await _probe_bind(host, port):
            errors[CONF_LISTEN_PORT] = "cannot_bind"

    return cleaned, errors


def _build_user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    vals = defaults or {}
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=vals.get(CONF_NAME, "LokalTerm")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Required(CONF_DEVID, default=vals.get(CONF_DEVID, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            ),
            vol.Required(CONF_DEVPIN, default=vals.get(CONF_DEVPIN, "")): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
            vol.Optional(
                CONF_LISTEN_HOST,
                default=vals.get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Optional(
                CONF_LISTEN_PORT,
                default=vals.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=65535,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


def _build_options_schema(defaults: dict[str, Any]) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(
                CONF_DEVPIN,
                default=defaults.get(CONF_DEVPIN, ""),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD)),
            vol.Optional(
                CONF_LISTEN_HOST,
                default=defaults.get(CONF_LISTEN_HOST, DEFAULT_LISTEN_HOST),
            ): TextSelector(TextSelectorConfig(type=TextSelectorType.TEXT)),
            vol.Optional(
                CONF_LISTEN_PORT,
                default=defaults.get(CONF_LISTEN_PORT, DEFAULT_LISTEN_PORT),
            ): NumberSelector(
                NumberSelectorConfig(
                    min=1,
                    max=65535,
                    step=1,
                    mode=NumberSelectorMode.BOX,
                )
            ),
        }
    )


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> LokalTermOptionsFlow:
        return LokalTermOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=_build_user_schema(),
            )

        cleaned, errors = await _validate_network_and_auth(
            self.hass,
            user_input,
            require_devid=True,
        )
        if errors:
            return self.async_show_form(
                step_id="user",
                data_schema=_build_user_schema(user_input),
                errors=errors,
            )

        await self.async_set_unique_id(cleaned[CONF_DEVID])
        self._abort_if_unique_id_configured()

        title = cleaned.pop(CONF_NAME)
        return self.async_create_entry(title=title, data=cleaned)


class LokalTermOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        current = {**self.config_entry.data, **self.config_entry.options}

        if user_input is None:
            return self.async_show_form(
                step_id="init",
                data_schema=_build_options_schema(current),
            )

        cleaned, errors = await _validate_network_and_auth(
            self.hass,
            user_input,
            require_devid=False,
            current_entry=self.config_entry,
        )
        if errors:
            return self.async_show_form(
                step_id="init",
                data_schema=_build_options_schema(user_input),
                errors=errors,
            )

        return self.async_create_entry(title="", data=cleaned)
