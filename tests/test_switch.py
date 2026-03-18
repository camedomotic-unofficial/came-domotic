"""Test CAME Domotic switch platform (relays and timers)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiocamedomotic.models import RelayStatus
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.came_domotic.api import (
    CameDomoticApiClientCommunicationError,
)
from custom_components.came_domotic.const import DOMAIN
from custom_components.came_domotic.models import CameDomoticServerData

from .conftest import (
    _mock_relay,
    _mock_server_info,
    _mock_timer,
    _mock_timer_time_slot,
    _mock_topology,
)
from .const import MOCK_CONFIG

_API_CLIENT = "custom_components.came_domotic.api.CameDomoticApiClient"

_COORDINATOR = (
    "custom_components.came_domotic.coordinator.CameDomoticDataUpdateCoordinator"
)


async def _setup_entry(hass, mock_relays, mock_timers=None):
    """Set up a config entry with the given mock relays and timers."""
    if mock_timers is None:
        mock_timers = []
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            return_value=_mock_server_info(),
        ),
        patch(f"{_API_CLIENT}.async_get_thermo_zones", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_scenarios", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_openings", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_lights", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_digital_inputs", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_analog_sensors", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_analog_inputs", return_value=[]),
        patch(
            f"{_API_CLIENT}.async_get_relays",
            return_value=mock_relays,
        ),
        patch(
            f"{_API_CLIENT}.async_get_timers",
            return_value=mock_timers,
        ),
        patch(
            f"{_API_CLIENT}.async_get_topology",
            return_value=_mock_topology(),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch(f"{_COORDINATOR}.start_long_poll"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


# =============================================================================
# Relay entity tests
# =============================================================================


# --- Entity creation ---


async def test_relay_entities_created(hass, bypass_get_data):
    """Test that switch entities are created per relay and timer."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "switch"
    ]
    # 2 relays + 2 timers = 4
    assert len(entries) == 4


async def test_relay_unique_id(hass, bypass_get_data):
    """Test relay unique IDs follow the expected pattern."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "switch"
    }
    assert unique_ids == {
        "test_relay_600",
        "test_relay_601",
        "test_timer_900",
        "test_timer_901",
    }


async def test_relay_state(hass, bypass_get_data):
    """Test relay entities exist with expected entity IDs."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    pump = hass.states.get("switch.pump_control")
    assert pump is not None

    heating = hass.states.get("switch.heating_relay")
    assert heating is not None


async def test_no_relays(hass):
    """Test no switch entities created when there are no relays or timers."""
    config_entry = await _setup_entry(hass, [])

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "switch"
    ]
    assert len(entries) == 0


# --- State properties ---


async def test_relay_is_on(hass):
    """Test is_on returns True when status is ON."""
    relays = [
        _mock_relay(600, "Pump Control", status=RelayStatus.ON),
    ]
    await _setup_entry(hass, relays)

    state = hass.states.get("switch.pump_control")
    assert state is not None
    assert state.state == "on"


async def test_relay_is_off(hass):
    """Test is_on returns False when status is OFF."""
    relays = [
        _mock_relay(600, "Pump Control", status=RelayStatus.OFF),
    ]
    await _setup_entry(hass, relays)

    state = hass.states.get("switch.pump_control")
    assert state is not None
    assert state.state == "off"


async def test_relay_unknown_status(hass):
    """Test is_on returns None when status is UNKNOWN."""
    relays = [
        _mock_relay(600, "Pump Control", status=RelayStatus.UNKNOWN),
    ]
    await _setup_entry(hass, relays)

    state = hass.states.get("switch.pump_control")
    assert state is not None
    assert state.state == "unknown"


