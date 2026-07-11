"""Sensor platform for CAME Domotic."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from aiocamedomotic.models import (
    AnalogIn,
    AnalogSensor,
    AnalogSensorType,
    EnergyMeter,
    LoadsCtrlMeter,
    ScenarioStatus,
    ThermoZone,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfPressure,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import CameDomoticConfigEntry
from .const import ATTRIBUTION, DOMAIN
from .coordinator import CameDomoticDataUpdateCoordinator
from .entity import CameDomoticDeviceEntity, CameDomoticEntity
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


@dataclass(frozen=True, kw_only=True)
class CameDomoticAnalogSensorDescription(SensorEntityDescription):
    """Describes a CAME Domotic analog sensor entity."""

    value_fn: Callable[[AnalogSensor], float | None]


ANALOG_SENSOR_DESCRIPTIONS: dict[
    AnalogSensorType, CameDomoticAnalogSensorDescription
] = {
    AnalogSensorType.TEMPERATURE: CameDomoticAnalogSensorDescription(
        key="analog_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda sensor: sensor.value,
    ),
    AnalogSensorType.HUMIDITY: CameDomoticAnalogSensorDescription(
        key="analog_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda sensor: sensor.value,
    ),
    AnalogSensorType.PRESSURE: CameDomoticAnalogSensorDescription(
        key="analog_pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda sensor: sensor.value,
    ),
}


def _get_analog_sensor_description(
    sensor: AnalogSensor,
) -> CameDomoticAnalogSensorDescription:
    """Return the entity description for an analog sensor based on its type."""
    known = ANALOG_SENSOR_DESCRIPTIONS.get(sensor.sensor_type)
    if known is not None:
        return known
    return CameDomoticAnalogSensorDescription(
        key="analog_unknown",
        native_unit_of_measurement=sensor.unit or None,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda s: s.value,
    )


@dataclass(frozen=True, kw_only=True)
class CameDomoticAnalogInputDescription(SensorEntityDescription):
    """Describes a CAME Domotic analog input entity."""

    value_fn: Callable[[AnalogIn], float | None]


ANALOG_INPUT_DESCRIPTIONS: dict[str, CameDomoticAnalogInputDescription] = {
    "C": CameDomoticAnalogInputDescription(
        key="analog_input_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda ai: ai.value,
    ),
    "%": CameDomoticAnalogInputDescription(
        key="analog_input_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda ai: ai.value,
    ),
    "hPa": CameDomoticAnalogInputDescription(
        key="analog_input_pressure",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE,
        native_unit_of_measurement=UnitOfPressure.HPA,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda ai: ai.value,
    ),
}


def _normalize_unit(unit: str | None) -> str:
    """Normalize a unit string for case-insensitive, variant-tolerant lookup.

    Strips leading/trailing whitespace, removes degree symbols (° and º),
    and lowercases the result so that e.g. '°C', 'c', ' hPa ', 'HPA' all
    match their canonical entries.
    """
    if not unit:
        return ""
    return unit.strip().replace("°", "").replace("\u00ba", "").lower()


_NORMALIZED_ANALOG_INPUT_DESCRIPTIONS: dict[str, CameDomoticAnalogInputDescription] = {
    _normalize_unit(k): v for k, v in ANALOG_INPUT_DESCRIPTIONS.items()
}


def _get_analog_input_description(
    analog_input: AnalogIn,
) -> CameDomoticAnalogInputDescription:
    """Return the entity description for an analog input based on its unit.

    Known units ('C', '%', 'hPa') are mapped to HA device classes for
    proper rendering.  The lookup is case-insensitive and tolerates common
    variants (e.g. '°C', 'HPA').  Unknown units fall back to a generic
    description that preserves the raw unit string.
    """
    known = _NORMALIZED_ANALOG_INPUT_DESCRIPTIONS.get(
        _normalize_unit(analog_input.unit)
    )
    if known is not None:
        return known
    return CameDomoticAnalogInputDescription(
        key="analog_input_generic",
        native_unit_of_measurement=analog_input.unit or None,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda ai: ai.value,
    )


@dataclass(frozen=True, kw_only=True)
class CameDomoticEnergyMeterDescription(SensorEntityDescription):
    """Describes a CAME Domotic energy meter sensor entity."""

    value_fn: Callable[[EnergyMeter], int | None]


ENERGY_METER_DIAGNOSTIC_SENSORS: tuple[CameDomoticEnergyMeterDescription, ...] = (
    # No device_class: HA forbids ENERGY with MEASUREMENT, and these are
    # rolling averages reported by the server, not cumulative counters.
    CameDomoticEnergyMeterDescription(
        key="energy_last_24h_avg",
        translation_key="energy_last_24h_avg",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda meter: meter.last_24h_avg,
    ),
    CameDomoticEnergyMeterDescription(
        key="energy_last_month_avg",
        translation_key="energy_last_month_avg",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda meter: meter.last_month_avg,
    ),
)


def _power_unit(unit: str | None) -> str | None:
    """Map the meter-reported power unit to an HA unit, passing unknowns through."""
    if unit == "W":
        return UnitOfPower.WATT
    return unit or None


def _energy_unit(unit: str | None) -> str | None:
    """Map the meter-reported energy unit to an HA unit, passing unknowns through."""
    if unit == "Wh":
        return UnitOfEnergy.WATT_HOUR
    return unit or None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor platform."""
    coordinator = entry.runtime_data.coordinator
    ping_coordinator = entry.runtime_data.ping_coordinator
    zones = coordinator.data.thermo_zones
    analog_sensors = coordinator.data.analog_sensors
    analog_inputs = coordinator.data.analog_inputs
    scenarios = coordinator.data.scenarios
    energy_meters = coordinator.data.energy_meters
    loadsctrl_meters = coordinator.data.loadsctrl_meters
    _LOGGER.debug(
        "Setting up %d thermo zone sensor(s), %d analog sensor(s), "
        "%d analog input(s), %d scenario status sensor(s), "
        "%d energy meter(s), and %d loads controller(s)",
        len(zones),
        len(analog_sensors),
        len(analog_inputs),
        len(scenarios),
        len(energy_meters),
        len(loadsctrl_meters),
    )
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
            *(
                CameDomoticAnalogSensorEntity(
                    coordinator,
                    act_id,
                    sensor.name,
                    _get_analog_sensor_description(sensor),
                )
                for act_id, sensor in analog_sensors.items()
            ),
            *(
                CameDomoticAnalogInputEntity(
                    coordinator,
                    act_id,
                    analog_input.name,
                    _get_analog_input_description(analog_input),
                )
                for act_id, analog_input in analog_inputs.items()
            ),
            *(
                CameDomoticScenarioStatusSensor(coordinator, scenario_id, scenario.name)
                for scenario_id, scenario in scenarios.items()
            ),
            *(
                CameDomoticEnergyMeterPowerSensor(coordinator, meter)
                for meter in energy_meters.values()
            ),
            *(
                CameDomoticEnergyMeterDiagnosticSensor(coordinator, meter, description)
                for meter in energy_meters.values()
                for description in ENERGY_METER_DIAGNOSTIC_SENSORS
            ),
            *(
                CameDomoticLoadsCtrlPowerSensor(coordinator, controller)
                for controller in loadsctrl_meters.values()
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


class CameDomoticAnalogSensorEntity(CameDomoticDeviceEntity, SensorEntity):
    """Sensor entity for a CAME Domotic analog sensor."""

    entity_description: CameDomoticAnalogSensorDescription

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        act_id: int,
        sensor_name: str,
        description: CameDomoticAnalogSensorDescription,
    ) -> None:
        """Initialize the analog sensor entity."""
        super().__init__(
            coordinator,
            entity_key=f"analog_sensor_{act_id}_{description.key}",
            device_name=sensor_name,
            device_id=f"analog_sensor_{act_id}",
            floor_ind=None,
            room_ind=None,
        )
        self.entity_description = description
        self._act_id = act_id
        self._attr_has_entity_name = False
        self._attr_name = sensor_name

    @property
    def native_value(self) -> float | None:
        """Return the current value of the analog sensor."""
        sensor = self.coordinator.data.analog_sensors.get(self._act_id)
        if sensor is None:
            return None
        return self.entity_description.value_fn(sensor)


