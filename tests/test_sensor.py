"""Test CAME Domotic Unofficial sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic_unofficial.const import DOMAIN
from custom_components.came_domotic_unofficial.models import CameDomoticServerData

from .conftest import _mock_server_info
from .const import MOCK_CONFIG

_API_CLIENT = (
    "custom_components.came_domotic_unofficial.api.CameDomoticUnofficialApiClient"
)

_COORDINATOR = (
    "custom_components.came_domotic_unofficial.coordinator"
    ".CameDomoticUnofficialDataUpdateCoordinator"
)


def _mock_thermo_zone(
    act_id,
    name,
    temperature,
    set_point=21.0,
    mode="AUTO",
    season="winter",
    status=1,
    antifreeze=5.0,
    floor_ind=0,
    room_ind=0,
    leaf=True,
):
    """Create a mock ThermoZone object."""
    zone = MagicMock()
    zone.act_id = act_id
    zone.name = name
    zone.temperature = temperature
    zone.set_point = set_point
    zone.mode.name = mode
    zone.season.name = season
    zone.status.name = "ON" if status else "OFF"
    zone.antifreeze = antifreeze
    zone.floor_ind = floor_ind
    zone.room_ind = room_ind
    zone.leaf = leaf
    zone.raw_data = {
        "act_id": act_id,
        "name": name,
        "temp_dec": int(temperature * 10),
        "set_point": int(set_point * 10),
        "mode": 2 if mode == "AUTO" else 1,
        "season": season,
        "status": status,
        "antifreeze": int(antifreeze * 10) if antifreeze is not None else 0,
        "leaf": int(leaf),
        "floor_ind": floor_ind,
        "room_ind": room_ind,
    }
    return zone


def _mock_zones_list():
    """Return a list of mock thermo zones for API mocking."""
    return [
        _mock_thermo_zone(
            1, "Living Room", 20.0, set_point=21.0, floor_ind=0, room_ind=0
        ),
        _mock_thermo_zone(
            52,
            "Bedroom",
            19.5,
            set_point=20.0,
            mode="MANUAL",
            floor_ind=1,
            room_ind=1,
        ),
    ]


async def _setup_entry(hass, mock_zones):
    """Set up a config entry with the given mock thermo zones list."""
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
            return_value=mock_zones,
        ),
        patch(f"{_API_CLIENT}.async_get_scenarios", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_openings", return_value=[]),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch(f"{_COORDINATOR}.start_long_poll"),
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

    living_room = hass.states.get("sensor.living_room")
    assert living_room is not None
    assert living_room.state == "20.0"

    bedroom = hass.states.get("sensor.bedroom")
    assert bedroom is not None
    assert bedroom.state == "19.5"


async def test_thermo_zone_sensor_attributes(hass, bypass_get_data):
    """Test sensor attributes are correctly set."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_room")
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
    assert unique_ids == {
        "test_thermo_zone_1_temperature",
        "test_thermo_zone_52_temperature",
    }


async def test_no_thermo_zones(hass):
    """Test no sensor entities created when there are no thermo zones."""
    config_entry = await _setup_entry(hass, [])

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "sensor"
    ]
    assert len(entries) == 0


async def test_thermo_zone_sensor_extra_attributes(hass, bypass_get_data):
    """Test sensor exposes extra thermo zone attributes."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_room")
    assert state is not None
    assert state.attributes["set_point"] == 21.0
    assert state.attributes["mode"] == "AUTO"
    assert state.attributes["season"] == "winter"
    assert state.attributes["status"] == "ON"
    assert state.attributes["antifreeze"] == 5.0


async def test_thermo_zone_sensor_zone_not_found(hass):
    """Test sensor returns unknown when zone disappears from data."""
    initial_zones = [_mock_thermo_zone(1, "Living Room", 20.0)]

    config_entry = await _setup_entry(hass, initial_zones)

    # Now simulate a refresh where zone 1 is gone
    coordinator = config_entry.runtime_data.coordinator
    empty_data = CameDomoticServerData(
        server_info=_mock_server_info(),
        thermo_zones={},
    )

    with (
        patch.object(
            coordinator,
            "_async_update_data",
            return_value=empty_data,
        ),
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("sensor.living_room")
    assert state is not None
    assert state.state == "unknown"