async def test_relay_is_on_not_found(hass):
    """Test is_on returns None when relay disappears from data."""
    relays = [_mock_relay(600, "Pump Control")]
    config_entry = await _setup_entry(hass, relays)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.relays.clear()

    empty_data = CameDomoticServerData(
        server_info=_mock_server_info(),
    )
    with patch.object(
        coordinator,
        "_async_update_data",
        return_value=empty_data,
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("switch.pump_control")
    assert state is not None


# --- Relay actions ---


async def test_relay_turn_on(hass):
    """Test turning on a relay calls async_set_relay_status with ON."""
    relays = [_mock_relay(600, "Pump Control")]
    config_entry = await _setup_entry(hass, relays)

    coordinator = config_entry.runtime_data.coordinator
    mock_set_status = AsyncMock()

    with patch.object(coordinator.api, "async_set_relay_status", mock_set_status):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.pump_control"},
            blocking=True,
        )

    mock_set_status.assert_awaited_once()
    called_relay = mock_set_status.call_args[0][0]
    called_status = mock_set_status.call_args[0][1]
    assert called_relay.act_id == 600
    assert called_status == RelayStatus.ON


async def test_relay_turn_off(hass):
    """Test turning off a relay calls async_set_relay_status with OFF."""
    relays = [_mock_relay(600, "Pump Control", status=RelayStatus.ON)]
    config_entry = await _setup_entry(hass, relays)

    coordinator = config_entry.runtime_data.coordinator
    mock_set_status = AsyncMock()

    with patch.object(coordinator.api, "async_set_relay_status", mock_set_status):
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.pump_control"},
            blocking=True,
        )

    mock_set_status.assert_awaited_once()
    called_status = mock_set_status.call_args[0][1]
    assert called_status == RelayStatus.OFF


# --- Not-found edge cases ---


async def test_relay_turn_on_not_found(hass):
    """Test turning on a relay when it disappears does not raise."""
    relays = [_mock_relay(600, "Pump Control")]
    config_entry = await _setup_entry(hass, relays)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.relays.clear()

    # Should not raise — just logs a warning
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.pump_control"},
        blocking=True,
    )


async def test_relay_turn_off_not_found(hass):
    """Test turning off a relay when it disappears does not raise."""
    relays = [_mock_relay(600, "Pump Control", status=RelayStatus.ON)]
    config_entry = await _setup_entry(hass, relays)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.relays.clear()

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.pump_control"},
        blocking=True,
    )


# --- Optimistic state updates ---


