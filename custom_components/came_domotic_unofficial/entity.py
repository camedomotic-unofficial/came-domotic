"""CameDomoticUnofficialEntity class."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, DOMAIN, NAME
from .coordinator import CameDomoticUnofficialDataUpdateCoordinator


class CameDomoticUnofficialEntity(
    CoordinatorEntity[CameDomoticUnofficialDataUpdateCoordinator]
):
    """Base entity for CAME Domotic Unofficial."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CameDomoticUnofficialDataUpdateCoordinator,
        entity_key: str = "",
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{entity_key}" if entity_key else entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.config_entry.entry_id)},
            name=NAME,
            manufacturer=NAME,
        )
