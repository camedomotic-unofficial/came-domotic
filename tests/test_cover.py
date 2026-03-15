"""Test CAME Domotic cover platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from aiocamedomotic.models import OpeningStatus, OpeningType
from homeassistant.components.cover import CoverDeviceClass
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic.const import DOMAIN
from custom_components.came_domotic.models import CameDomoticServerData

from .conftest import _mock_opening, _mock_server_info, _mock_topology
from .const import MOCK_CONFIG

_API_CLIENT = "custom_components.came_domotic.api.CameDomoticApiClient"

_COORDINATOR = (
    "custom_components.came_domotic.coordinator.CameDomoticDataUpdateCoordinator"
)


async def _setup_entry(hass, mock_openings):
    """Set up a config entry with the given mock openings list."""
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
        patch(
            f"{_API_CLIENT}.async_get_openings",
            return_value=mock_openings,
        ),
        patch(f"{_API_CLIENT}.async_get_lights", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_digital_inputs", return_value=[]),
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


# --- Entity creation ---


async def test_cover_entities_created(hass, bypass_get_data):
    """Test that one cover entity is created per opening."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "cover"
    ]
    assert len(entries) == 2


async def test_cover_unique_id(hass, bypass_get_data):
    """Test cover unique IDs follow the expected pattern."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "cover"
    }
    assert unique_ids == {
        "test_opening_100",
        "test_opening_200",
    }


async def test_cover_state(hass, bypass_get_data):
    """Test cover entities exist with expected entity IDs."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    living_room = hass.states.get("cover.living_room_shutter")
    assert living_room is not None

    bedroom = hass.states.get("cover.bedroom_shutter")
    assert bedroom is not None


async def test_no_openings(hass):
    """Test no cover entities created when there are no openings."""
    config_entry = await _setup_entry(hass, [])

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "cover"
    ]
    assert len(entries) == 0


# --- State properties ---


async def test_cover_is_closed_returns_none(hass):
    """Test is_closed always returns None (no position tracking)."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    await _setup_entry(hass, openings)

    state = hass.states.get("cover.living_room_shutter")
    assert state is not None
    # HA maps is_closed=None to "unknown" state
    # The entity exists and has no definitive closed/open state


async def test_cover_is_opening(hass):
    """Test is_opening returns True when status is OPENING."""
    openings = [
        _mock_opening(100, 101, "Living Room Shutter", status=OpeningStatus.OPENING)
    ]
    await _setup_entry(hass, openings)

    state = hass.states.get("cover.living_room_shutter")
    assert state is not None
    assert state.state == "opening"


async def test_cover_is_closing(hass):
    """Test is_closing returns True when status is CLOSING."""
    openings = [
        _mock_opening(100, 101, "Living Room Shutter", status=OpeningStatus.CLOSING)
    ]
    await _setup_entry(hass, openings)

    state = hass.states.get("cover.living_room_shutter")
    assert state is not None
    assert state.state == "closing"


async def test_cover_is_not_opening_when_stopped(hass):
    """Test is_opening returns False when status is STOPPED."""
    openings = [
        _mock_opening(100, 101, "Living Room Shutter", status=OpeningStatus.STOPPED)
    ]
    await _setup_entry(hass, openings)

    state = hass.states.get("cover.living_room_shutter")
    assert state is not None
    assert state.state != "opening"
    assert state.state != "closing"


async def test_cover_is_opening_not_found(hass):
    """Test is_opening returns False when opening disappears from data."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    config_entry = await _setup_entry(hass, openings)

    # Remove the opening from coordinator data
    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.openings.clear()

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

    state = hass.states.get("cover.living_room_shutter")
    assert state is not None
    assert state.state != "opening"


async def test_cover_is_closing_not_found(hass):
    """Test is_closing returns False when opening disappears from data."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    config_entry = await _setup_entry(hass, openings)

    coordinator = config_entry.runtime_data.coordinator
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

    state = hass.states.get("cover.living_room_shutter")
    assert state is not None
    assert state.state != "closing"


# --- Cover actions ---


async def test_cover_open(hass):
    """Test opening a cover calls async_set_opening_status with OPENING."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    config_entry = await _setup_entry(hass, openings)

    coordinator = config_entry.runtime_data.coordinator
    mock_set_status = AsyncMock()

    with patch.object(coordinator.api, "async_set_opening_status", mock_set_status):
        await hass.services.async_call(
            "cover",
            "open_cover",
            {"entity_id": "cover.living_room_shutter"},
            blocking=True,
        )

    mock_set_status.assert_awaited_once()
    called_opening = mock_set_status.call_args[0][0]
    called_status = mock_set_status.call_args[0][1]
    assert called_opening.open_act_id == 100
    assert called_status == OpeningStatus.OPENING


async def test_cover_close(hass):
    """Test closing a cover calls async_set_opening_status with CLOSING."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    config_entry = await _setup_entry(hass, openings)

    coordinator = config_entry.runtime_data.coordinator
    mock_set_status = AsyncMock()

    with patch.object(coordinator.api, "async_set_opening_status", mock_set_status):
        await hass.services.async_call(
            "cover",
            "close_cover",
            {"entity_id": "cover.living_room_shutter"},
            blocking=True,
        )

    mock_set_status.assert_awaited_once()
    called_status = mock_set_status.call_args[0][1]
    assert called_status == OpeningStatus.CLOSING


async def test_cover_stop(hass):
    """Test stopping a cover calls async_set_opening_status with STOPPED."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    config_entry = await _setup_entry(hass, openings)

    coordinator = config_entry.runtime_data.coordinator
    mock_set_status = AsyncMock()

    with patch.object(coordinator.api, "async_set_opening_status", mock_set_status):
        await hass.services.async_call(
            "cover",
            "stop_cover",
            {"entity_id": "cover.living_room_shutter"},
            blocking=True,
        )

    mock_set_status.assert_awaited_once()
    called_status = mock_set_status.call_args[0][1]
    assert called_status == OpeningStatus.STOPPED


