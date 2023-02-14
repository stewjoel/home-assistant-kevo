"""Config flow for Kevo Plus integration."""
from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from aiokevoplus import KevoApi, KevoAuthError
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.data_entry_flow import FlowResult
from httpx import ConnectError, ConnectTimeout

from .const import CONF_LOCKS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kevo Plus."""

    def __init__(self) -> None:
        self.data: dict = {}

        self._api: KevoApi = None
        self._locks = None

    VERSION = 1

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Hande reauthentication step."""
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
            device_id = uuid.UUID(
                bytes=hashlib.md5(user_input[CONF_PASSWORD].encode()).digest()
            )
            self._api = KevoApi(device_id)

            await self._api.login(user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
            self._locks = {dev.lock_id: dev.name for dev in await self._api.get_locks()}
            self.data = user_input
            return await self.async_step_devices()
        except KevoAuthError:
            errors["base"] = "invalid_auth"
        except (ConnectError, ConnectTimeout):
            errors["base"] = "cannot_connect"
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception: %s", ex)
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
                            CONF_LOCKS, default=list(self._locks)
                        ): cv.multi_select(self._locks)
                    }
                ),
            )

        self.data.update(user_input)
        return self.async_create_entry(title=self.data[CONF_USERNAME], data=self.data)
