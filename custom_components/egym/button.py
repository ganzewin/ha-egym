"""Button to fetch the latest EGYM data now, instead of waiting for the next sync."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import EgymCoordinator
from .sensor import device_info


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    async_add_entities([EgymRefreshButton(entry.runtime_data, entry)])


class EgymRefreshButton(CoordinatorEntity[EgymCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Gegevens ophalen"
    _attr_icon = "mdi:cloud-download"

    def __init__(self, coordinator: EgymCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_gegevens_ophalen"
        self._attr_device_info = device_info(coordinator, entry)

    @property
    def available(self) -> bool:
        # Stay pressable after a failed sync, so a retry is possible
        return True

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()
