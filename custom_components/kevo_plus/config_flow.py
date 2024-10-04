"""Config flow for Kevo Plus integration."""

from __future__ import annotations

import hashlib
import logging
import uuid
from typing import Any

import voluptuous as vol
from aiokevoplus import KevoApi, KevoAuthError
from homeassistant import config_entries
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from httpx import ConnectError, ConnectTimeout

from .const import CONF_LOCKS, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): str,
    vol.Required(CONF_PASSWORD): str,
})

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Kevo Plus."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self.data: dict[str, Any] = {}
        self._api: KevoApi | None = None
        self._locks: dict[str, str] = {}

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
            await self.hass.async_add_executor_job(
                self._api.login,
                user_input[CONF_USERNAME],
                user_input[CONF_PASSWORD]
            )
            locks = await self.hass.async_add_executor_job(self._api.get_locks)
            self._locks = {dev.lock_id: dev.name for dev in locks}
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

    async def async_step_devices(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle lock selection step."""
        if user_input is None:
            return self.async_show_form(
                step_id="devices",
                data_schema=vol.Schema({
                    vol.Required(CONF_LOCKS, default=list(self._locks)): cv.multi_select(self._locks)
                }),
            )

        self.data.update(user_input)
        return self.async_create_entry(
            title=self.data[CONF_USERNAME], data=self.data, options=user_input
        )

    async def async_step_reauth(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle reauthentication step."""
        return await self.async_step_user()

class OptionsFlowHandler(config_entries.OptionsFlow):
    """Options flow for Kevo Plus."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        if self.config_entry.state != config_entries.ConfigEntryState.LOADED:
            return self.async_abort(reason="unknown")

        data = self.hass.data[DOMAIN][self.config_entry.entry_id]
        try:
            locks = await self.hass.async_add_executor_job(data.get_all_devices)
            lock_dict = {dev.lock_id: dev.name for dev in locks}
        except KevoAuthError:
            return self.async_abort(reason="invalid_auth")
        except (ConnectError, ConnectTimeout):
            return self.async_abort(reason="cannot_connect")
        except Exception:  # pylint: disable=broad-except
            return self.async_abort(reason="unknown")

        default_locks = self.config_entry.options.get(CONF_LOCKS) or self.config_entry.data.get(CONF_LOCKS, [])

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Required(CONF_LOCKS, default=default_locks): cv.multi_select(lock_dict),
            }),
        )
