"""Climate platform for CAME Domotic.

Exposes CAME Domotic thermoregulation zones as Home Assistant climate entities.
Maps the two-axis CAME model (plant-level season + zone-level mode) onto HA's
climate abstractions:

- Season (WINTER/SUMMER) determines HEAT vs COOL in the HA UI
- Zone mode (OFF/MANUAL/AUTO/JOLLY) maps to HVACMode and preset
- Fan speed maps conditionally to FAN_MODE (only for fan-coil zones)

Setting temperature always switches the zone to MANUAL mode because the CAME
server silently ignores temperature changes in AUTO/JOLLY modes.
"""

from __future__ import annotations

import logging
from typing import Any

from aiocamedomotic.models import (
    ThermoZoneFanSpeed,
    ThermoZoneMode,
    ThermoZoneSeason,
    ThermoZoneStatus,
)
from homeassistant.components.climate import (
    ATTR_TEMPERATURE,
    PRESET_NONE,
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CameDomoticConfigEntry
from .coordinator import CameDomoticDataUpdateCoordinator
from .entity import CameDomoticDeviceEntity

_LOGGER = logging.getLogger(__name__)

# Map aiocamedomotic ThermoZoneFanSpeed to HA fan mode strings.
_FAN_MODE_MAP: dict[ThermoZoneFanSpeed, str] = {
    ThermoZoneFanSpeed.OFF: "off",
    ThermoZoneFanSpeed.SLOW: "low",
    ThermoZoneFanSpeed.MEDIUM: "medium",
    ThermoZoneFanSpeed.FAST: "high",
    ThermoZoneFanSpeed.AUTO: "auto",
}
_FAN_MODE_REVERSE: dict[str, ThermoZoneFanSpeed] = {
    v: k for k, v in _FAN_MODE_MAP.items()
}

_PRESET_JOLLY = "Jolly"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up climate platform."""
    coordinator = entry.runtime_data.coordinator
    zones = coordinator.data.thermo_zones
    _LOGGER.debug("Setting up %d climate entit(ies)", len(zones))
    async_add_entities(
        CameDomoticClimate(
            coordinator,
            act_id,
            zone.name,
            zone.fan_speed,
            zone.floor_ind,
            zone.room_ind,
        )
        for act_id, zone in zones.items()
    )


class CameDomoticClimate(CameDomoticDeviceEntity, ClimateEntity):
    """Climate entity for a CAME Domotic thermoregulation zone.

    Maps the CAME two-axis model (season + mode) onto HA's climate
    entity. Season is a plant-level setting controlled via the select
    entity; this entity handles zone-level mode and temperature control.
    """

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_precision = 0.1
    _attr_target_temperature_step = 0.1
    _attr_min_temp = 5.0
    _attr_max_temp = 34.0
    _attr_preset_modes = [PRESET_NONE, _PRESET_JOLLY]
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        act_id: int,
        zone_name: str,
        initial_fan_speed: ThermoZoneFanSpeed,
        floor_ind: int | None = None,
        room_ind: int | None = None,
    ) -> None:
        """Initialize the climate entity.

        Args:
            coordinator: The data update coordinator.
            act_id: The actuator ID that identifies this thermo zone.
            zone_name: The display name of the zone.
            initial_fan_speed: The fan speed at setup time; UNKNOWN means
                the zone has no fan coil and FAN_MODE is not exposed.
            floor_ind: Floor index for suggested area lookup.
            room_ind: Room index for suggested area lookup.
        """
        super().__init__(
            coordinator,
            entity_key=f"climate_{act_id}",
            device_name=zone_name,
            device_id=f"thermo_zone_{act_id}",
            floor_ind=floor_ind,
            room_ind=room_ind,
        )
        self._act_id = act_id
        self._attr_has_entity_name = False
        self._attr_name = zone_name

        # Build supported features based on zone capabilities.
        features = (
            ClimateEntityFeature.TARGET_TEMPERATURE
            | ClimateEntityFeature.PRESET_MODE
            | ClimateEntityFeature.TURN_ON
            | ClimateEntityFeature.TURN_OFF
        )
        self._has_fan = initial_fan_speed != ThermoZoneFanSpeed.UNKNOWN
        if self._has_fan:
            features |= ClimateEntityFeature.FAN_MODE
            self._attr_fan_modes = list(_FAN_MODE_MAP.values())
        self._attr_supported_features = features

    # --- Read-only properties ---

    @property
    def hvac_mode(self) -> HVACMode | None:
        """Return the current HVAC mode based on zone mode and season."""
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            return None
        if zone.season == ThermoZoneSeason.PLANT_OFF:
            return HVACMode.OFF
        if zone.mode == ThermoZoneMode.OFF:
            return HVACMode.OFF
        if zone.mode == ThermoZoneMode.MANUAL:
            if zone.season == ThermoZoneSeason.WINTER:
                return HVACMode.HEAT
            return HVACMode.COOL
        if zone.mode in (ThermoZoneMode.AUTO, ThermoZoneMode.JOLLY):
            return HVACMode.AUTO
        return None

    @property
    def hvac_modes(self) -> list[HVACMode]:
        """Return available HVAC modes based on current season."""
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            return [HVACMode.OFF]
        if zone.season == ThermoZoneSeason.WINTER:
            return [HVACMode.OFF, HVACMode.HEAT, HVACMode.AUTO]
        if zone.season == ThermoZoneSeason.SUMMER:
            return [HVACMode.OFF, HVACMode.COOL, HVACMode.AUTO]
        return [HVACMode.OFF]

    @property
    def hvac_action(self) -> HVACAction | None:
        """Return what the device is actually doing right now."""
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            return None
        if zone.mode == ThermoZoneMode.OFF or zone.season == ThermoZoneSeason.PLANT_OFF:
            return HVACAction.OFF
        if zone.status == ThermoZoneStatus.ON:
            if zone.season == ThermoZoneSeason.WINTER:
                return HVACAction.HEATING
            return HVACAction.COOLING
        return HVACAction.IDLE

    @property
    def current_temperature(self) -> float | None:
        """Return the current temperature in degrees Celsius."""
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            return None
        return zone.temperature

    @property
    def target_temperature(self) -> float | None:
        """Return the target temperature in degrees Celsius."""
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            return None
        return zone.set_point

    @property
    def fan_mode(self) -> str | None:
        """Return the current fan mode."""
        if not self._has_fan:
            return None
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            return None
        return _FAN_MODE_MAP.get(zone.fan_speed)

    @property
    def preset_mode(self) -> str | None:
        """Return the current preset mode ('Jolly' when JOLLY, else 'none')."""
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            return None
        if zone.mode == ThermoZoneMode.JOLLY:
            return _PRESET_JOLLY
        return PRESET_NONE

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional thermo zone attributes not covered by climate entity."""
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            return None
        return {
            "dehumidifier_enabled": zone.dehumidifier_enabled,
            "dehumidifier_setpoint": zone.dehumidifier_setpoint,
            "antifreeze": zone.antifreeze,
            "t1": zone.t1,
            "t2": zone.t2,
            "t3": zone.t3,
        }

    # --- Control methods ---

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """Set the HVAC mode.

        Maps HA modes to CAME zone modes:
        - OFF -> ThermoZoneMode.OFF
        - HEAT/COOL -> ThermoZoneMode.MANUAL
        - AUTO -> ThermoZoneMode.AUTO
        """
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            _LOGGER.warning(
                "Cannot set HVAC mode for zone act_id=%d: not found in coordinator data",
                self._act_id,
            )
            return

        if hvac_mode == HVACMode.OFF:
            await self.coordinator.api.async_set_thermo_zone_mode(
                zone, ThermoZoneMode.OFF
            )
        elif hvac_mode in (HVACMode.HEAT, HVACMode.COOL):
            await self.coordinator.api.async_set_thermo_zone_mode(
                zone, ThermoZoneMode.MANUAL
            )
        elif hvac_mode == HVACMode.AUTO:
            await self.coordinator.api.async_set_thermo_zone_mode(
                zone, ThermoZoneMode.AUTO
            )
        else:
            _LOGGER.warning(
                "Unhandled HVAC mode %s for zone act_id=%d",
                hvac_mode,
                self._act_id,
            )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """Set the target temperature.

        Always uses async_set_config with MANUAL mode to guarantee the
        temperature takes effect. The CAME server silently ignores
        temperature changes in AUTO/JOLLY modes, so switching to MANUAL
        is the correct behavior when a user explicitly adjusts the
        temperature.
        """
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            _LOGGER.warning(
                "Cannot set temperature for zone act_id=%d: "
                "not found in coordinator data",
                self._act_id,
            )
            return

        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        await self.coordinator.api.async_set_thermo_zone_config(
            zone, ThermoZoneMode.MANUAL, temperature
        )

    async def async_set_fan_mode(self, fan_mode: str) -> None:
        """Set the fan mode."""
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            _LOGGER.warning(
                "Cannot set fan mode for zone act_id=%d: not found in coordinator data",
                self._act_id,
            )
            return

        speed = _FAN_MODE_REVERSE.get(fan_mode)
        if speed is None:
            _LOGGER.warning("Unknown fan mode: %s", fan_mode)
            return

        await self.coordinator.api.async_set_thermo_zone_fan_speed(zone, speed)

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode.

        'Jolly' activates CAME's JOLLY mode. 'none' reverts from JOLLY
        to AUTO; if not currently in JOLLY, this is a no-op.
        """
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            _LOGGER.warning(
                "Cannot set preset for zone act_id=%d: not found in coordinator data",
                self._act_id,
            )
            return

        if preset_mode == _PRESET_JOLLY:
            await self.coordinator.api.async_set_thermo_zone_mode(
                zone, ThermoZoneMode.JOLLY
            )
        elif preset_mode == PRESET_NONE and zone.mode == ThermoZoneMode.JOLLY:
            await self.coordinator.api.async_set_thermo_zone_mode(
                zone, ThermoZoneMode.AUTO
            )

    async def async_turn_on(self) -> None:
        """Turn on the climate entity by switching to AUTO mode."""
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            _LOGGER.warning(
                "Cannot turn on zone act_id=%d: not found in coordinator data",
                self._act_id,
            )
            return
        await self.coordinator.api.async_set_thermo_zone_mode(zone, ThermoZoneMode.AUTO)

    async def async_turn_off(self) -> None:
        """Turn off the climate entity by switching to OFF mode."""
        zone = self.coordinator.data.thermo_zones.get(self._act_id)
        if zone is None:
            _LOGGER.warning(
                "Cannot turn off zone act_id=%d: not found in coordinator data",
                self._act_id,
            )
            return
        await self.coordinator.api.async_set_thermo_zone_mode(zone, ThermoZoneMode.OFF)
