"""Scene platform for CAME Domotic Unofficial."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.scene import Scene
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CameDomoticUnofficialConfigEntry
from .coordinator import CameDomoticUnofficialDataUpdateCoordinator
from .entity import CameDomoticUnofficialEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticUnofficialConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up scene platform."""
    coordinator = entry.runtime_data.coordinator
    scenarios = coordinator.data.scenarios
    _LOGGER.debug("Setting up %d scenario scene(s)", len(scenarios))
    async_add_entities(
        CameDomoticScene(coordinator, scenario_id, scenario.name)
        for scenario_id, scenario in scenarios.items()
    )


class CameDomoticScene(CameDomoticUnofficialEntity, Scene):
    """Scene entity for a CAME Domotic scenario."""

    def __init__(
        self,
        coordinator: CameDomoticUnofficialDataUpdateCoordinator,
        scenario_id: int,
        scenario_name: str,
    ) -> None:
        """Initialize the scenario scene."""
        super().__init__(coordinator, entity_key=f"scenario_{scenario_id}")
        self._scenario_id = scenario_id
        self._attr_has_entity_name = False
        self._attr_name = scenario_name

    async def async_activate(self, **kwargs: Any) -> None:
        """Activate the scenario."""
        scenario = self.coordinator.data.scenarios.get(self._scenario_id)
        if scenario is None:
            _LOGGER.warning(
                "Cannot activate scenario id=%d: not found in coordinator data",
                self._scenario_id,
            )
            return
        await self.coordinator.api.async_activate_scenario(scenario)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional scenario attributes."""
        scenario = self.coordinator.data.scenarios.get(self._scenario_id)
        if scenario is None:
            return None
        return {
            "scenario_status": scenario.scenario_status.name,
            "user_defined": bool(scenario.user_defined),
        }
