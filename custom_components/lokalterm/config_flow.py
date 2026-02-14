from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME

from .const import (
    DOMAIN,
    CONF_LISTEN_HOST,
    CONF_LISTEN_PORT,
    CONF_DEVID,
    CONF_DEVPIN,
    DEFAULT_LISTEN_HOST,
    DEFAULT_LISTEN_PORT,
)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_NAME, default="LokalTerm"): str,
        vol.Required(CONF_DEVID): str,
        vol.Required(CONF_DEVPIN): str,
        vol.Optional(CONF_LISTEN_HOST, default=DEFAULT_LISTEN_HOST): str,
        vol.Optional(CONF_LISTEN_PORT, default=DEFAULT_LISTEN_PORT): int,
    }
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(step_id="user", data_schema=STEP_USER_DATA_SCHEMA)

        await self.async_set_unique_id(user_input[CONF_DEVID])
        self._abort_if_unique_id_configured()

        title = user_input.pop(CONF_NAME)
        return self.async_create_entry(title=title, data=user_input)
