"""Select platform for CAME Domotic.

Exposes a plant-level thermoregulation season selector.
The CAME Domotic server has a single global season setting
(WINTER, SUMMER, PLANT_OFF) that applies to all thermo zones.
"""

from __future__ import annotations

import logging

from aiocamedomotic.models import ThermoZoneSeason
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CameDomoticConfigEntry
from .coordinator import CameDomoticDataUpdateCoordinator
from .entity import CameDomoticEntity

_LOGGER = logging.getLogger(__name__)

# Map between HA option strings and library enum values.
_SEASON_OPTIONS: dict[str, ThermoZoneSeason] = {
    "winter": ThermoZoneSeason.WINTER,
    "summer": ThermoZoneSeason.SUMMER,
    "plant_off": ThermoZoneSeason.PLANT_OFF,
}
_SEASON_REVERSE: dict[ThermoZoneSeason, str] = {
    v: k for k, v in _SEASON_OPTIONS.items()
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up select platform."""
    coordinator = entry.runtime_data.coordinator
    zones = coordinator.data.thermo_zones
    if not zones:
        _LOGGER.debug("No thermo zones found, skipping thermo season select")
        return
    _LOGGER.debug("Setting up thermo season select entity")
    async_add_entities([CameDomoticThermoSeasonSelect(coordinator)])


class CameDomoticThermoSeasonSelect(CameDomoticEntity, SelectEntity):
    """Select entity for the plant-level thermoregulation season.

    Reads the current season from the first thermo zone (all zones
    share the same plant-level season) and sets it via
    async_set_thermo_season on the CAME server.
    """

    _attr_translation_key = "thermo_season"
    _attr_options = list(_SEASON_OPTIONS.keys())

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
    ) -> None:
        """Initialize the thermo season select entity."""
        super().__init__(coordinator, entity_key="thermo_season")

    @property
    def current_option(self) -> str | None:
        """Return the current season from the first thermo zone."""
        zones = self.coordinator.data.thermo_zones
        if not zones:
            return None
        zone = next(iter(zones.values()))
        return _SEASON_REVERSE.get(zone.season)

    async def async_select_option(self, option: str) -> None:
        """Set the plant-level thermoregulation season."""
        season = _SEASON_OPTIONS.get(option)
        if season is None:
            _LOGGER.warning("Unknown thermo season option: %s", option)
            return
        await self.coordinator.api.async_set_thermo_season(season)
