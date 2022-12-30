from homeassistant.const import PERCENTAGE
from .const import DOMAIN, MODEL
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from . import KevoCoordinator
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.sensor import SensorEntity


async def async_setup_entry(hass: HomeAssistant, config, add_entities):
    coordinator: KevoCoordinator = hass.data[DOMAIN][config.entry_id]

    devices = await coordinator.get_devices()

    entities = []
    for lock in devices:
        entities.append(
            KevoSensorEntity(
                hass=hass,
                name="Battery Level",
                device=lock,
                coordinator=coordinator,
                device_type="battery_level",
            )
        )

    add_entities(entities)


class KevoSensorEntity(SensorEntity, CoordinatorEntity):
    def __init__(self, hass, name, device, coordinator, device_type):
        self._hass = hass
        self._device = device
        self._coordinator = coordinator
        self._device_type = device_type

        self._attr_name = name
        if device_type == "battery_level":
            self._attr_device_class = "battery"
        self._attr_has_entity_name = True
        self._attr_native_unit_of_measurement = PERCENTAGE

        self._attr_unique_id = device.lock_id + "_" + device_type

        device._api.register_callback(self._update_data)

        if self._device_type == "battery_level":
            self._attr_native_value = device.battery_level

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.lock_id)},
            manufacturer=device.brand,
            name=device.name,
            model=MODEL,
            sw_version=device.firmware,
        )

        super().__init__(coordinator)

    @callback
    def _update_data(self, args):
        if self._device_type == "battery_level":
            self._attr_native_value = self._device.battery_level
        self.schedule_update_ha_state(False)
