"""Light platform for CAME Domotic.

Exposes CAME Domotic lights as Home Assistant light entities.
Supports three light types via the aiocamedomotic library:
- STEP_STEP: simple on/off control (ColorMode.ONOFF)
- DIMMER: on/off with brightness control (ColorMode.BRIGHTNESS)
- RGB: on/off with brightness and RGB color control (ColorMode.RGB)
"""

from __future__ import annotations

import logging
import time
from typing import Any

from aiocamedomotic.models import LightStatus, LightType
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CameDomoticConfigEntry
from .coordinator import CameDomoticDataUpdateCoordinator
from .entity import CameDomoticDeviceEntity

_LOGGER = logging.getLogger(__name__)

_OPTIMISTIC_TIMEOUT = 10.0  # seconds before optimistic state is force-cleared

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
        CameDomoticLight(
            coordinator,
            act_id,
            light.name,
            light.type,
            light.floor_ind,
            light.room_ind,
        )
        for act_id, light in lights.items()
    )


class CameDomoticLight(CameDomoticDeviceEntity, LightEntity):
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
        floor_ind: int | None = None,
        room_ind: int | None = None,
    ) -> None:
        """Initialize the light entity.

        Args:
            coordinator: The data update coordinator.
            act_id: The actuator ID that identifies this light.
            light_name: The display name of the light.
            light_type: The type of light (STEP_STEP, DIMMER, RGB).
            floor_ind: Floor index for suggested area lookup.
            room_ind: Room index for suggested area lookup.
        """
        super().__init__(
            coordinator,
            entity_key=f"light_{act_id}",
            device_name=light_name,
            device_id=f"light_{act_id}",
            floor_ind=floor_ind,
            room_ind=room_ind,
        )
        self._act_id = act_id
        self._attr_has_entity_name = False
        self._attr_name = light_name
        color_mode = _COLOR_MODE_MAP.get(light_type, ColorMode.ONOFF)
        self._attr_color_mode = color_mode
        self._attr_supported_color_modes = {color_mode}
        self._optimistic_is_on: bool | None = None
        self._optimistic_brightness: int | None = None
        self._optimistic_rgb: tuple[int, int, int] | None = None
        self._optimistic_snapshot_status: LightStatus | None = None
        self._optimistic_set_at: float | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Clear optimistic state when coordinator data catches up or times out."""
        if self._optimistic_is_on is not None:
            light = self.coordinator.data.lights.get(self._act_id)
            timed_out = (
                self._optimistic_set_at is not None
                and time.monotonic() - self._optimistic_set_at > _OPTIMISTIC_TIMEOUT
            )
            data_changed = (
                light is not None
                and self._optimistic_snapshot_status is not None
                and light.status != self._optimistic_snapshot_status
            )
            if timed_out or data_changed or light is None:
                _LOGGER.debug(
                    "Clearing optimistic state for light act_id=%d"
                    " (timed_out=%s, data_changed=%s)",
                    self._act_id,
                    timed_out,
                    data_changed,
                )
                self._optimistic_is_on = None
                self._optimistic_brightness = None
                self._optimistic_rgb = None
                self._optimistic_snapshot_status = None
                self._optimistic_set_at = None
        super()._handle_coordinator_update()

    @property
    def is_on(self) -> bool | None:
        """Return True if the light is on."""
        if self._optimistic_is_on is not None:
            return self._optimistic_is_on
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
        if self._optimistic_brightness is not None:
            return self._optimistic_brightness
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
        if self._optimistic_rgb is not None:
            return self._optimistic_rgb
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

        # Optimistic update after successful API call
        self._optimistic_snapshot_status = light.status
        self._optimistic_set_at = time.monotonic()
        self._optimistic_is_on = True
        if brightness is not None:
            self._optimistic_brightness = round(brightness * 255 / 100)
        if ATTR_RGB_COLOR in kwargs:
            self._optimistic_rgb = tuple(kwargs[ATTR_RGB_COLOR])
        _LOGGER.debug(
            "Optimistic update for light act_id=%d: is_on=%s, brightness=%s, rgb=%s",
            self._act_id,
            self._optimistic_is_on,
            self._optimistic_brightness,
            self._optimistic_rgb,
        )
        self.async_write_ha_state()

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

        self._optimistic_snapshot_status = light.status
        self._optimistic_set_at = time.monotonic()
        self._optimistic_is_on = False
        _LOGGER.debug(
            "Optimistic update for light act_id=%d: is_on=False",
            self._act_id,
        )
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional light attributes."""
        light = self.coordinator.data.lights.get(self._act_id)
        if light is None:
            return None
        return {
            "light_type": light.type.name,
        }
