"""Test CAME Domotic Unofficial coordinator."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, create_autospec, patch

from aiocamedomotic.auth import Auth
from aiocamedomotic.models import ThermoZone
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic_unofficial.api import (
    CameDomoticUnofficialApiClientAuthenticationError,
    CameDomoticUnofficialApiClientCommunicationError,
    CameDomoticUnofficialApiClientError,
)
from custom_components.came_domotic_unofficial.const import (
    DOMAIN,
    SESSION_RECYCLE_THRESHOLD,
)
from custom_components.came_domotic_unofficial.coordinator import (
    CameDomoticUnofficialDataUpdateCoordinator,
)

from .conftest import MOCK_THERMO_ZONES, _mock_server_info
from .const import MOCK_CONFIG

_API_CLIENT = (
    "custom_components.came_domotic_unofficial.api.CameDomoticUnofficialApiClient"
)

_MOCK_AUTH = create_autospec(Auth, instance=True)


def _real_thermo_zone(
    act_id,
    name,
    temperature=20.0,
    set_point=21.0,
    mode=2,
    season="winter",
    status=1,
    antifreeze=50,
    floor_ind=0,
    room_ind=0,
    leaf=0,
):
    """Create a real ThermoZone with the given values (for merge tests)."""
    return ThermoZone(
        raw_data={
            "act_id": act_id,
            "name": name,
            "temp_dec": int(temperature * 10),
            "set_point": int(set_point * 10),
            "mode": mode,
            "season": season,
            "status": status,
            "antifreeze": antifreeze,
            "leaf": leaf,
            "floor_ind": floor_ind,
            "room_ind": room_ind,
        },
        auth=_MOCK_AUTH,
    )


def _real_zone_thermo_zones():
    """Return a list of real ThermoZone objects for testing."""
    return [
        _real_thermo_zone(1, "Living Room", temperature=20.0, set_point=21.0),
        _real_thermo_zone(
            52,
            "Bedroom",
            temperature=19.5,
            set_point=20.0,
            mode=1,
            floor_ind=1,
            room_ind=1,
        ),
    ]


# --- _async_update_data (initial full fetch) ---


async def test_coordinator_update_success(hass, bypass_get_data):
    """Test coordinator fetches data and stores zones from API response."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator
    assert coordinator.data is not None
    assert coordinator.data.server_info.keycode == "AA:BB:CC:DD:EE:FF"
    assert coordinator.data.server_info.swver == "1.2.3"

    zones = coordinator.data.thermo_zones
    assert len(zones) == 2
    assert 1 in zones
    assert zones[1].temperature == 20.0
    assert 52 in zones


