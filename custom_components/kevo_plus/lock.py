"""Support for Kevo Plus locks."""
from typing import Any

from aiokevoplus import KevoAuthError, KevoLock

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import KevoCoordinator
from .const import DOMAIN, MODEL

async def async_setup_entry(hass: HomeAssistant, config: ConfigEntry, async_add_entities):
    """Setup the lock platform."""
    coordinator: KevoCoordinator = hass.data[DOMAIN][config.entry_id]

    try:
        devices = await coordinator.get_devices()
    except Exception as ex:
        raise PlatformNotReady("Error getting devices") from ex

    entities = [
        KevoLockEntity(hass=hass, name="Lock", device=lock, coordinator=coordinator)
        for lock in devices
    ]

    async_add_entities(entities)

class KevoLockEntity(LockEntity, CoordinatorEntity):
    """Representation of a Kevo Lock."""

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        device: KevoLock,
        coordinator: KevoCoordinator,
    ) -> None:
        super().__init__(coordinator)
        self._hass = hass
        self._device = device
        self._attr_name = name
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{device.lock_id}_lock"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.lock_id)},
            manufacturer=device.brand,
            name=device.name,
            model=MODEL,
            sw_version=device.firmware,
        )
        self._update_attributes()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the device."""
        try:
            await self._device.lock()
            await self.coordinator.async_request_refresh()
        except KevoAuthError:
            await self.coordinator.entry.async_start_reauth(self._hass)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the device."""
        try:
            await self._device.unlock()
            await self.coordinator.async_request_refresh()
        except KevoAuthError:
            await self.coordinator.entry.async_start_reauth(self._hass)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_attributes()
        self.async_write_ha_state()

    @callback
    def _update_attributes(self) -> None:
        """Update the entity attributes."""
        self._attr_is_locked = self._device.is_locked
        self._attr_is_jammed = self._device.is_jammed
        self._attr_is_locking = self._device.is_locking
        self._attr_is_unlocking = self._device.is_unlocking

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        self.async_on_remove(self._device.api.register_callback(self._handle_device_update))

    @callback
    def _handle_device_update(self, *args):
        """Handle updates from the device."""
        self._update_attributes()
        self.async_write_ha_state()
