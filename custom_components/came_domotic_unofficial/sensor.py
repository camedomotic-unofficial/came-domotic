"""Sensor platform for CAME Domotic Unofficial."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CameDomoticUnofficialConfigEntry
from .coordinator import CameDomoticUnofficialDataUpdateCoordinator
from .entity import CameDomoticUnofficialEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticUnofficialConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        CameDomoticThermoZoneSensor(coordinator, zone.act_id, zone.name)
        for zone in coordinator.data.get("thermo_zones", [])
    )


class CameDomoticThermoZoneSensor(CameDomoticUnofficialEntity, SensorEntity):
    """Sensor for a CAME Domotic thermoregulation zone temperature."""

    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS

    def __init__(
        self,
        coordinator: CameDomoticUnofficialDataUpdateCoordinator,
        act_id: int,
        zone_name: str,
    ) -> None:
        """Initialize the thermo zone sensor."""
        super().__init__(coordinator, entity_key=f"thermo_zone_{act_id}")
        self._act_id = act_id
        self._attr_name = zone_name

    def _find_zone(self):
        """Find the thermo zone matching this sensor's act_id."""
        for zone in self.coordinator.data.get("thermo_zones", []):
            if zone.act_id == self._act_id:
                return zone
        return None

    @property
    def native_value(self) -> float | None:
        """Return the current temperature of the zone."""
        zone = self._find_zone()
        return zone.temperature if zone else None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional thermo zone attributes."""
        zone = self._find_zone()
        if zone is None:
            return None
        return {
            "set_point": zone.set_point,
            "mode": zone.mode.name,
            "season": zone.season.name,
            "status": zone.status.name,
            "antifreeze": zone.antifreeze,
            "floor_ind": zone.floor_ind,
            "room_ind": zone.room_ind,
        }
