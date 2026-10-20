"""EGYM sensors: current values (bio age, activity, muscle balance) and the last measured value per exercise,
machine and body metric. The history of the last group is in the long-term statistics."""

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import EgymCoordinator


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    coordinator: EgymCoordinator = entry.runtime_data
    known: set[str] = set()

    @callback
    def add_new() -> None:
        # New exercises or machines show up after a sync; add their sensors then
        new = [key for key in coordinator.data if key not in known]
        known.update(new)
        if new:
            async_add_entities(EgymSensor(coordinator, entry, key) for key in new)

    add_new()
    entry.async_on_unload(coordinator.async_add_listener(add_new))


class EgymSensor(CoordinatorEntity[EgymCoordinator], SensorEntity):
    _attr_has_entity_name = True
    # Chart data for dashboards; the recorder does not need it, the statistics already hold it
    _unrecorded_attributes = frozenset({"sessies", "krachttest", "verloop", "intensiteit"})

    def __init__(self, coordinator: EgymCoordinator, entry: ConfigEntry, key: str) -> None:
        super().__init__(coordinator)
        self._key = key
        info = coordinator.data[key]
        self._attr_name = info["name"]
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        self._attr_native_unit_of_measurement = info["unit"]
        self._attr_icon = info["icon"]
        self._attr_entity_registry_enabled_default = info["enabled"]
        if info["measurement"]:
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
        return self._current["value"] if self._current else None

    @property
    def extra_state_attributes(self):
        return (self._current or {}).get("attrs") or None
