"""Sensors for EGYM values that only exist as a current value: bio age, activity level and muscle balance."""

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EgymCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator: EgymCoordinator = entry.runtime_data
    async_add_entities(EgymSensor(coordinator, entry, key) for key in coordinator.data)


class EgymSensor(CoordinatorEntity[EgymCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: EgymCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        name, _value, unit, _attrs = coordinator.data[key]
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = unit
        if unit is not None:
            self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"EGYM {coordinator.person}",
            manufacturer="EGYM",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def _current(self):
        return self.coordinator.data.get(self._key)

    @property
    def available(self) -> bool:
        return super().available and self._current is not None

    @property
    def native_value(self):
        return self._current[1] if self._current else None

    @property
    def extra_state_attributes(self):
        return self._current[3] if self._current and self._current[3] else None
