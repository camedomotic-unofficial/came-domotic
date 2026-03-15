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
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CameDomoticConfigEntry
from .coordinator import CameDomoticDataUpdateCoordinator
from .entity import CameDomoticDeviceEntity

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
        CameDomoticCover(
            coordinator,
            open_act_id,
            opening.name,
            opening.type,
            opening.floor_ind,
            opening.room_ind,
        )
        for open_act_id, opening in openings.items()
    )


class CameDomoticCover(CameDomoticDeviceEntity, CoverEntity):
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
        floor_ind: int | None = None,
        room_ind: int | None = None,
    ) -> None:
        """Initialize the opening cover.

        Args:
            coordinator: The data update coordinator.
            open_act_id: The actuator ID that identifies this opening.
            opening_name: The display name of the opening.
            opening_type: The type of opening (e.g. SHUTTER).
            floor_ind: Floor index for suggested area lookup.
            room_ind: Room index for suggested area lookup.
        """
        super().__init__(
            coordinator,
            entity_key=f"opening_{open_act_id}",
            device_name=opening_name,
            device_id=f"opening_{open_act_id}",
            floor_ind=floor_ind,
            room_ind=room_ind,
        )
        self._open_act_id = open_act_id
        self._attr_has_entity_name = False
        self._attr_name = opening_name
        self._attr_device_class = _DEVICE_CLASS_MAP.get(opening_type)
        self._optimistic_is_opening: bool | None = None
        self._optimistic_is_closing: bool | None = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Clear optimistic state when coordinator pushes real data."""
        if (
            self._optimistic_is_opening is not None
            or self._optimistic_is_closing is not None
        ):
            _LOGGER.debug(
                "Coordinator update clearing optimistic state for cover open_act_id=%d"
                " (is_opening=%s, is_closing=%s)",
                self._open_act_id,
                self._optimistic_is_opening,
                self._optimistic_is_closing,
            )
        self._optimistic_is_opening = None
        self._optimistic_is_closing = None
        super()._handle_coordinator_update()

    @property
    def is_closed(self) -> bool | None:
        """Return None because the CAME API does not track position."""
        return None

    @property
    def is_opening(self) -> bool:
        """Return True if the cover motor is currently opening."""
        if self._optimistic_is_opening is not None:
            return self._optimistic_is_opening
        opening = self.coordinator.data.openings.get(self._open_act_id)
        if opening is None:
            return False
        return opening.status == OpeningStatus.OPENING

    @property
    def is_closing(self) -> bool:
        """Return True if the cover motor is currently closing."""
        if self._optimistic_is_closing is not None:
            return self._optimistic_is_closing
        opening = self.coordinator.data.openings.get(self._open_act_id)
        if opening is None:
            return False
        return opening.status == OpeningStatus.CLOSING

    async def _async_set_status(
        self,
        target_status: OpeningStatus,
        action: str,
        is_opening: bool,
        is_closing: bool,
    ) -> None:
        """Send a status command and optimistically update state."""
        opening = self.coordinator.data.openings.get(self._open_act_id)
        if opening is None:
            _LOGGER.warning(
                "Cannot %s cover open_act_id=%d: not found in coordinator data",
                action,
                self._open_act_id,
            )
            return
        await self.coordinator.api.async_set_opening_status(opening, target_status)

        self._optimistic_is_opening = is_opening
        self._optimistic_is_closing = is_closing
        _LOGGER.debug(
            "Optimistic update for cover open_act_id=%d: is_opening=%s, is_closing=%s",
            self._open_act_id,
            is_opening,
            is_closing,
        )
        self.async_write_ha_state()

    async def async_open_cover(self, **kwargs: Any) -> None:
        """Open the cover."""
        await self._async_set_status(
            OpeningStatus.OPENING, "open", is_opening=True, is_closing=False
        )

    async def async_close_cover(self, **kwargs: Any) -> None:
        """Close the cover."""
        await self._async_set_status(
            OpeningStatus.CLOSING, "close", is_opening=False, is_closing=True
        )

    async def async_stop_cover(self, **kwargs: Any) -> None:
        """Stop the cover motor."""
        await self._async_set_status(
            OpeningStatus.STOPPED, "stop", is_opening=False, is_closing=False
        )

    async def async_open_cover_tilt(self, **kwargs: Any) -> None:
        """Open the cover tilt (slat open)."""
        await self._async_set_status(
            OpeningStatus.SLAT_OPEN, "open tilt", is_opening=False, is_closing=False
        )

    async def async_close_cover_tilt(self, **kwargs: Any) -> None:
        """Close the cover tilt (slat close)."""
        await self._async_set_status(
            OpeningStatus.SLAT_CLOSE,
            "close tilt",
            is_opening=False,
            is_closing=False,
        )

    async def async_stop_cover_tilt(self, **kwargs: Any) -> None:
        """Stop the cover tilt."""
        await self._async_set_status(
            OpeningStatus.STOPPED,
            "stop tilt",
            is_opening=False,
            is_closing=False,
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