async def test_coordinator_auth_error_raises_config_entry_auth_failed(
    hass, bypass_get_data
):
    """Test coordinator raises ConfigEntryAuthFailed on auth error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    with (
        patch.object(
            coordinator.api,
            "async_get_server_info",
            side_effect=CameDomoticUnofficialApiClientAuthenticationError("Bad auth"),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await coordinator._async_update_data()


async def test_coordinator_communication_error_raises_update_failed(
    hass, bypass_get_data
):
    """Test coordinator raises UpdateFailed on communication error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    with (
        patch.object(
            coordinator.api,
            "async_get_server_info",
            side_effect=CameDomoticUnofficialApiClientCommunicationError("Timeout"),
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()


# --- start_long_poll / stop_long_poll ---


async def test_start_and_stop_long_poll(hass):
    """Test long-poll task creation and cancellation."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            return_value=_mock_server_info(),
        ),
        patch(
            f"{_API_CLIENT}.async_get_thermo_zones",
            return_value=list(MOCK_THERMO_ZONES),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch.object(
            CameDomoticUnofficialDataUpdateCoordinator,
            "_async_long_poll_loop",
            new_callable=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = config_entry.runtime_data.coordinator
        # start_long_poll was called during setup, task should exist
        assert coordinator._long_poll_task is not None

        await coordinator.stop_long_poll()
        assert coordinator._long_poll_task is None


async def test_start_long_poll_already_running(hass):
    """Test that starting long-poll when already running logs warning."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            return_value=_mock_server_info(),
        ),
        patch(
            f"{_API_CLIENT}.async_get_thermo_zones",
            return_value=list(MOCK_THERMO_ZONES),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch.object(
            CameDomoticUnofficialDataUpdateCoordinator,
            "_async_long_poll_loop",
            new_callable=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = config_entry.runtime_data.coordinator
        first_task = coordinator._long_poll_task

        # Starting again should not create a second task
        coordinator.start_long_poll()
        assert coordinator._long_poll_task is first_task

        await coordinator.stop_long_poll()


async def test_stop_long_poll_when_not_running(hass, bypass_get_data):
    """Test that stopping long-poll when not running is safe."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator
    # Should not raise
    await coordinator.stop_long_poll()


# --- _async_long_poll_loop ---


async def test_long_poll_loop_incremental_update(hass):
    """Test that incremental updates are merged and pushed to entities."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    real_zones = _real_zone_thermo_zones()

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            return_value=_mock_server_info(),
        ),
        patch(
            f"{_API_CLIENT}.async_get_thermo_zones",
            return_value=real_zones,
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch.object(CameDomoticUnofficialDataUpdateCoordinator, "start_long_poll"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    # Create a mock update for zone 1 with new temperature only
    mock_update = MagicMock()
    mock_update.act_id = 1
    mock_update.name = "Living Room"
    mock_update.raw_data = {"act_id": 1, "temp_dec": 225}

    mock_update_list = MagicMock()
    mock_update_list.has_plant_update = False
    mock_update_list.get_typed_by_device_type.return_value = [mock_update]

    call_count = 0

    async def _fake_get_updates(timeout=120):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_update_list
        # Cancel the loop after first iteration
        raise asyncio.CancelledError

    with (
        patch.object(
            coordinator.api, "async_get_updates", side_effect=_fake_get_updates
        ),
        patch("custom_components.came_domotic_unofficial.coordinator.asyncio.sleep"),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._async_long_poll_loop()

    # Verify the temperature was updated via raw_data merge
    zone = coordinator.data.thermo_zones[1]
    assert zone.temperature == 22.5
    # Other fields should remain unchanged
    assert zone.set_point == 21.0


async def test_long_poll_loop_plant_update_triggers_full_refresh(hass, bypass_get_data):
    """Test that a plant update triggers a full data refresh."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    mock_update_list = MagicMock()
    mock_update_list.has_plant_update = True

    call_count = 0

    async def _fake_get_updates(timeout=120):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_update_list
        raise asyncio.CancelledError

    mock_update_data = AsyncMock(return_value=coordinator.data)
    with (
        patch.object(
            coordinator.api, "async_get_updates", side_effect=_fake_get_updates
        ),
        patch.object(coordinator, "_async_update_data", mock_update_data),
        patch("custom_components.came_domotic_unofficial.coordinator.asyncio.sleep"),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._async_long_poll_loop()

    mock_update_data.assert_awaited_once()


async def test_long_poll_loop_auth_error_triggers_reauth(hass, bypass_get_data):
    """Test that auth error in long-poll loop triggers reauth and exits."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    with (
        patch.object(
            coordinator.api,
            "async_get_updates",
            side_effect=CameDomoticUnofficialApiClientAuthenticationError("Bad auth"),
        ),
        patch.object(config_entry, "async_start_reauth") as mock_reauth,
    ):
        # Should return (not raise) when auth error occurs
        await coordinator._async_long_poll_loop()

    mock_reauth.assert_called_once_with(hass)


async def test_long_poll_loop_comm_error_retries(hass, bypass_get_data):
    """Test that communication errors are retried after delay."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    call_count = 0

    async def _fake_get_updates(timeout=120):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise CameDomoticUnofficialApiClientCommunicationError("Connection lost")
        raise asyncio.CancelledError

    with (
        patch.object(
            coordinator.api, "async_get_updates", side_effect=_fake_get_updates
        ),
        patch(
            "custom_components.came_domotic_unofficial.coordinator.asyncio.sleep"
        ) as mock_sleep,
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._async_long_poll_loop()

    # Should have slept with RECONNECT_DELAY (5s) after the comm error
    mock_sleep.assert_any_call(5)
    assert call_count == 2


async def test_long_poll_loop_generic_error_retries(hass, bypass_get_data):
    """Test that generic API errors are retried after delay."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    call_count = 0

    async def _fake_get_updates(timeout=120):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise CameDomoticUnofficialApiClientError("Generic error")
        raise asyncio.CancelledError

    with (
        patch.object(
            coordinator.api, "async_get_updates", side_effect=_fake_get_updates
        ),
        patch(
            "custom_components.came_domotic_unofficial.coordinator.asyncio.sleep"
        ) as mock_sleep,
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._async_long_poll_loop()

    mock_sleep.assert_any_call(5)
    assert call_count == 2


async def test_long_poll_loop_throttle_between_updates(hass, bypass_get_data):
    """Test that 1s throttle delay is applied between update iterations."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    mock_update_list = MagicMock()
    mock_update_list.has_plant_update = False
    mock_update_list.get_typed_by_device_type.return_value = []

    call_count = 0

    async def _fake_get_updates(timeout=120):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_update_list
        raise asyncio.CancelledError

    with (
        patch.object(
            coordinator.api, "async_get_updates", side_effect=_fake_get_updates
        ),
        patch(
            "custom_components.came_domotic_unofficial.coordinator.asyncio.sleep"
        ) as mock_sleep,
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._async_long_poll_loop()

    # Verify throttle delay (1s) was called after processing the update
    mock_sleep.assert_any_call(1)


async def test_long_poll_loop_plant_update_auth_failure(hass, bypass_get_data):
    """Test that auth failure during plant update full refresh exits the loop."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    mock_update_list = MagicMock()
    mock_update_list.has_plant_update = True

    call_count = 0

    async def _fake_get_updates(timeout=120):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_update_list
        raise asyncio.CancelledError

    with (
        patch.object(
            coordinator.api, "async_get_updates", side_effect=_fake_get_updates
        ),
        patch.object(
            coordinator,
            "_async_update_data",
            side_effect=ConfigEntryAuthFailed("Bad auth"),
        ),
        patch("custom_components.came_domotic_unofficial.coordinator.asyncio.sleep"),
    ):
        # Should return (exit loop) on auth failure, not raise
        await coordinator._async_long_poll_loop()

    # Only one call to get_updates — loop exited after auth failure
    assert call_count == 1


async def test_long_poll_loop_plant_update_refresh_failure(hass, bypass_get_data):
    """Test that UpdateFailed during plant refresh keeps stale data and continues."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    mock_update_list = MagicMock()
    mock_update_list.has_plant_update = True

    call_count = 0

    async def _fake_get_updates(timeout=120):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_update_list
        raise asyncio.CancelledError

    with (
        patch.object(
            coordinator.api, "async_get_updates", side_effect=_fake_get_updates
        ),
        patch.object(
            coordinator,
            "_async_update_data",
            side_effect=UpdateFailed("Comm error"),
        ),
        patch("custom_components.came_domotic_unofficial.coordinator.asyncio.sleep"),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._async_long_poll_loop()

    # Loop continued after the failed refresh (call_count == 2)
    assert call_count == 2


async def test_stop_long_poll_cancels_running_task(hass):
    """Test that stop_long_poll properly cancels a running background task."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    loop_started = asyncio.Event()

    async def _blocking_loop():
        """Simulate a long-running loop that blocks until cancelled."""
        loop_started.set()
        try:
            await asyncio.sleep(3600)  # Will be cancelled
        except asyncio.CancelledError:
            raise

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            return_value=_mock_server_info(),
        ),
        patch(
            f"{_API_CLIENT}.async_get_thermo_zones",
            return_value=list(MOCK_THERMO_ZONES),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch.object(
            CameDomoticUnofficialDataUpdateCoordinator,
            "_async_long_poll_loop",
            side_effect=_blocking_loop,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = config_entry.runtime_data.coordinator
        # Wait for the loop to start
        await asyncio.wait_for(loop_started.wait(), timeout=2)
        assert coordinator._long_poll_task is not None

        await coordinator.stop_long_poll()
        assert coordinator._long_poll_task is None


# --- _merge_updates ---


async def test_merge_updates_known_zone(hass):
    """Test merging an update for a known zone updates its state."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    real_zones = _real_zone_thermo_zones()

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            return_value=_mock_server_info(),
        ),
        patch(
            f"{_API_CLIENT}.async_get_thermo_zones",
            return_value=real_zones,
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch.object(CameDomoticUnofficialDataUpdateCoordinator, "start_long_poll"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    # Create a partial update for zone 1 (only temperature changed)
    mock_update = MagicMock()
    mock_update.act_id = 1
    mock_update.name = "Living Room"
    mock_update.raw_data = {"act_id": 1, "temp_dec": 250}

    mock_update_list = MagicMock()
    mock_update_list.get_typed_by_device_type.return_value = [mock_update]

    coordinator._merge_updates(mock_update_list)

    zone = coordinator.data.thermo_zones[1]
    assert zone.temperature == 25.0
    # Original set_point should be preserved
    assert zone.set_point == 21.0


async def test_merge_updates_unknown_zone_ignored(hass):
    """Test that updates for unknown zones are silently ignored."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    real_zones = _real_zone_thermo_zones()

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            return_value=_mock_server_info(),
        ),
        patch(
            f"{_API_CLIENT}.async_get_thermo_zones",
            return_value=real_zones,
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch.object(CameDomoticUnofficialDataUpdateCoordinator, "start_long_poll"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    mock_update = MagicMock()
    mock_update.act_id = 999  # unknown zone

    mock_update_list = MagicMock()
    mock_update_list.get_typed_by_device_type.return_value = [mock_update]

    coordinator._merge_updates(mock_update_list)

    # All original zones should still be present
    assert len(coordinator.data.thermo_zones) == 2


async def test_merge_updates_preserves_fields_not_in_update(hass):
    """Test that partial updates only overwrite keys present in raw_data."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    real_zones = _real_zone_thermo_zones()

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            return_value=_mock_server_info(),
        ),
        patch(
            f"{_API_CLIENT}.async_get_thermo_zones",
            return_value=real_zones,
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch.object(CameDomoticUnofficialDataUpdateCoordinator, "start_long_poll"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    # Update only contains temp_dec — everything else should be preserved
    mock_update = MagicMock()
    mock_update.act_id = 1
    mock_update.name = "Living Room"
    mock_update.raw_data = {"act_id": 1, "temp_dec": 300}

    mock_update_list = MagicMock()
    mock_update_list.get_typed_by_device_type.return_value = [mock_update]

    coordinator._merge_updates(mock_update_list)
    zone = coordinator.data.thermo_zones[1]

    assert zone.temperature == 30.0
    assert zone.set_point == 21.0  # preserved
    assert zone.antifreeze == 5.0  # preserved
    assert zone.name == "Living Room"  # preserved
    assert zone.floor_ind == 0  # preserved


# --- Session recycling (cseq reset) ---


async def test_session_recycle_after_threshold(hass, bypass_get_data):
    """Test that session is recycled after reaching the long-poll threshold."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator
    coordinator._long_poll_count = SESSION_RECYCLE_THRESHOLD

    mock_update_list = MagicMock()
    mock_update_list.has_plant_update = False
    mock_update_list.get_typed_by_device_type.return_value = []

    call_count = 0

    async def _fake_get_updates(timeout=120):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_update_list
        raise asyncio.CancelledError

    with (
        patch.object(
            coordinator.api, "async_get_updates", side_effect=_fake_get_updates
        ),
        patch.object(
            coordinator.api, "async_dispose", new_callable=AsyncMock
        ) as mock_dispose,
        patch.object(
            coordinator.api, "async_connect", new_callable=AsyncMock
        ) as mock_connect,
        patch.object(
            coordinator,
            "_async_update_data",
            new_callable=AsyncMock,
            return_value=coordinator.data,
        ) as mock_update_data,
        patch("custom_components.came_domotic_unofficial.coordinator.asyncio.sleep"),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._async_long_poll_loop()

    mock_dispose.assert_awaited_once()
    mock_connect.assert_awaited_once()
    mock_update_data.assert_awaited_once()
    # Counter was reset to 0 by recycle, then incremented by the successful call
    assert coordinator._long_poll_count == 1


async def test_session_recycle_auth_error_triggers_reauth(hass, bypass_get_data):
    """Test that auth error during session recycle triggers reauth and exits."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator
    coordinator._long_poll_count = SESSION_RECYCLE_THRESHOLD

    with (
        patch.object(coordinator.api, "async_dispose", new_callable=AsyncMock),
        patch.object(
            coordinator.api,
            "async_connect",
            side_effect=CameDomoticUnofficialApiClientAuthenticationError("Bad auth"),
        ),
        patch.object(config_entry, "async_start_reauth") as mock_reauth,
    ):
        # Should return (not raise) when auth error occurs
        await coordinator._async_long_poll_loop()

    mock_reauth.assert_called_once_with(hass)


async def test_session_recycle_comm_error_retries(hass, bypass_get_data):
    """Test that comm error during session recycle retries after delay."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator
    coordinator._long_poll_count = SESSION_RECYCLE_THRESHOLD

    connect_call_count = 0

    async def _fake_connect():
        nonlocal connect_call_count
        connect_call_count += 1
        if connect_call_count == 1:
            raise CameDomoticUnofficialApiClientCommunicationError("Connection lost")
        # Second call succeeds

    mock_update_list = MagicMock()
    mock_update_list.has_plant_update = False
    mock_update_list.get_typed_by_device_type.return_value = []

    updates_call_count = 0

    async def _fake_get_updates(timeout=120):
        nonlocal updates_call_count
        updates_call_count += 1
        if updates_call_count == 1:
            return mock_update_list
        raise asyncio.CancelledError

    with (
        patch.object(coordinator.api, "async_dispose", new_callable=AsyncMock),
        patch.object(coordinator.api, "async_connect", side_effect=_fake_connect),
        patch.object(
            coordinator,
            "_async_update_data",
            new_callable=AsyncMock,
            return_value=coordinator.data,
        ),
        patch.object(
            coordinator.api, "async_get_updates", side_effect=_fake_get_updates
        ),
        patch(
            "custom_components.came_domotic_unofficial.coordinator.asyncio.sleep"
        ) as mock_sleep,
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._async_long_poll_loop()

    # First recycle attempt failed, slept RECONNECT_DELAY, second succeeded
    mock_sleep.assert_any_call(5)
    assert connect_call_count == 2


async def test_no_recycle_below_threshold(hass, bypass_get_data):
    """Test that no recycling occurs when count is below threshold."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator
    coordinator._long_poll_count = SESSION_RECYCLE_THRESHOLD - 2

    mock_update_list = MagicMock()
    mock_update_list.has_plant_update = False
    mock_update_list.get_typed_by_device_type.return_value = []

    call_count = 0

    async def _fake_get_updates(timeout=120):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_update_list
        raise asyncio.CancelledError

    with (
        patch.object(
            coordinator.api, "async_get_updates", side_effect=_fake_get_updates
        ),
        patch.object(
            coordinator.api, "async_dispose", new_callable=AsyncMock
        ) as mock_dispose,
        patch("custom_components.came_domotic_unofficial.coordinator.asyncio.sleep"),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._async_long_poll_loop()

    mock_dispose.assert_not_called()
    # Count incremented by 1 successful call, still below threshold
    assert coordinator._long_poll_count == SESSION_RECYCLE_THRESHOLD - 1


async def test_long_poll_count_only_increments_on_success(hass, bypass_get_data):
    """Test that long-poll count only increments on successful calls."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    mock_update_list = MagicMock()
    mock_update_list.has_plant_update = False
    mock_update_list.get_typed_by_device_type.return_value = []

    call_count = 0

    async def _fake_get_updates(timeout=120):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise CameDomoticUnofficialApiClientCommunicationError("Connection lost")
        if call_count == 2:
            return mock_update_list
        raise asyncio.CancelledError

    with (
        patch.object(
            coordinator.api, "async_get_updates", side_effect=_fake_get_updates
        ),
        patch("custom_components.came_domotic_unofficial.coordinator.asyncio.sleep"),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._async_long_poll_loop()

    # Only the successful call (call 2) incremented the counter
    assert coordinator._long_poll_count == 1


async def test_plant_update_does_not_reset_long_poll_count(hass, bypass_get_data):
    """Test that a plant update does NOT reset the long-poll count.

    Only session recycling resets the counter, because a plant update
    does not clear the cseq on the remote server.
    """
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator
    coordinator._long_poll_count = 500

    mock_update_list = MagicMock()
    mock_update_list.has_plant_update = True

    call_count = 0

    async def _fake_get_updates(timeout=120):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return mock_update_list
        raise asyncio.CancelledError

    with (
        patch.object(
            coordinator.api, "async_get_updates", side_effect=_fake_get_updates
        ),
        patch.object(
            coordinator,
            "_async_update_data",
            new_callable=AsyncMock,
            return_value=coordinator.data,
        ),
        patch("custom_components.came_domotic_unofficial.coordinator.asyncio.sleep"),
        pytest.raises(asyncio.CancelledError),
    ):
        await coordinator._async_long_poll_loop()

    # Counter was incremented (not reset) — only recycle resets it
    assert coordinator._long_poll_count == 501
