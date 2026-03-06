"""Test CAME Domotic Unofficial sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic_unofficial.const import DOMAIN

from .const import MOCK_CONFIG

_API_CLIENT = (
    "custom_components.came_domotic_unofficial.api." "CameDomoticUnofficialApiClient"
)


def _mock_thermo_zone(act_id, name, temperature):
    """Create a mock ThermoZone object."""
    zone = MagicMock()
    zone.act_id = act_id
    zone.name = name
    zone.temperature = temperature
    return zone


async def _setup_entry(hass, mock_data):
    """Set up a config entry with the given mock API data."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(f"{_API_CLIENT}.async_get_data", return_value=mock_data),
        patch(f"{_API_CLIENT}.async_dispose"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def test_thermo_zone_sensors_created(hass, bypass_get_data):
    """Test that one sensor entity is created per thermo zone."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "sensor"
    ]
    assert len(entries) == 2


async def test_thermo_zone_sensor_state(hass, bypass_get_data):
    """Test sensor states match zone temperatures."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    living_room = hass.states.get("sensor.came_domotic_unofficial_living_room")
    assert living_room is not None
    assert living_room.state == "20.0"

    bedroom = hass.states.get("sensor.came_domotic_unofficial_bedroom")
    assert bedroom is not None
    assert bedroom.state == "19.5"


async def test_thermo_zone_sensor_attributes(hass, bypass_get_data):
    """Test sensor attributes are correctly set."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.came_domotic_unofficial_living_room")
    assert state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS


async def test_thermo_zone_sensor_unique_id(hass, bypass_get_data):
    """Test sensor unique IDs follow the expected pattern."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "sensor"
    }
    assert unique_ids == {"test_thermo_zone_1", "test_thermo_zone_52"}


async def test_no_thermo_zones(hass):
    """Test no sensor entities created when there are no thermo zones."""
    mock_data = {
        "keycode": "AA:BB:CC:DD:EE:FF",
        "software_version": "1.2.3",
        "server_type": "ETI/Domo",
        "board": "board_v1",
        "thermo_zones": [],
    }
    config_entry = await _setup_entry(hass, mock_data)

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "sensor"
    ]
    assert len(entries) == 0


async def test_thermo_zone_sensor_zone_not_found(hass):
    """Test sensor returns unknown when zone disappears from data."""
    initial_data = {
        "keycode": "AA:BB:CC:DD:EE:FF",
        "software_version": "1.2.3",
        "server_type": "ETI/Domo",
        "board": "board_v1",
        "thermo_zones": [_mock_thermo_zone(1, "Living Room", 20.0)],
    }
    updated_data = {
        "keycode": "AA:BB:CC:DD:EE:FF",
        "software_version": "1.2.3",
        "server_type": "ETI/Domo",
        "board": "board_v1",
        "thermo_zones": [],
    }
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_data",
            side_effect=[initial_data, updated_data],
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Trigger a refresh with updated data (zone removed)
        coordinator = config_entry.runtime_data.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("sensor.came_domotic_unofficial_living_room")
    assert state is not None
    assert state.state == "unknown"
