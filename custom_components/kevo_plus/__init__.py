# Kevo lock integration
"""The Kevo Plus integration."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import uuid

from aiokevoplus import KevoApi, KevoAuthError
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.LOCK, Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Kevo Plus from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    password = entry.data.get(CONF_PASSWORD)
    device_id = uuid.UUID(bytes=hashlib.md5(password.encode()).digest())
    client = KevoApi(device_id)

    try:
        await client.login(entry.data.get(CONF_USERNAME), password)
    except Exception as ex:
        raise ConfigEntryNotReady("Timeout while connecting to Kevo servers") from ex

    coordinator = KevoCoordinator(hass, client, entry)
    try:
        await coordinator.get_devices()
    except Exception as ex:
        raise ConfigEntryNotReady("Failed to get Kevo devices") from ex

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_config_entry_first_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.data[DOMAIN][entry.entry_id].api.websocket_close()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class KevoCoordinator(DataUpdateCoordinator):
    """Kevo Data Coordinator."""

    def __init__(
        self,
        hass: HomeAssistant,
        api: KevoApi,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            # Name of the data. For logging purposes.
            name="Kevo",
        )
        self.api = api
        self.hass = hass
        self.entry = entry
        self._devices = None
        self._device_lock = asyncio.Lock()

    async def get_devices(self) -> list:
        """Retrieve the devices associated with the coordinator."""
        async with self._device_lock:
            if self._devices is None:
                try:
                    self._devices = await self.api.get_locks()
                except KevoAuthError:
                    await self.entry.async_start_reauth(self.hass)
            return self._devices

    async def _async_update_data(self):
        await self.api.websocket_connect()
