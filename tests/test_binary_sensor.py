"""Test CAME Domotic binary sensor platform."""

from __future__ import annotations

from unittest.mock import patch

from aiocamedomotic.models import DigitalInputStatus
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic.const import DOMAIN
from custom_components.came_domotic.models import CameDomoticServerData, PingResult

from .conftest import _mock_digital_input, _mock_server_info
from .const import MOCK_CONFIG

_API_CLIENT = "custom_components.came_domotic.api.CameDomoticApiClient"

_COORDINATOR = (
    "custom_components.came_domotic.coordinator.CameDomoticDataUpdateCoordinator"
)


async def _setup_entry(hass, mock_digital_inputs, ping_return=10.0):
    """Set up a config entry with the given mock digital inputs list."""
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
        patch(
            f"{_API_CLIENT}.async_get_digital_inputs",
            return_value=mock_digital_inputs,
        ),
        patch(f"{_API_CLIENT}.async_ping", return_value=ping_return),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch(f"{_COORDINATOR}.start_long_poll"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


# --- Entity creation ---


async def test_binary_sensor_entities_created(hass, bypass_get_data):
    """Test that one binary sensor entity is created per digital input."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "binary_sensor"
    ]
    assert len(entries) == 3


async def test_binary_sensor_unique_id(hass, bypass_get_data):
    """Test binary sensor unique IDs follow the expected pattern."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "binary_sensor"
    }
    assert unique_ids == {
        "test_digital_input_400",
        "test_digital_input_401",
        "test_server_connectivity",
    }


async def test_binary_sensor_state(hass, bypass_get_data):
    """Test binary sensor entities exist with expected entity IDs."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    front_door = hass.states.get("binary_sensor.front_door_sensor")
    assert front_door is not None

    window = hass.states.get("binary_sensor.window_contact")
    assert window is not None


async def test_no_digital_inputs(hass):
    """Test only the connectivity sensor is created when there are no digital inputs."""
    config_entry = await _setup_entry(hass, [])

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "binary_sensor"
    ]
    assert len(entries) == 1


# --- State properties ---


async def test_binary_sensor_is_on_active(hass):
    """Test is_on returns True when status is ACTIVE."""
    digital_inputs = [
        _mock_digital_input(400, "Front Door Sensor", status=DigitalInputStatus.ACTIVE),
    ]
    await _setup_entry(hass, digital_inputs)

    state = hass.states.get("binary_sensor.front_door_sensor")
    assert state is not None
    assert state.state == "on"


async def test_binary_sensor_is_on_idle(hass):
    """Test is_on returns False when status is IDLE."""
    digital_inputs = [
        _mock_digital_input(400, "Front Door Sensor", status=DigitalInputStatus.IDLE),
    ]
    await _setup_entry(hass, digital_inputs)

    state = hass.states.get("binary_sensor.front_door_sensor")
    assert state is not None
    assert state.state == "off"


async def test_binary_sensor_is_on_unknown(hass):
    """Test is_on returns None when status is UNKNOWN."""
    digital_inputs = [
        _mock_digital_input(
            400, "Front Door Sensor", status=DigitalInputStatus.UNKNOWN
        ),
    ]
    await _setup_entry(hass, digital_inputs)

    state = hass.states.get("binary_sensor.front_door_sensor")
    assert state is not None
    assert state.state == "unknown"


async def test_binary_sensor_is_on_not_found(hass):
    """Test is_on returns None when digital input disappears from data."""
    digital_inputs = [_mock_digital_input(400, "Front Door Sensor")]
    config_entry = await _setup_entry(hass, digital_inputs)

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

    state = hass.states.get("binary_sensor.front_door_sensor")
    assert state is not None
    assert state.state == "unknown"


# --- Extra attributes ---


async def test_binary_sensor_extra_attributes(hass):
    """Test binary sensor exposes extra digital input attributes."""
    digital_inputs = [
        _mock_digital_input(
            400,
            "Front Door Sensor",
            status=DigitalInputStatus.ACTIVE,
            utc_time=1700000000,
        ),
    ]
    await _setup_entry(hass, digital_inputs)

    state = hass.states.get("binary_sensor.front_door_sensor")
    assert state is not None
    assert state.attributes["addr"] == 0
    assert state.attributes["input_type"] == "STATUS"
    assert state.attributes["timestamp"] == "2023-11-14T14:13:20-08:00"


async def test_binary_sensor_extra_attributes_not_found(hass):
    """Test binary sensor returns no extra attributes when device disappears."""
    digital_inputs = [_mock_digital_input(400, "Front Door Sensor")]
    config_entry = await _setup_entry(hass, digital_inputs)

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

    state = hass.states.get("binary_sensor.front_door_sensor")
    assert state is not None
    # Extra attributes should not contain digital-input-specific keys
    assert "input_type" not in state.attributes


# --- Server connectivity sensor ---


async def test_server_connectivity_sensor_created(hass, bypass_get_data):
    """Test one server connectivity sensor is created per config entry."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entry = next(
        (
            e
            for e in registry.entities.values()
            if e.config_entry_id == config_entry.entry_id
            and e.unique_id == "test_server_connectivity"
        ),
        None,
    )
    assert entry is not None
    assert entry.domain == "binary_sensor"


async def test_server_connectivity_sensor_on(hass):
    """Test connectivity sensor is on when server responds to ping."""
    config_entry = await _setup_entry(hass, [], ping_return=5.0)

    ping_coordinator = config_entry.runtime_data.ping_coordinator
    ping_coordinator.async_set_updated_data(PingResult(connected=True, latency_ms=5.0))
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entry = next(
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id
        and e.unique_id == "test_server_connectivity"
    )
    state = hass.states.get(entry.entity_id)
    assert state is not None
    assert state.state == "on"


async def test_server_connectivity_sensor_off(hass):
    """Test connectivity sensor is off when server is unreachable."""
    config_entry = await _setup_entry(hass, [], ping_return=5.0)

    ping_coordinator = config_entry.runtime_data.ping_coordinator
    ping_coordinator.async_set_updated_data(
        PingResult(connected=False, latency_ms=None)
    )
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entry = next(
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id
        and e.unique_id == "test_server_connectivity"
    )
    state = hass.states.get(entry.entity_id)
    assert state is not None
    assert state.state == "off"
