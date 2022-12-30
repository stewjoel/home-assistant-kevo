"""Config flow for Kevo Plus integration."""
from __future__ import annotations

import logging
from homeassistant.const import CONF_USERNAME
import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from aiokevoplus import KevoApi, KevoAuthError

from typing import Any
import voluptuous as vol
from .const import DOMAIN
import uuid

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("username"): str,
        vol.Required("password"): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kevo Plus."""

    def __init__(self):
        self.data: dict = {}

        device_id = uuid.UUID(int=uuid.getnode())
        self._api = KevoApi(device_id)
        self._locks = None

    VERSION = 1

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        return await self.async_step_user()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            await self._api.login(user_input["username"], user_input["password"])
            self._locks = {dev.lock_id: dev.name for dev in await self._api.get_locks()}
            self.data = user_input
            return await self.async_step_devices()
        except KevoAuthError:
            errors["base"] = "invalid_auth"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    async def async_step_devices(self, user_input: dict[str, Any] | None = None):
        """Handle lock selection step."""
        if user_input is None:
            return self.async_show_form(
                step_id="devices",
                data_schema=vol.Schema(
                    {
                        vol.Required(
                            "locks", default=list(self._locks)
                        ): cv.multi_select(self._locks)
                    }
                ),
            )
        else:
            self.data.update(user_input)
            return self.async_create_entry(
                title=self.data[CONF_USERNAME], data=self.data
            )