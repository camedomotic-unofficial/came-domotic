"""Light platform for CAME Domotic.

Exposes CAME Domotic lights as Home Assistant light entities.
Supports three light types via the aiocamedomotic library:
- STEP_STEP: simple on/off control (ColorMode.ONOFF)
- DIMMER: on/off with brightness control (ColorMode.BRIGHTNESS)
- RGB: on/off with brightness and RGB color control (ColorMode.RGB)
"""

from __future__ import annotations

import logging
from typing import Any

from aiocamedomotic.models import LightStatus, LightType
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CameDomoticConfigEntry
from .coordinator import CameDomoticDataUpdateCoordinator
from .entity import CameDomoticEntity

_LOGGER = logging.getLogger(__name__)

# Map aiocamedomotic LightType to Home Assistant ColorMode.
_COLOR_MODE_MAP: dict[LightType, ColorMode] = {
    LightType.STEP_STEP: ColorMode.ONOFF,
    LightType.DIMMER: ColorMode.BRIGHTNESS,
    LightType.RGB: ColorMode.RGB,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up light platform."""
    coordinator = entry.runtime_data.coordinator
    lights = coordinator.data.lights
    _LOGGER.debug("Setting up %d light(s)", len(lights))
    async_add_entities(
        CameDomoticLight(coordinator, act_id, light.name, light.type)
        for act_id, light in lights.items()
    )


class CameDomoticLight(CameDomoticEntity, LightEntity):
    """Light entity for a CAME Domotic light.

    Supports on/off, dimmable, and RGB lights depending on the
    LightType reported by the CAME server.
    """

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        act_id: int,
        light_name: str,
        light_type: LightType,
    ) -> None:
        """Initialize the light entity.

        Args:
            coordinator: The data update coordinator.
            act_id: The actuator ID that identifies this light.
            light_name: The display name of the light.
            light_type: The type of light (STEP_STEP, DIMMER, RGB).
        """
        super().__init__(coordinator, entity_key=f"light_{act_id}")
        self._act_id = act_id
        self._attr_has_entity_name = False
        self._attr_name = light_name
        color_mode = _COLOR_MODE_MAP.get(light_type, ColorMode.ONOFF)
        self._attr_color_mode = color_mode
        self._attr_supported_color_modes = {color_mode}

    @property
    def is_on(self) -> bool | None:
        """Return True if the light is on."""
        light = self.coordinator.data.lights.get(self._act_id)
        if light is None:
            return None
        return light.status == LightStatus.ON

    @property
    def brightness(self) -> int | None:
        """Return the brightness (0-255 HA scale).

        Converts from CAME's 0-100 percentage to HA's 0-255 range.
        Returns None for ONOFF lights or when light data is unavailable.
        HA only calls this property for modes that support brightness.
        """
        light = self.coordinator.data.lights.get(self._act_id)
        if light is None or light.perc is None:
            return None
        return round(light.perc * 255 / 100)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        """Return the RGB color of the light.

        Returns None when light data is unavailable or has no color.
        HA only calls this property for modes that support RGB.
        """
        light = self.coordinator.data.lights.get(self._act_id)
        if light is None or light.rgb is None:
            return None
        return (light.rgb[0], light.rgb[1], light.rgb[2])

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the light with optional brightness and RGB color."""
        light = self.coordinator.data.lights.get(self._act_id)
        if light is None:
            _LOGGER.warning(
                "Cannot turn on light act_id=%d: not found in coordinator data",
                self._act_id,
            )
            return

        # Convert HA brightness (0-255) to CAME brightness (0-100)
        brightness: int | None = None
        if ATTR_BRIGHTNESS in kwargs:
            brightness = round(kwargs[ATTR_BRIGHTNESS] * 100 / 255)

        # Convert HA rgb_color tuple to CAME rgb list
        rgb: list[int] | None = None
        if ATTR_RGB_COLOR in kwargs:
            rgb = list(kwargs[ATTR_RGB_COLOR])

        await self.coordinator.api.async_set_light_status(
            light, LightStatus.ON, brightness=brightness, rgb=rgb
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the light."""
        light = self.coordinator.data.lights.get(self._act_id)
        if light is None:
            _LOGGER.warning(
                "Cannot turn off light act_id=%d: not found in coordinator data",
                self._act_id,
            )
            return
        await self.coordinator.api.async_set_light_status(light, LightStatus.OFF)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional light attributes."""
        light = self.coordinator.data.lights.get(self._act_id)
        if light is None:
            return None
        return {
            "light_type": light.type.name,
        }
