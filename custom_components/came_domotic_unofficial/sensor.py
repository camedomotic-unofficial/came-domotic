"""Sensor platform for CAME Domotic Unofficial."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any

from aiocamedomotic.models import ThermoZone
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CameDomoticUnofficialConfigEntry
from .coordinator import CameDomoticUnofficialDataUpdateCoordinator
from .entity import CameDomoticUnofficialEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class CameDomoticSensorDescription(SensorEntityDescription):
    """Describes a CAME Domotic sensor entity."""

    value_fn: Callable[[ThermoZone], float | str | None]


THERMO_ZONE_SENSORS: tuple[CameDomoticSensorDescription, ...] = (
    CameDomoticSensorDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda zone: zone.temperature,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticUnofficialConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = entry.runtime_data.coordinator
    zones = coordinator.data.thermo_zones
    _LOGGER.debug("Setting up %d thermo zone sensor(s)", len(zones))
    async_add_entities(
        CameDomoticThermoZoneSensor(coordinator, act_id, zone.name, description)
        for act_id, zone in zones.items()
        for description in THERMO_ZONE_SENSORS
    )


class CameDomoticThermoZoneSensor(CameDomoticUnofficialEntity, SensorEntity):
    """Sensor for a CAME Domotic thermoregulation zone."""

    entity_description: CameDomoticSensorDescription

    def __init__(
        self,
        coordinator: CameDomoticUnofficialDataUpdateCoordinator,
        act_id: int,
        zone_name: str,
        description: CameDomoticSensorDescription,
    ) -> None:
        """Initialize the thermo zone sensor."""
        super().__init__(
            coordinator, entity_key=f"thermo_zone_{act_id}_{description.key}"
        )
        self.entity_description = description
        self._act_id = act_id
        self._attr_has_entity_name = False
        self._attr_name = zone_name

    @property
    def native_value(self) -> float | str | None:
        """Return the current value of the sensor."""
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            return None
        return self.entity_description.value_fn(zone)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional thermo zone attributes."""
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            return None
        return {
            "set_point": zone.set_point,
            "mode": zone.mode.name,
            "season": zone.season.name,
            "status": zone.status.name,
            "antifreeze": zone.antifreeze,
        }
