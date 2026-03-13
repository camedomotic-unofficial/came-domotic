"""CameDomoticEntity class."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_SERVER_INFO, DOMAIN, MANUFACTURER
from .coordinator import CameDomoticDataUpdateCoordinator


class CameDomoticEntity(CoordinatorEntity[CameDomoticDataUpdateCoordinator]):
    """Base entity for CAME Domotic."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        entity_key: str = "",
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        assert coordinator.config_entry is not None  # noqa: S101  # nosec B101
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{entity_key}" if entity_key else entry_id
        stored = coordinator.config_entry.data.get(CONF_SERVER_INFO, {})
        self._attr_device_info = DeviceInfo(
            name=f"CAME Domotic ({coordinator.hass.config.location_name})",
            identifiers={(DOMAIN, entry_id)},
            hw_version=stored.get("board"),
            manufacturer=MANUFACTURER,
            model=(
                f"Server type: {stored['type']} - Board: {stored['board']}"
                if "type" in stored
                else None
            ),
            serial_number=stored.get("serial"),
            sw_version=stored.get("swver"),
        )

    @property
    def available(self) -> bool:
        """Return True only if the coordinator is up and the server is reachable."""
        return super().available and self.coordinator.server_available
