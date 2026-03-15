"""Sensor platform for CAME Domotic."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import logging

from aiocamedomotic.models import ThermoZone
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import CameDomoticConfigEntry
from .const import ATTRIBUTION, DOMAIN
from .coordinator import CameDomoticDataUpdateCoordinator
from .entity import CameDomoticDeviceEntity
from .ping_coordinator import CameDomoticPingCoordinator

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
    entry: CameDomoticConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = entry.runtime_data.coordinator
    ping_coordinator = entry.runtime_data.ping_coordinator
    zones = coordinator.data.thermo_zones
    _LOGGER.debug("Setting up %d thermo zone sensor(s)", len(zones))
    async_add_entities(
        [
            CameDomoticServerLatencySensor(ping_coordinator, entry.entry_id),
            *(
                CameDomoticThermoZoneSensor(
                    coordinator,
                    act_id,
                    zone.name,
                    description,
                    zone.floor_ind,
                    zone.room_ind,
                )
                for act_id, zone in zones.items()
                for description in THERMO_ZONE_SENSORS
            ),
        ]
    )


class CameDomoticThermoZoneSensor(CameDomoticDeviceEntity, SensorEntity):
    """Sensor for a CAME Domotic thermoregulation zone."""

    entity_description: CameDomoticSensorDescription

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        act_id: int,
        zone_name: str,
        description: CameDomoticSensorDescription,
        floor_ind: int | None = None,
        room_ind: int | None = None,
    ) -> None:
        """Initialize the thermo zone sensor."""
        super().__init__(
            coordinator,
            entity_key=f"thermo_zone_{act_id}_{description.key}",
            device_name=zone_name,
            device_id=f"thermo_zone_{act_id}",
            floor_ind=floor_ind,
            room_ind=room_ind,
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


class CameDomoticServerLatencySensor(
    CoordinatorEntity[CameDomoticPingCoordinator], SensorEntity
):
    """Diagnostic sensor reporting round-trip latency to the CAME server in ms.

    Disabled by default — enable it to monitor server response times.
    Shows unknown when the server is unreachable.
    """

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_translation_key = "ping_latency"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MILLISECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: CameDomoticPingCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize the server latency sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_ping_latency"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry_id)})

    @property
    def native_value(self) -> float | None:
        """Return the last measured round-trip latency in milliseconds."""
        return self.coordinator.data.latency_ms