class TestRelayOptimisticState:
    """Tests for optimistic state update behaviour on relays."""

    async def test_relay_turn_on_optimistic_state(self, hass):
        """Test state shows 'on' immediately after successful turn_on."""
        relays = [_mock_relay(600, "Pump Control", status=RelayStatus.OFF)]
        config_entry = await _setup_entry(hass, relays)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_set_relay_status", AsyncMock()):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.pump_control"},
                blocking=True,
            )

        state = hass.states.get("switch.pump_control")
        assert state is not None
        assert state.state == "on"

    async def test_relay_turn_off_optimistic_state(self, hass):
        """Test state shows 'off' immediately after successful turn_off."""
        relays = [_mock_relay(600, "Pump Control", status=RelayStatus.ON)]
        config_entry = await _setup_entry(hass, relays)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_set_relay_status", AsyncMock()):
            await hass.services.async_call(
                "switch",
                "turn_off",
                {"entity_id": "switch.pump_control"},
                blocking=True,
            )

        state = hass.states.get("switch.pump_control")
        assert state is not None
        assert state.state == "off"

    async def test_relay_optimistic_cleared_on_coordinator_update(self, hass):
        """Test optimistic state is cleared when coordinator data catches up."""
        relays = [_mock_relay(600, "Pump Control", status=RelayStatus.OFF)]
        config_entry = await _setup_entry(hass, relays)

        coordinator = config_entry.runtime_data.coordinator

        # Set optimistic state
        with patch.object(coordinator.api, "async_set_relay_status", AsyncMock()):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.pump_control"},
                blocking=True,
            )

        state = hass.states.get("switch.pump_control")
        assert state.state == "on"

        # Simulate server catching up: relay status changes to ON
        coordinator.data.relays[600].status = RelayStatus.ON
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

        # State still "on" from real data, but optimistic is cleared
        state = hass.states.get("switch.pump_control")
        assert state.state == "on"

        # Push relay back to OFF to prove optimistic was truly cleared
        coordinator.data.relays[600].status = RelayStatus.OFF
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

        state = hass.states.get("switch.pump_control")
        assert state.state == "off"

    async def test_relay_optimistic_preserved_when_data_unchanged(self, hass):
        """Test optimistic state persists when coordinator data hasn't caught up."""
        relays = [_mock_relay(600, "Pump Control", status=RelayStatus.OFF)]
        config_entry = await _setup_entry(hass, relays)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_set_relay_status", AsyncMock()):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.pump_control"},
                blocking=True,
            )

        # Status unchanged (still OFF) — push update
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

        # Optimistic state should still show "on"
        state = hass.states.get("switch.pump_control")
        assert state.state == "on"

    async def test_relay_turn_on_api_error_no_optimistic(self, hass):
        """Test no optimistic update when API call fails."""
        relays = [_mock_relay(600, "Pump Control", status=RelayStatus.OFF)]
        config_entry = await _setup_entry(hass, relays)

        coordinator = config_entry.runtime_data.coordinator
        mock_set_status = AsyncMock(
            side_effect=CameDomoticApiClientCommunicationError("fail"),
        )

        with (
            patch.object(coordinator.api, "async_set_relay_status", mock_set_status),
            pytest.raises(CameDomoticApiClientCommunicationError),
        ):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.pump_control"},
                blocking=True,
            )

        state = hass.states.get("switch.pump_control")
        assert state is not None
        assert state.state == "off"

    async def test_relay_turn_off_api_error_no_optimistic(self, hass):
        """Test no optimistic update when API call fails on turn_off."""
        relays = [_mock_relay(600, "Pump Control", status=RelayStatus.ON)]
        config_entry = await _setup_entry(hass, relays)

        coordinator = config_entry.runtime_data.coordinator
        mock_set_status = AsyncMock(
            side_effect=CameDomoticApiClientCommunicationError("fail"),
        )

        with (
            patch.object(coordinator.api, "async_set_relay_status", mock_set_status),
            pytest.raises(CameDomoticApiClientCommunicationError),
        ):
            await hass.services.async_call(
                "switch",
                "turn_off",
                {"entity_id": "switch.pump_control"},
                blocking=True,
            )

        state = hass.states.get("switch.pump_control")
        assert state is not None
        assert state.state == "on"

    async def test_relay_optimistic_timeout_resets_on_rapid_commands(self, hass):
        """Test rapid on/off cancels the first timer and starts a new one."""
        relays = [_mock_relay(600, "Pump Control", status=RelayStatus.OFF)]
        config_entry = await _setup_entry(hass, relays)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_set_relay_status", AsyncMock()):
            # First command: turn on
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.pump_control"},
                blocking=True,
            )
            # Second command: turn off (cancels first timer, starts new one)
            await hass.services.async_call(
                "switch",
                "turn_off",
                {"entity_id": "switch.pump_control"},
                blocking=True,
            )

        state = hass.states.get("switch.pump_control")
        assert state.state == "off"

        # Advance past timeout — timer from turn_off fires
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=8))
        await hass.async_block_till_done()

        # Optimistic cleared; entity reads coordinator data (OFF, since
        # the mock API didn't actually mutate the relay object)
        state = hass.states.get("switch.pump_control")
        assert state.state == "off"

    async def test_relay_optimistic_timeout_clears_state(self, hass):
        """Test optimistic state is force-cleared after timeout.

        Verifies the active timer fires even without coordinator updates,
        preventing stale optimistic state from persisting indefinitely.
        """
        relays = [_mock_relay(600, "Pump Control", status=RelayStatus.OFF)]
        config_entry = await _setup_entry(hass, relays)

        coordinator = config_entry.runtime_data.coordinator

        # Turn on optimistically (underlying data stays OFF)
        with patch.object(coordinator.api, "async_set_relay_status", AsyncMock()):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.pump_control"},
                blocking=True,
            )

        state = hass.states.get("switch.pump_control")
        assert state.state == "on"

        # Advance time past the optimistic timeout (7 seconds)
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=8))
        await hass.async_block_till_done()

        # Optimistic state cleared; entity reads coordinator data (OFF)
        state = hass.states.get("switch.pump_control")
        assert state.state == "off"

    async def test_relay_optimistic_timeout_cancelled_on_removal(self, hass):
        """Test pending optimistic timeout is cancelled when entity is removed."""
        relays = [_mock_relay(600, "Pump Control", status=RelayStatus.OFF)]
        config_entry = await _setup_entry(hass, relays)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_set_relay_status", AsyncMock()):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.pump_control"},
                blocking=True,
            )

        # Unload the entry (triggers async_will_remove_from_hass)
        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        # Advance time past the timeout — should not raise or write state
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=8))
        await hass.async_block_till_done()

    async def test_relay_optimistic_cleared_when_relay_disappears(self, hass):
        """Test optimistic state cleared when relay disappears during update."""
        relays = [_mock_relay(600, "Pump Control", status=RelayStatus.OFF)]
        config_entry = await _setup_entry(hass, relays)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_set_relay_status", AsyncMock()):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.pump_control"},
                blocking=True,
            )

        state = hass.states.get("switch.pump_control")
        assert state.state == "on"

        # Relay disappears from coordinator data
        empty_data = CameDomoticServerData(
            server_info=_mock_server_info(),
        )
        with patch.object(
            coordinator,
            "_async_update_data",
            return_value=empty_data,
        ):
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        # Optimistic state should be cleared
        state = hass.states.get("switch.pump_control")
        assert state is not None