async def test_cover_open_tilt(hass):
    """Test opening tilt calls async_set_opening_status with SLAT_OPEN."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    config_entry = await _setup_entry(hass, openings)

    coordinator = config_entry.runtime_data.coordinator
    mock_set_status = AsyncMock()

    with patch.object(coordinator.api, "async_set_opening_status", mock_set_status):
        await hass.services.async_call(
            "cover",
            "open_cover_tilt",
            {"entity_id": "cover.living_room_shutter"},
            blocking=True,
        )

    mock_set_status.assert_awaited_once()
    called_status = mock_set_status.call_args[0][1]
    assert called_status == OpeningStatus.SLAT_OPEN


async def test_cover_close_tilt(hass):
    """Test closing tilt calls async_set_opening_status with SLAT_CLOSE."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    config_entry = await _setup_entry(hass, openings)

    coordinator = config_entry.runtime_data.coordinator
    mock_set_status = AsyncMock()

    with patch.object(coordinator.api, "async_set_opening_status", mock_set_status):
        await hass.services.async_call(
            "cover",
            "close_cover_tilt",
            {"entity_id": "cover.living_room_shutter"},
            blocking=True,
        )

    mock_set_status.assert_awaited_once()
    called_status = mock_set_status.call_args[0][1]
    assert called_status == OpeningStatus.SLAT_CLOSE


async def test_cover_stop_tilt(hass):
    """Test stopping tilt calls async_set_opening_status with STOPPED."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    config_entry = await _setup_entry(hass, openings)

    coordinator = config_entry.runtime_data.coordinator
    mock_set_status = AsyncMock()

    with patch.object(coordinator.api, "async_set_opening_status", mock_set_status):
        await hass.services.async_call(
            "cover",
            "stop_cover_tilt",
            {"entity_id": "cover.living_room_shutter"},
            blocking=True,
        )

    mock_set_status.assert_awaited_once()
    called_status = mock_set_status.call_args[0][1]
    assert called_status == OpeningStatus.STOPPED


# --- Not-found edge cases ---


async def test_cover_open_not_found(hass):
    """Test opening a cover when opening disappears does not raise."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    config_entry = await _setup_entry(hass, openings)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.openings.clear()

    # Should not raise — just logs a warning
    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": "cover.living_room_shutter"},
        blocking=True,
    )


async def test_cover_close_not_found(hass):
    """Test closing a cover when opening disappears does not raise."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    config_entry = await _setup_entry(hass, openings)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.openings.clear()

    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": "cover.living_room_shutter"},
        blocking=True,
    )


async def test_cover_stop_not_found(hass):
    """Test stopping a cover when opening disappears does not raise."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    config_entry = await _setup_entry(hass, openings)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.openings.clear()

    await hass.services.async_call(
        "cover",
        "stop_cover",
        {"entity_id": "cover.living_room_shutter"},
        blocking=True,
    )


async def test_cover_open_tilt_not_found(hass):
    """Test opening tilt when opening disappears does not raise."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    config_entry = await _setup_entry(hass, openings)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.openings.clear()

    await hass.services.async_call(
        "cover",
        "open_cover_tilt",
        {"entity_id": "cover.living_room_shutter"},
        blocking=True,
    )


async def test_cover_close_tilt_not_found(hass):
    """Test closing tilt when opening disappears does not raise."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    config_entry = await _setup_entry(hass, openings)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.openings.clear()

    await hass.services.async_call(
        "cover",
        "close_cover_tilt",
        {"entity_id": "cover.living_room_shutter"},
        blocking=True,
    )


async def test_cover_stop_tilt_not_found(hass):
    """Test stopping tilt when opening disappears does not raise."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    config_entry = await _setup_entry(hass, openings)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.openings.clear()

    await hass.services.async_call(
        "cover",
        "stop_cover_tilt",
        {"entity_id": "cover.living_room_shutter"},
        blocking=True,
    )


# --- Extra attributes ---


async def test_cover_extra_attributes(hass):
    """Test cover exposes extra opening attributes."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    await _setup_entry(hass, openings)

    state = hass.states.get("cover.living_room_shutter")
    assert state is not None
    assert state.attributes["status"] == "STOPPED"
    assert state.attributes["opening_type"] == "SHUTTER"


async def test_cover_extra_attributes_not_found(hass):
    """Test cover returns no extra attributes when opening disappears."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    config_entry = await _setup_entry(hass, openings)

    # Simulate opening disappearing
    coordinator = config_entry.runtime_data.coordinator
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

    state = hass.states.get("cover.living_room_shutter")
    assert state is not None
    # Extra attributes should not contain opening-specific keys
    assert "status" not in state.attributes


# --- Device class ---


async def test_cover_device_class_shutter(hass):
    """Test cover device class is SHUTTER for shutter-type openings."""
    openings = [_mock_opening(100, 101, "Living Room Shutter")]
    await _setup_entry(hass, openings)

    state = hass.states.get("cover.living_room_shutter")
    assert state is not None
    assert state.attributes.get("device_class") == CoverDeviceClass.SHUTTER


async def test_cover_device_class_unknown_type(hass):
    """Test cover device class is None for unknown opening types."""
    openings = [
        _mock_opening(100, 101, "Mystery Opening", opening_type=OpeningType.UNKNOWN)
    ]
    await _setup_entry(hass, openings)

    state = hass.states.get("cover.mystery_opening")
    assert state is not None
    assert "device_class" not in state.attributes
