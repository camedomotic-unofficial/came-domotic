"""CameDomoticEntity class."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_SERVER_INFO, DOMAIN, MANUFACTURER
from .coordinator import CameDomoticDataUpdateCoordinator


class CameDomoticEntity(CoordinatorEntity[CameDomoticDataUpdateCoordinator]):
    """Base entity for CAME Domotic (gateway device)."""

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
                if "type" in stored and "board" in stored
                else None
            ),
            serial_number=stored.get("serial"),
            sw_version=stored.get("swver"),
        )

    @property
    def available(self) -> bool:
        """Return True only if the coordinator is up and the server is reachable."""
        return super().available and self.coordinator.server_available


def _get_suggested_area(
    coordinator: CameDomoticDataUpdateCoordinator,
    room_ind: int | None,
) -> str | None:
    """Look up the room name for a device's room_ind.

    Returns the room name if found, or None if the room_ind is not
    available or not found in the coordinator's room data.
    """
    if room_ind is None:
        return None
    room = coordinator.data.rooms.get(room_ind)
    if room is None:
        return None
    return room.name


class CameDomoticDeviceEntity(CoordinatorEntity[CameDomoticDataUpdateCoordinator]):
    """Base entity for per-device CAME Domotic entities."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        entity_key: str,
        device_name: str,
        device_id: str,
        floor_ind: int | None = None,
        room_ind: int | None = None,
    ) -> None:
        """Initialize a per-device entity.

        Args:
            coordinator: The data update coordinator.
            entity_key: Unique key for this entity within the config entry.
            device_name: Display name for the HA device.
            device_id: Unique device identifier (e.g. "light_300").
            floor_ind: Floor index (reserved for future hierarchical area
                resolution; currently not used in suggested_area lookup).
            room_ind: Room index for suggested area lookup.
        """
        super().__init__(coordinator)
        assert coordinator.config_entry is not None  # noqa: S101  # nosec B101
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{entity_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{device_id}")},
            name=device_name,
            manufacturer=MANUFACTURER,
            via_device=(DOMAIN, entry_id),
            suggested_area=_get_suggested_area(coordinator, room_ind),
        )

    @property
    def available(self) -> bool:
        """Return True only if the coordinator is up and the server is reachable."""
        return super().available and self.coordinator.server_available