class CameDomoticAnalogInputEntity(CameDomoticDeviceEntity, SensorEntity):
    """Sensor entity for a CAME Domotic standalone analog input."""

    entity_description: CameDomoticAnalogInputDescription

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        act_id: int,
        input_name: str,
        description: CameDomoticAnalogInputDescription,
    ) -> None:
        """Initialize the analog input entity."""
        super().__init__(
            coordinator,
            entity_key=f"analog_input_{act_id}_{description.key}",
            device_name=input_name,
            device_id=f"analog_input_{act_id}",
            floor_ind=None,
            room_ind=None,
        )
        self.entity_description = description
        self._act_id = act_id
        self._attr_has_entity_name = False
        self._attr_name = input_name

    @property
    def native_value(self) -> float | None:
        """Return the current value of the analog input."""
        analog_input = self.coordinator.data.analog_inputs.get(self._act_id)
        if analog_input is None:
            return None
        return self.entity_description.value_fn(analog_input)


class CameDomoticEnergyMeterPowerSensor(CameDomoticDeviceEntity, SensorEntity):
    """Power sensor for a CAME Domotic energy meter.

    Energy meters are plant-level devices (no floor/room placement) that
    report instantaneous power; the server pushes an update whenever the
    measured power changes.
    """

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_suggested_display_precision = 0
    _attr_name = None

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        meter: EnergyMeter,
    ) -> None:
        """Initialize the energy meter power sensor."""
        super().__init__(
            coordinator,
            entity_key=f"energy_meter_{meter.id}_power",
            device_name=meter.name,
            device_id=f"energy_meter_{meter.id}",
        )
        self._meter_id = meter.id
        self._attr_native_unit_of_measurement = _power_unit(meter.unit)

    @property
    def native_value(self) -> int | None:
        """Return the current instantaneous power."""
        meter = self.coordinator.data.energy_meters.get(self._meter_id)
        if meter is None:
            return None
        return meter.instant_power

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return raw meter fields useful for debugging."""
        meter = self.coordinator.data.energy_meters.get(self._meter_id)
        if meter is None:
            return None
        return {
            "meter_type": meter.meter_type.name.lower(),
            "produced": meter.produced,
        }


class CameDomoticLoadsCtrlPowerSensor(CameDomoticDeviceEntity, SensorEntity):
    """Power sensor for a CAME Domotic load shedding controller.

    Reports the current power measured by the controller's associated
    energy meter. The overload threshold (max_power), hysteresis band,
    and associated meter id are exposed as read-only attributes.
    """

    _attr_device_class = SensorDeviceClass.POWER
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_suggested_display_precision = 0
    _attr_name = None

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        controller: LoadsCtrlMeter,
    ) -> None:
        """Initialize the loads controller power sensor."""
        super().__init__(
            coordinator,
            entity_key=f"loadsctrl_{controller.id}_power",
            device_name=controller.name,
            device_id=f"loadsctrl_{controller.id}",
        )
        self._controller_id = controller.id

    @property
    def native_value(self) -> float | None:
        """Return the current power reading."""
        controller = self.coordinator.data.loadsctrl_meters.get(self._controller_id)
        if controller is None:
            return None
        return controller.power

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the controller's read-only configuration."""
        controller = self.coordinator.data.loadsctrl_meters.get(self._controller_id)
        if controller is None:
            return None
        return {
            "max_power": controller.max_power,
            "hysteresis": controller.hysteresis,
            "meter_id": controller.meter_id,
        }