# =============================================================================
# Timer entity tests
# =============================================================================


async def test_timer_entities_created(hass):
    """Test that timer switch entities are created."""
    timers = [
        _mock_timer(900, "Morning Timer"),
        _mock_timer(901, "Weekend Timer", enabled=False),
    ]
    config_entry = await _setup_entry(hass, [], mock_timers=timers)

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "switch"
    ]
    assert len(entries) == 2


async def test_timer_unique_id(hass):
    """Test timer unique IDs follow the expected pattern."""
    timers = [_mock_timer(900, "Morning Timer")]
    config_entry = await _setup_entry(hass, [], mock_timers=timers)

    registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "switch"
    }
    assert unique_ids == {"test_timer_900"}


async def test_timer_is_on(hass):
    """Test is_on returns True when timer is enabled."""
    timers = [_mock_timer(900, "Morning Timer", enabled=True)]
    await _setup_entry(hass, [], mock_timers=timers)

    state = hass.states.get("switch.morning_timer")
    assert state is not None
    assert state.state == "on"


async def test_timer_is_off(hass):
    """Test is_on returns False when timer is disabled."""
    timers = [_mock_timer(900, "Morning Timer", enabled=False)]
    await _setup_entry(hass, [], mock_timers=timers)

    state = hass.states.get("switch.morning_timer")
    assert state is not None
    assert state.state == "off"


async def test_timer_is_on_not_found(hass):
    """Test is_on returns None when timer disappears from data."""
    timers = [_mock_timer(900, "Morning Timer")]
    config_entry = await _setup_entry(hass, [], mock_timers=timers)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.timers.clear()

    empty_data = CameDomoticServerData(server_info=_mock_server_info())
    with patch.object(coordinator, "_async_update_data", return_value=empty_data):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("switch.morning_timer")
    assert state is not None


async def test_timer_extra_attributes(hass):
    """Test extra_state_attributes exposes days, timetable, and bars."""
    timetable = [
        _mock_timer_time_slot(0, 8, 0, 0, 12, 0, 0, active=True),
        _mock_timer_time_slot(1, 14, 30, 0, None, None, None, active=None),
    ]
    timers = [
        _mock_timer(
            900,
            "Morning Timer",
            days=0b0000101,
            bars=2,
            timetable=timetable,
            active_days=["Monday", "Wednesday"],
        )
    ]
    await _setup_entry(hass, [], mock_timers=timers)

    state = hass.states.get("switch.morning_timer")
    assert state is not None
    assert state.attributes["days"] == ["monday", "wednesday"]
    assert state.attributes["bars"] == 2
    tt = state.attributes["timetable"]
    assert len(tt) == 2
    assert tt[0]["start"] == "08:00:00"
    assert tt[0]["stop"] == "12:00:00"
    assert tt[0]["active"] is True
    assert tt[1]["start"] == "14:30:00"
    assert "stop" not in tt[1]
    assert "active" not in tt[1]


