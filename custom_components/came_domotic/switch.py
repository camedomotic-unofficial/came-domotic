"""Switch platform for CAME Domotic.

Exposes CAME Domotic relays and timers as Home Assistant switch entities.
Each relay supports simple on/off control. Each timer supports global
enable/disable plus a ``set_timer_timetable`` entity service for scheduling.
"""

from __future__ import annotations

import logging
from typing import Any

from aiocamedomotic.models import RelayStatus
from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import (
    AddEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.event import async_call_later
import voluptuous as vol

from . import CameDomoticConfigEntry
from .coordinator import CameDomoticDataUpdateCoordinator
from .entity import CameDomoticDeviceEntity, CameDomoticEntity

_LOGGER = logging.getLogger(__name__)

_OPTIMISTIC_TIMEOUT = 5.0  # seconds before optimistic state is force-cleared

_DAY_NAMES = [
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
]

_DAY_NAME_TO_INDEX = {name: i for i, name in enumerate(_DAY_NAMES)}

SET_TIMER_TIMETABLE_SCHEMA: vol.Schema = {  # type: ignore[assignment]
    vol.Optional("days"): vol.All(
        cv.ensure_list,
        [vol.In(_DAY_NAMES)],
    ),
    vol.Optional("slots"): vol.All(
        cv.ensure_list,
        vol.Length(min=1, max=4),
        [
            vol.Schema(
                {
                    vol.Required("start"): cv.string,
                    vol.Optional("stop"): cv.string,
                }
            )
        ],
    ),
}


def _parse_time_string(value: str) -> tuple[int, int, int]:
    """Parse a time string (HH:MM or HH:MM:SS) to (hour, min, sec) tuple."""
    parts = value.split(":")
    if len(parts) == 2:  # noqa: PLR2004
        return int(parts[0]), int(parts[1]), 0
    if len(parts) == 3:  # noqa: PLR2004
        return int(parts[0]), int(parts[1]), int(parts[2])
    msg = f"Invalid time format '{value}', expected HH:MM or HH:MM:SS"
    raise vol.Invalid(msg)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch platform."""
    coordinator = entry.runtime_data.coordinator
    relays = coordinator.data.relays
    timers = coordinator.data.timers

    entities: list[SwitchEntity] = [
        CameDomoticRelay(
            coordinator,
            act_id,
            relay.name,
            relay.floor_ind,
            relay.room_ind,
        )
        for act_id, relay in relays.items()
    ]
    entities.extend(
        CameDomoticTimer(coordinator, timer_id, timer.name)
        for timer_id, timer in timers.items()
    )

    _LOGGER.debug(
        "Setting up %d relay switch(es) and %d timer switch(es)",
        len(relays),
        len(timers),
    )
    async_add_entities(entities)

    # Register entity service for timer timetable configuration
    platform = async_get_current_platform()
    platform.async_register_entity_service(
        "set_timer_timetable",
        SET_TIMER_TIMETABLE_SCHEMA,
        "async_set_timer_timetable",
    )


class CameDomoticRelay(CameDomoticDeviceEntity, SwitchEntity):
    """Switch entity for a CAME Domotic relay.

    Supports on/off control. Uses optimistic state updates with a
    timer-based timeout to provide responsive UI feedback while waiting
    for the server to confirm the state change via long-polling.
    """

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        act_id: int,
        relay_name: str,
        floor_ind: int | None = None,
        room_ind: int | None = None,
    ) -> None:
        """Initialize the relay switch entity.

        Args:
            coordinator: The data update coordinator.
            act_id: The actuator ID that identifies this relay.
            relay_name: The display name of the relay.
            floor_ind: Floor index for suggested area lookup.
            room_ind: Room index for suggested area lookup.
        """
        super().__init__(
            coordinator,
            entity_key=f"relay_{act_id}",
            device_name=relay_name,
            device_id=f"relay_{act_id}",
            floor_ind=floor_ind,
            room_ind=room_ind,
        )
        self._act_id = act_id
        self._attr_has_entity_name = False
        self._attr_name = relay_name
        self._optimistic_is_on: bool | None = None
        self._optimistic_snapshot_status: RelayStatus | None = None
        self._optimistic_timeout_cancel: CALLBACK_TYPE | None = None

    @callback
    def _clear_optimistic_state(self, reason: str) -> None:
        """Clear optimistic state and cancel any pending timeout."""
        _LOGGER.debug(
            "Clearing optimistic state for relay act_id=%d (%s)",
            self._act_id,
            reason,
        )
        self._optimistic_is_on = None
        self._optimistic_snapshot_status = None
        if self._optimistic_timeout_cancel is not None:
            self._optimistic_timeout_cancel()
            self._optimistic_timeout_cancel = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Clear optimistic state when coordinator data catches up."""
        if self._optimistic_is_on is not None:
            relay = self.coordinator.data.relays.get(self._act_id)
            data_changed = (
                relay is not None
                and self._optimistic_snapshot_status is not None
                and relay.status != self._optimistic_snapshot_status
            )
            if data_changed or relay is None:
                self._clear_optimistic_state(
                    f"data_changed={data_changed}, relay_missing={relay is None}"
                )
        super()._handle_coordinator_update()

    @property
    def is_on(self) -> bool | None:
        """Return True if the relay is on."""
        if self._optimistic_is_on is not None:
            return self._optimistic_is_on
        relay = self.coordinator.data.relays.get(self._act_id)
        if relay is None or relay.status == RelayStatus.UNKNOWN:
            return None
        return relay.status == RelayStatus.ON

    async def async_will_remove_from_hass(self) -> None:
        """Cancel any pending optimistic timeout on entity removal."""
        if self._optimistic_timeout_cancel is not None:
            self._optimistic_timeout_cancel()
            self._optimistic_timeout_cancel = None
        await super().async_will_remove_from_hass()

    def _schedule_optimistic_timeout(self) -> None:
        """Schedule an active timer to force-clear optimistic state."""
        # Cancel any existing timer (e.g., from a previous rapid command)
        if self._optimistic_timeout_cancel is not None:
            self._optimistic_timeout_cancel()

        @callback
        def _on_timeout(_now: Any) -> None:
            self._optimistic_timeout_cancel = None
            if self._optimistic_is_on is not None:
                self._clear_optimistic_state("timeout")
                self.async_write_ha_state()

        self._optimistic_timeout_cancel = async_call_later(
            self.hass, _OPTIMISTIC_TIMEOUT, _on_timeout
        )

    async def _async_apply_relay_state(
        self, target_status: RelayStatus, optimistic_is_on: bool
    ) -> None:
        """Send a relay command and apply an optimistic state update.

        Args:
            target_status: The RelayStatus to send to the server.
            optimistic_is_on: The optimistic is_on value to display until confirmed.
        """
        relay = self.coordinator.data.relays.get(self._act_id)
        if relay is None:
            _LOGGER.warning(
                "Cannot set relay act_id=%d to %s: not found in coordinator data",
                self._act_id,
                target_status.name,
            )
            return

        # Capture pre-call state so _handle_coordinator_update can detect changes
        pre_call_status = relay.status

        await self.coordinator.api.async_set_relay_status(relay, target_status)

        # Optimistic update after successful API call
        self._optimistic_snapshot_status = pre_call_status
        self._optimistic_is_on = optimistic_is_on
        self._schedule_optimistic_timeout()
        _LOGGER.debug(
            "Optimistic update for relay act_id=%d: is_on=%s",
            self._act_id,
            optimistic_is_on,
        )
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the relay."""
        await self._async_apply_relay_state(RelayStatus.ON, optimistic_is_on=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the relay."""
        await self._async_apply_relay_state(RelayStatus.OFF, optimistic_is_on=False)


class CameDomoticTimer(CameDomoticEntity, SwitchEntity):
    """Switch entity for a CAME Domotic timer.

    Exposes the timer's global enabled/disabled state as an on/off switch.
    Additional scheduling attributes (active days, timetable slots) are
    available via extra_state_attributes. The ``set_timer_timetable`` entity
    service allows configuring the schedule from automations.
    """

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        timer_id: int,
        timer_name: str,
    ) -> None:
        """Initialize the timer switch entity.

        Args:
            coordinator: The data update coordinator.
            timer_id: The timer identifier.
            timer_name: The display name of the timer.
        """
        super().__init__(coordinator, entity_key=f"timer_{timer_id}")
        self._timer_id = timer_id
        self._attr_has_entity_name = False
        self._attr_name = timer_name
        self._optimistic_is_on: bool | None = None
        self._optimistic_snapshot_enabled: bool | None = None
        self._optimistic_timeout_cancel: CALLBACK_TYPE | None = None

    @callback
    def _clear_optimistic_state(self, reason: str) -> None:
        """Clear optimistic state and cancel any pending timeout."""
        _LOGGER.debug(
            "Clearing optimistic state for timer id=%d (%s)",
            self._timer_id,
            reason,
        )
        self._optimistic_is_on = None
        self._optimistic_snapshot_enabled = None
        if self._optimistic_timeout_cancel is not None:
            self._optimistic_timeout_cancel()
            self._optimistic_timeout_cancel = None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Clear optimistic state when coordinator data catches up."""
        if self._optimistic_is_on is not None:
            timer = self.coordinator.data.timers.get(self._timer_id)
            data_changed = (
                timer is not None
                and self._optimistic_snapshot_enabled is not None
                and timer.enabled != self._optimistic_snapshot_enabled
            )
            if data_changed or timer is None:
                self._clear_optimistic_state(
                    f"data_changed={data_changed}, timer_missing={timer is None}"
                )
        super()._handle_coordinator_update()

    @property
    def is_on(self) -> bool | None:
        """Return True if the timer is enabled."""
        if self._optimistic_is_on is not None:
            return self._optimistic_is_on
        timer = self.coordinator.data.timers.get(self._timer_id)
        if timer is None:
            return None
        return timer.enabled

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return timer scheduling attributes."""
        timer = self.coordinator.data.timers.get(self._timer_id)
        if timer is None:
            return None
        timetable = []
        for slot in timer.timetable:
            entry: dict[str, Any] = {
                "start": f"{slot.start_hour:02d}:{slot.start_min:02d}:{slot.start_sec:02d}",
            }
            if slot.stop_hour is not None:
                entry["stop"] = (
                    f"{slot.stop_hour:02d}:{slot.stop_min:02d}:{slot.stop_sec:02d}"
                )
            if slot.active is not None:
                entry["active"] = slot.active
            timetable.append(entry)
        return {
            "days": [d.lower() for d in timer.active_days],
            "timetable": timetable,
            "bars": timer.bars,
        }

    async def async_will_remove_from_hass(self) -> None:
        """Cancel any pending optimistic timeout on entity removal."""
        if self._optimistic_timeout_cancel is not None:
            self._optimistic_timeout_cancel()
            self._optimistic_timeout_cancel = None
        await super().async_will_remove_from_hass()

    def _schedule_optimistic_timeout(self) -> None:
        """Schedule a timeout to force-clear optimistic state."""
        if self._optimistic_timeout_cancel is not None:
            self._optimistic_timeout_cancel()

        @callback
        def _on_timeout(_now: Any) -> None:
            self._optimistic_timeout_cancel = None
            if self._optimistic_is_on is not None:
                self._clear_optimistic_state("timeout")
                self.async_write_ha_state()

        self._optimistic_timeout_cancel = async_call_later(
            self.hass, _OPTIMISTIC_TIMEOUT, _on_timeout
        )

    async def _async_apply_timer_state(self, *, enable: bool) -> None:
        """Send a timer enable/disable command with optimistic update.

        Args:
            enable: True to enable, False to disable.
        """
        timer = self.coordinator.data.timers.get(self._timer_id)
        if timer is None:
            _LOGGER.warning(
                "Cannot %s timer id=%d: not found in coordinator data",
                "enable" if enable else "disable",
                self._timer_id,
            )
            return

        pre_call_enabled = timer.enabled

        if enable:
            await self.coordinator.api.async_enable_timer(timer)
        else:
            await self.coordinator.api.async_disable_timer(timer)

        self._optimistic_snapshot_enabled = pre_call_enabled
        self._optimistic_is_on = enable
        self._schedule_optimistic_timeout()
        _LOGGER.debug(
            "Optimistic update for timer id=%d: is_on=%s",
            self._timer_id,
            enable,
        )
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the timer."""
        await self._async_apply_timer_state(enable=True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the timer."""
        await self._async_apply_timer_state(enable=False)

    async def async_set_timer_timetable(
        self,
        days: list[str] | None = None,
        slots: list[dict[str, str]] | None = None,
    ) -> None:
        """Handle the set_timer_timetable entity service call.

        Args:
            days: Optional list of day names to enable (unlisted days disabled).
            slots: Optional list of slot dicts with "start" and optional "stop".
        """
        timer = self.coordinator.data.timers.get(self._timer_id)
        if timer is None:
            _LOGGER.warning(
                "Cannot set timetable for timer id=%d: not found in coordinator data",
                self._timer_id,
            )
            return

        if days is not None:
            enabled_indices = {_DAY_NAME_TO_INDEX[d] for d in days}
            for day_index in range(7):
                if day_index in enabled_indices:
                    await self.coordinator.api.async_enable_timer_day(timer, day_index)
                else:
                    await self.coordinator.api.async_disable_timer_day(timer, day_index)

        if slots is not None:
            parsed: list[tuple[int, int, int] | None] = [
                _parse_time_string(s["start"]) for s in slots
            ]
            # Pad to exactly 4 entries
            while len(parsed) < 4:  # noqa: PLR2004
                parsed.append(None)
            await self.coordinator.api.async_set_timer_timetable(timer, parsed)