class CameDomoticEnergyMeterDiagnosticSensor(CameDomoticDeviceEntity, SensorEntity):
    """Diagnostic sensor for an energy meter's rolling average values.

    Exposes the raw last_24h_avg / last_month_avg fields as reported by
    the server (refreshed with every meter push update).
    """

    entity_description: CameDomoticEnergyMeterDescription

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        meter: EnergyMeter,
        description: CameDomoticEnergyMeterDescription,
    ) -> None:
        """Initialize the energy meter diagnostic sensor."""
        super().__init__(
            coordinator,
            entity_key=f"energy_meter_{meter.id}_{description.key}",
            device_name=meter.name,
            device_id=f"energy_meter_{meter.id}",
        )
        self.entity_description = description
        self._meter_id = meter.id
        self._attr_native_unit_of_measurement = _energy_unit(meter.energy_unit)

    @property
    def native_value(self) -> int | None:
        """Return the rolling average value."""
        meter = self.coordinator.data.energy_meters.get(self._meter_id)
        if meter is None:
            return None
        return self.entity_description.value_fn(meter)


_SCENARIO_STATUS_VALUES = [s.name for s in ScenarioStatus]


class CameDomoticScenarioStatusSensor(CameDomoticEntity, SensorEntity):
    """Sensor reporting the status of a CAME Domotic scenario.

    Exposes the scenario's current status (OFF, TRIGGERED, ACTIVE) and
    tracks when it was last triggered.
    """

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        scenario_id: int,
        scenario_name: str,
    ) -> None:
        """Initialize the scenario status sensor."""
        super().__init__(coordinator, entity_key=f"scenario_status_{scenario_id}")
        self._scenario_id = scenario_id
        self._attr_has_entity_name = False
        self._attr_name = f"{scenario_name} status"
        self._last_triggered: datetime | None = None
        self._previous_status: str | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Track status transitions to update last_triggered."""
        scenario = self.coordinator.data.scenarios.get(self._scenario_id)
        if scenario is not None:
            current_status = scenario.scenario_status.name
            if current_status == "TRIGGERED" and self._previous_status != "TRIGGERED":
                self._last_triggered = dt_util.utcnow()
            self._previous_status = current_status
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> str | None:
        """Return the current scenario status."""
        scenario = self.coordinator.data.scenarios.get(self._scenario_id)
        if scenario is None:
            return None
        return scenario.scenario_status.name

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return scenario status attributes."""
        scenario = self.coordinator.data.scenarios.get(self._scenario_id)
        if scenario is None:
            return None
        return {
            "allowed_values": _SCENARIO_STATUS_VALUES,
            "last_triggered": self._last_triggered,
        }