async def test_timer_extra_attributes_not_found(hass):
    """Test extra_state_attributes returns None when timer disappears."""
    timers = [_mock_timer(900, "Morning Timer")]
    config_entry = await _setup_entry(hass, [], mock_timers=timers)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.timers.clear()

    empty_data = CameDomoticServerData(server_info=_mock_server_info())
    with patch.object(coordinator, "_async_update_data", return_value=empty_data):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("switch.morning_timer")
    assert state is not None


# --- Timer actions ---


async def test_timer_turn_on(hass):
    """Test turning on a timer calls async_enable_timer."""
    timers = [_mock_timer(900, "Morning Timer", enabled=False)]
    config_entry = await _setup_entry(hass, [], mock_timers=timers)

    coordinator = config_entry.runtime_data.coordinator
    mock_enable = AsyncMock()

    with patch.object(coordinator.api, "async_enable_timer", mock_enable):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.morning_timer"},
            blocking=True,
        )

    mock_enable.assert_awaited_once()
    called_timer = mock_enable.call_args[0][0]
    assert called_timer.id == 900


async def test_timer_turn_off(hass):
    """Test turning off a timer calls async_disable_timer."""
    timers = [_mock_timer(900, "Morning Timer", enabled=True)]
    config_entry = await _setup_entry(hass, [], mock_timers=timers)

    coordinator = config_entry.runtime_data.coordinator
    mock_disable = AsyncMock()

    with patch.object(coordinator.api, "async_disable_timer", mock_disable):
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.morning_timer"},
            blocking=True,
        )

    mock_disable.assert_awaited_once()
    called_timer = mock_disable.call_args[0][0]
    assert called_timer.id == 900


async def test_timer_turn_on_not_found(hass):
    """Test turning on a timer when it disappears does not raise."""
    timers = [_mock_timer(900, "Morning Timer", enabled=False)]
    config_entry = await _setup_entry(hass, [], mock_timers=timers)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.timers.clear()

    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.morning_timer"},
        blocking=True,
    )


async def test_timer_turn_off_not_found(hass):
    """Test turning off a timer when it disappears does not raise."""
    timers = [_mock_timer(900, "Morning Timer", enabled=True)]
    config_entry = await _setup_entry(hass, [], mock_timers=timers)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.timers.clear()

    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.morning_timer"},
        blocking=True,
    )


# --- Timer optimistic state ---


