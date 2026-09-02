"""CameDomoticEntity class."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import (
    DeviceInfo,
    async_get_device_id_by_identifier,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTRIBUTION, CONF_SERVER_INFO, DOMAIN, MANUFACTURER
from .coordinator import CameDomoticDataUpdateCoordinator

_LOGGER: logging.Logger = logging.getLogger(__name__)


def gateway_device_info(entry: ConfigEntry) -> DeviceInfo:
    """Build the DeviceInfo describing the CAME server (gateway) device.

    Shared by the gateway-level entities and by the explicit registration done
    during setup, so per-device entities can link to the gateway through
    ``via_device_id``.
    """
    stored = entry.data.get(CONF_SERVER_INFO, {})
    return DeviceInfo(
        translation_key="came_server_device_friendly_name",
        identifiers={(DOMAIN, entry.entry_id)},
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
        self._attr_device_info = gateway_device_info(coordinator.config_entry)

    @property
    def available(self) -> bool:
        """Return True only if the coordinator is up and the server is reachable."""
        return super().available and self.coordinator.server_available


def _get_suggested_area(
    coordinator: CameDomoticDataUpdateCoordinator,
    room_ind: int | None,
) -> str | None:
    """Look up the room name for a device's room_ind from topology.

    Returns the room name if found, or None if the room_ind is not
    available or not found in the coordinator's topology data.
    """
    if room_ind is None:
        return None
    topology = coordinator.data.topology
    if topology is None:
        return None
    for floor in topology.floors:
        for room in floor.rooms:
            if room.id == room_ind:
                _LOGGER.debug("Resolved room_ind=%d to area '%s'", room_ind, room.name)
                return room.name
    _LOGGER.debug("Room index %d not found in topology, no area suggestion", room_ind)
    return None


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
        device_translation_key: str | None = None,
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
            device_translation_key: Optional key into the ``device`` section
                of the translations; the translated name receives
                ``device_name`` via the ``{name}`` placeholder.
        """
        super().__init__(coordinator)
        assert coordinator.config_entry is not None  # noqa: S101  # nosec B101
        entry_id = coordinator.config_entry.entry_id
        self._attr_unique_id = f"{entry_id}_{entity_key}"
        suggested_area = _get_suggested_area(coordinator, room_ind)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{entry_id}_{device_id}")},
            name=device_name,
            manufacturer=MANUFACTURER,
            via_device_id=async_get_device_id_by_identifier(
                coordinator.hass, (DOMAIN, entry_id), config_entry_id=entry_id
            ),
            suggested_area=suggested_area,
        )
        if device_translation_key is not None:
            self._attr_device_info["translation_key"] = device_translation_key
            self._attr_device_info["translation_placeholders"] = {"name": device_name}
        _LOGGER.debug(
            "Device entity '%s' initialized (suggested_area=%s)",
            device_name,
            suggested_area,
        )

    @property
    def available(self) -> bool:
        """Return True only if the coordinator is up and the server is reachable."""
        return super().available and self.coordinator.server_available
