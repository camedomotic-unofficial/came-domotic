"""Cover platform for CAME Domotic.

Exposes CAME Domotic openings (e.g. shutters) as Home Assistant cover
entities. Each opening supports open/close/stop motor control and
slat (tilt) open/close commands via the aiocamedomotic library.
"""

from __future__ import annotations

import logging
from typing import Any

from aiocamedomotic.models import OpeningStatus, OpeningType
from homeassistant.components.cover import (
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CameDomoticConfigEntry
from .coordinator import CameDomoticDataUpdateCoordinator
from .entity import CameDomoticEntity

_LOGGER = logging.getLogger(__name__)

# Map aiocamedomotic OpeningType to Home Assistant CoverDeviceClass.
_DEVICE_CLASS_MAP: dict[OpeningType, CoverDeviceClass] = {
    OpeningType.SHUTTER: CoverDeviceClass.SHUTTER,
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up cover platform."""
    coordinator = entry.runtime_data.coordinator
    openings = coordinator.data.openings
    _LOGGER.debug("Setting up %d opening cover(s)", len(openings))
    async_add_entities(
        CameDomoticCover(coordinator, open_act_id, opening.name, opening.type)
        for open_act_id, opening in openings.items()
    )


class CameDomoticCover(CameDomoticEntity, CoverEntity):
    """Cover entity for a CAME Domotic opening (e.g. shutter).

    Supports open/close/stop motor control and slat (tilt) open/close.
    Position tracking is not available — the CAME API only reports
    discrete motor states (opening, closing, stopped, slat open/close).
    """

    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.STOP_TILT
    )

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        open_act_id: int,
        opening_name: str,
        opening_type: OpeningType,
    ) -> None:
        """Initialize the opening cover.

        Args:
            coordinator: The data update coordinator.
            open_act_id: The actuator ID that identifies this opening.
            opening_name: The display name of the opening.
            opening_type: The type of opening (e.g. SHUTTER).
        """
        super().__init__(coordinator, entity_key=f"opening_{open_act_id}")
        self._open_act_id = open_act_id
        self._attr_has_entity_name = False
        self._attr_name = opening_name
        self._attr_device_class = _DEVICE_CLASS_MAP.get(opening_type)

    @property
    def is_closed(self) -> bool | None:
        """Return None because the CAME API does not track position."""
        return None

    @property
    def is_opening(self) -> bool:
        """Return True if the cover motor is currently opening."""
        opening = self.coordinator.data.openings.get(self._open_act_id)
        if opening is None:
            return False
        return opening.status == OpeningStatus.OPENING

    @property
    def is_closing(self) -> bool:
        """Return True if the cover motor is currently closing."""
        opening = self.coordinator.data.openings.get(self._open_act_id)
        if opening is None:
            return False
        return opening.status == OpeningStatus.CLOSING

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        opening = self.coordinator.data.openings.get(self._open_act_id)
        if opening is None:
            _LOGGER.warning(
                "Cannot open cover open_act_id=%d: not found in coordinator data",
                self._open_act_id,
            )
            return
        await self.coordinator.api.async_set_opening_status(
            opening, OpeningStatus.OPENING
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        opening = self.coordinator.data.openings.get(self._open_act_id)
        if opening is None:
            _LOGGER.warning(
                "Cannot close cover open_act_id=%d: not found in coordinator data",
                self._open_act_id,
            )
            return
        await self.coordinator.api.async_set_opening_status(
            opening, OpeningStatus.CLOSING
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover motor."""
        opening = self.coordinator.data.openings.get(self._open_act_id)
        if opening is None:
            _LOGGER.warning(
                "Cannot stop cover open_act_id=%d: not found in coordinator data",
                self._open_act_id,
            )
            return
        await self.coordinator.api.async_set_opening_status(
            opening, OpeningStatus.STOPPED
        )

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt (slat open)."""
        opening = self.coordinator.data.openings.get(self._open_act_id)
        if opening is None:
            _LOGGER.warning(
                "Cannot open tilt for cover open_act_id=%d: not found",
                self._open_act_id,
            )
            return
        await self.coordinator.api.async_set_opening_status(
            opening, OpeningStatus.SLAT_OPEN
        )

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt (slat close)."""
        opening = self.coordinator.data.openings.get(self._open_act_id)
        if opening is None:
            _LOGGER.warning(
                "Cannot close tilt for cover open_act_id=%d: not found",
                self._open_act_id,
            )
            return
        await self.coordinator.api.async_set_opening_status(
            opening, OpeningStatus.SLAT_CLOSE
        )

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        opening = self.coordinator.data.openings.get(self._open_act_id)
        if opening is None:
            _LOGGER.warning(
                "Cannot stop tilt for cover open_act_id=%d: not found",
                self._open_act_id,
            )
            return
        await self.coordinator.api.async_set_opening_status(
            opening, OpeningStatus.STOPPED
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional opening attributes."""
        opening = self.coordinator.data.openings.get(self._open_act_id)
        if opening is None:
            return None
        return {
            "status": opening.status.name,
            "opening_type": opening.type.name,
        }