class TestTimerOptimisticState:
    """Tests for optimistic state update behaviour on timers."""

    async def test_timer_turn_on_optimistic_state(self, hass):
        """Test state shows 'on' immediately after successful turn_on."""
        timers = [_mock_timer(900, "Morning Timer", enabled=False)]
        config_entry = await _setup_entry(hass, [], mock_timers=timers)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_enable_timer", AsyncMock()):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.morning_timer"},
                blocking=True,
            )

        state = hass.states.get("switch.morning_timer")
        assert state is not None
        assert state.state == "on"

    async def test_timer_turn_off_optimistic_state(self, hass):
        """Test state shows 'off' immediately after successful turn_off."""
        timers = [_mock_timer(900, "Morning Timer", enabled=True)]
        config_entry = await _setup_entry(hass, [], mock_timers=timers)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_disable_timer", AsyncMock()):
            await hass.services.async_call(
                "switch",
                "turn_off",
                {"entity_id": "switch.morning_timer"},
                blocking=True,
            )

        state = hass.states.get("switch.morning_timer")
        assert state is not None
        assert state.state == "off"

    async def test_timer_optimistic_cleared_on_coordinator_update(self, hass):
        """Test optimistic state cleared when coordinator data catches up."""
        timers = [_mock_timer(900, "Morning Timer", enabled=False)]
        config_entry = await _setup_entry(hass, [], mock_timers=timers)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_enable_timer", AsyncMock()):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.morning_timer"},
                blocking=True,
            )

        state = hass.states.get("switch.morning_timer")
        assert state.state == "on"

        # Server catches up: enabled changes to True
        coordinator.data.timers[900].enabled = True
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

        # Push back to disabled to prove optimistic was cleared
        coordinator.data.timers[900].enabled = False
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

        state = hass.states.get("switch.morning_timer")
        assert state.state == "off"

    async def test_timer_optimistic_preserved_when_data_unchanged(self, hass):
        """Test optimistic state persists when coordinator hasn't caught up."""
        timers = [_mock_timer(900, "Morning Timer", enabled=False)]
        config_entry = await _setup_entry(hass, [], mock_timers=timers)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_enable_timer", AsyncMock()):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.morning_timer"},
                blocking=True,
            )

        # Data unchanged (still disabled) — push update
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

        state = hass.states.get("switch.morning_timer")
        assert state.state == "on"

    async def test_timer_optimistic_timeout_clears_state(self, hass):
        """Test optimistic state is force-cleared after timeout."""
        timers = [_mock_timer(900, "Morning Timer", enabled=False)]
        config_entry = await _setup_entry(hass, [], mock_timers=timers)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_enable_timer", AsyncMock()):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.morning_timer"},
                blocking=True,
            )

        state = hass.states.get("switch.morning_timer")
        assert state.state == "on"

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=8))
        await hass.async_block_till_done()

        state = hass.states.get("switch.morning_timer")
        assert state.state == "off"

    async def test_timer_optimistic_timeout_cancelled_on_removal(self, hass):
        """Test pending optimistic timeout is cancelled when entity is removed."""
        timers = [_mock_timer(900, "Morning Timer", enabled=False)]
        config_entry = await _setup_entry(hass, [], mock_timers=timers)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_enable_timer", AsyncMock()):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.morning_timer"},
                blocking=True,
            )

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=8))
        await hass.async_block_till_done()

    async def test_timer_optimistic_cleared_when_timer_disappears(self, hass):
        """Test optimistic state cleared when timer disappears during update."""
        timers = [_mock_timer(900, "Morning Timer", enabled=False)]
        config_entry = await _setup_entry(hass, [], mock_timers=timers)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_enable_timer", AsyncMock()):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.morning_timer"},
                blocking=True,
            )

        state = hass.states.get("switch.morning_timer")
        assert state.state == "on"

        empty_data = CameDomoticServerData(server_info=_mock_server_info())
        with patch.object(coordinator, "_async_update_data", return_value=empty_data):
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        state = hass.states.get("switch.morning_timer")
        assert state is not None

    async def test_timer_turn_on_api_error_no_optimistic(self, hass):
        """Test no optimistic update when API call fails."""
        timers = [_mock_timer(900, "Morning Timer", enabled=False)]
        config_entry = await _setup_entry(hass, [], mock_timers=timers)

        coordinator = config_entry.runtime_data.coordinator

        with (
            patch.object(
                coordinator.api,
                "async_enable_timer",
                AsyncMock(side_effect=CameDomoticApiClientCommunicationError("fail")),
            ),
            pytest.raises(CameDomoticApiClientCommunicationError),
        ):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.morning_timer"},
                blocking=True,
            )

        state = hass.states.get("switch.morning_timer")
        assert state is not None
        assert state.state == "off"


# =============================================================================
# set_timer_timetable entity service tests
# =============================================================================


async def test_set_timer_timetable_days_only(hass):
    """Test setting only days via the entity service."""
    timers = [_mock_timer(900, "Morning Timer")]
    config_entry = await _setup_entry(hass, [], mock_timers=timers)

    coordinator = config_entry.runtime_data.coordinator
    mock_enable_day = AsyncMock()
    mock_disable_day = AsyncMock()

    with (
        patch.object(coordinator.api, "async_enable_timer_day", mock_enable_day),
        patch.object(coordinator.api, "async_disable_timer_day", mock_disable_day),
    ):
        await hass.services.async_call(
            DOMAIN,
            "set_timer_timetable",
            {
                "entity_id": "switch.morning_timer",
                "days": ["monday", "friday"],
            },
            blocking=True,
        )

    # Monday (0) and Friday (4) enabled, rest disabled
    enabled_days = {c.args[1] for c in mock_enable_day.call_args_list}
    disabled_days = {c.args[1] for c in mock_disable_day.call_args_list}
    assert enabled_days == {0, 4}
    assert disabled_days == {1, 2, 3, 5, 6}


async def test_set_timer_timetable_slots_only(hass):
    """Test setting only slots via the entity service."""
    timers = [_mock_timer(900, "Morning Timer")]
    config_entry = await _setup_entry(hass, [], mock_timers=timers)

    coordinator = config_entry.runtime_data.coordinator
    mock_set_tt = AsyncMock()

    with patch.object(coordinator.api, "async_set_timer_timetable", mock_set_tt):
        await hass.services.async_call(
            DOMAIN,
            "set_timer_timetable",
            {
                "entity_id": "switch.morning_timer",
                "slots": [
                    {"start": "08:00"},
                    {"start": "14:30:15", "stop": "18:00"},
                ],
            },
            blocking=True,
        )

    mock_set_tt.assert_awaited_once()
    called_slots = mock_set_tt.call_args[0][1]
    assert len(called_slots) == 4
    assert called_slots[0] == (8, 0, 0)
    assert called_slots[1] == (14, 30, 15)
    assert called_slots[2] is None
    assert called_slots[3] is None


async def test_set_timer_timetable_both(hass):
    """Test setting both days and slots via the entity service."""
    timers = [_mock_timer(900, "Morning Timer")]
    config_entry = await _setup_entry(hass, [], mock_timers=timers)

    coordinator = config_entry.runtime_data.coordinator
    mock_enable_day = AsyncMock()
    mock_disable_day = AsyncMock()
    mock_set_tt = AsyncMock()

    with (
        patch.object(coordinator.api, "async_enable_timer_day", mock_enable_day),
        patch.object(coordinator.api, "async_disable_timer_day", mock_disable_day),
        patch.object(coordinator.api, "async_set_timer_timetable", mock_set_tt),
    ):
        await hass.services.async_call(
            DOMAIN,
            "set_timer_timetable",
            {
                "entity_id": "switch.morning_timer",
                "days": ["saturday", "sunday"],
                "slots": [{"start": "09:00", "stop": "13:00"}],
            },
            blocking=True,
        )

    # Days set
    enabled_days = {c.args[1] for c in mock_enable_day.call_args_list}
    assert enabled_days == {5, 6}

    # Slots set
    mock_set_tt.assert_awaited_once()
    called_slots = mock_set_tt.call_args[0][1]
    assert called_slots[0] == (9, 0, 0)
    assert called_slots[1] is None
    assert called_slots[2] is None
    assert called_slots[3] is None


async def test_set_timer_timetable_invalid_time_format(hass):
    """Test that an invalid time format raises vol.Invalid via the schema."""
    import voluptuous as vol

    from custom_components.came_domotic.switch import _parse_time_string

    with pytest.raises(vol.Invalid, match="Invalid time format"):
        _parse_time_string("08")


async def test_timer_optimistic_timeout_resets_on_rapid_commands(hass):
    """Test rapid on/off cancels the first optimistic timer and starts a new one."""
    timers = [_mock_timer(900, "Morning Timer", enabled=False)]
    config_entry = await _setup_entry(hass, [], mock_timers=timers)

    coordinator = config_entry.runtime_data.coordinator

    with (
        patch.object(coordinator.api, "async_enable_timer", AsyncMock()),
        patch.object(coordinator.api, "async_disable_timer", AsyncMock()),
    ):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.morning_timer"},
            blocking=True,
        )
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.morning_timer"},
            blocking=True,
        )

    state = hass.states.get("switch.morning_timer")
    assert state.state == "off"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=8))
    await hass.async_block_till_done()

    state = hass.states.get("switch.morning_timer")
    assert state.state == "off"


async def test_set_timer_timetable_not_found(hass):
    """Test set_timer_timetable when timer disappears does not raise."""
    timers = [_mock_timer(900, "Morning Timer")]
    config_entry = await _setup_entry(hass, [], mock_timers=timers)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.timers.clear()

    # Should not raise — just logs a warning
    await hass.services.async_call(
        DOMAIN,
        "set_timer_timetable",
        {
            "entity_id": "switch.morning_timer",
            "days": ["monday"],
        },
        blocking=True,
    )
