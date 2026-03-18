"""Test CAME Domotic sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from aiocamedomotic.models import AnalogSensorType
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, UnitOfPressure, UnitOfTemperature
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic.const import DOMAIN
from custom_components.came_domotic.models import CameDomoticServerData, PingResult

from .conftest import (
    MOCK_ANALOG_INPUTS,
    MOCK_ANALOG_SENSORS,
    MOCK_SCENARIOS,
    MOCK_THERMO_ZONES,
    _mock_analog_input,
    _mock_analog_sensor,
    _mock_scenario,
    _mock_server_info,
    _mock_thermo_zone,
    _mock_topology,
)
from .const import MOCK_CONFIG

_API_CLIENT = "custom_components.came_domotic.api.CameDomoticApiClient"

_COORDINATOR = (
    "custom_components.came_domotic.coordinator.CameDomoticDataUpdateCoordinator"
)


async def _setup_entry(
    hass,
    mock_zones=None,
    mock_analog_sensors=None,
    mock_analog_inputs=None,
    mock_scenarios=None,
    ping_return=10.0,
):
    """Set up a config entry with the given mock device lists."""
    if mock_zones is None:
        mock_zones = list(MOCK_THERMO_ZONES)
    if mock_analog_sensors is None:
        mock_analog_sensors = list(MOCK_ANALOG_SENSORS)
    if mock_analog_inputs is None:
        mock_analog_inputs = list(MOCK_ANALOG_INPUTS)
    if mock_scenarios is None:
        mock_scenarios = []
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
        patch(
            f"{_API_CLIENT}.async_get_scenarios",
            return_value=mock_scenarios,
        ),
        patch(f"{_API_CLIENT}.async_get_openings", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_lights", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_digital_inputs", return_value=[]),
        patch(
            f"{_API_CLIENT}.async_get_analog_sensors",
            return_value=mock_analog_sensors,
        ),
        patch(
            f"{_API_CLIENT}.async_get_analog_inputs",
            return_value=mock_analog_inputs,
        ),
        patch(f"{_API_CLIENT}.async_get_relays", return_value=[]),
        patch(
            f"{_API_CLIENT}.async_get_topology",
            return_value=_mock_topology(),
        ),
        patch(f"{_API_CLIENT}.async_ping", return_value=ping_return),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch(f"{_COORDINATOR}.start_long_poll"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


# --- Thermo zone temperature sensors ---


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
    # 2 thermo zones + 1 latency + 2 analog sensors + 2 analog inputs
    # + 2 scenario status = 9
    assert len(entries) == 9


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
        "test_ping_latency",
        "test_analog_sensor_500_analog_temperature",
        "test_analog_sensor_501_analog_humidity",
        "test_analog_input_800_analog_input_temperature",
        "test_analog_input_801_analog_input_humidity",
        "test_scenario_status_10",
        "test_scenario_status_20",
    }


async def test_no_thermo_zones(hass):
    """Test only the latency sensor is created when there are no device sensors."""
    config_entry = await _setup_entry(
        hass, mock_zones=[], mock_analog_sensors=[], mock_analog_inputs=[]
    )

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "sensor"
    ]
    assert len(entries) == 1


async def test_thermo_zone_sensor_zone_not_found(hass):
    """Test sensor returns unknown when zone disappears from data."""
    initial_zones = [_mock_thermo_zone(1, "Living Room", 20.0)]

    config_entry = await _setup_entry(hass, mock_zones=initial_zones)

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


# --- Server latency sensor ---


async def test_server_latency_sensor_created(hass, bypass_get_data):
    """Test one latency sensor is created per config entry, disabled by default."""
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
            and e.unique_id == "test_ping_latency"
        ),
        None,
    )
    assert entry is not None
    assert entry.domain == "sensor"
    assert entry.disabled_by is not None  # disabled by default


async def test_server_latency_sensor_value(hass):
    """Test latency sensor reflects the round-trip time from async_ping."""
    config_entry = await _setup_entry(hass, mock_zones=[], ping_return=12.5)

    ping_coordinator = config_entry.runtime_data.ping_coordinator
    assert ping_coordinator.data is not None
    assert ping_coordinator.data.latency_ms == 12.5


async def test_server_latency_sensor_no_data_when_unreachable(hass):
    """Test latency sensor returns None when server is unreachable."""
    config_entry = await _setup_entry(hass, mock_zones=[], ping_return=10.0)

    ping_coordinator = config_entry.runtime_data.ping_coordinator
    ping_coordinator.async_set_updated_data(
        PingResult(connected=False, latency_ms=None)
    )
    await hass.async_block_till_done()

    assert ping_coordinator.data.latency_ms is None


def test_server_latency_native_value():
    """Test CameDomoticServerLatencySensor.native_value reads from coordinator data."""
    from custom_components.came_domotic.sensor import CameDomoticServerLatencySensor

    coordinator = MagicMock()
    coordinator.data = PingResult(connected=True, latency_ms=25.0)
    entity = CameDomoticServerLatencySensor(coordinator, "test_entry")
    assert entity.native_value == 25.0

    coordinator.data = PingResult(connected=False, latency_ms=None)
    assert entity.native_value is None


# --- Analog sensor tests ---


async def test_analog_sensor_created(hass):
    """Test analog sensor entities are created."""
    config_entry = await _setup_entry(hass, mock_zones=[])

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id
        and e.domain == "sensor"
        and "analog_sensor" in e.unique_id
    ]
    assert len(entries) == 2


async def test_analog_sensor_state(hass):
    """Test analog sensor states match sensor values."""
    await _setup_entry(hass, mock_zones=[])

    state = hass.states.get("sensor.outdoor_temperature")
    assert state is not None
    assert state.state == "15.5"

    state = hass.states.get("sensor.indoor_humidity")
    assert state is not None
    assert state.state == "45.0"


async def test_analog_sensor_temperature_attributes(hass):
    """Test temperature analog sensor attributes are correctly set."""
    await _setup_entry(hass, mock_zones=[])

    state = hass.states.get("sensor.outdoor_temperature")
    assert state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS


async def test_analog_sensor_humidity_attributes(hass):
    """Test humidity analog sensor attributes are correctly set."""
    await _setup_entry(hass, mock_zones=[])

    state = hass.states.get("sensor.indoor_humidity")
    assert state.attributes["device_class"] == SensorDeviceClass.HUMIDITY
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert state.attributes["unit_of_measurement"] == PERCENTAGE


async def test_analog_sensor_unique_ids(hass):
    """Test analog sensor unique IDs follow the expected pattern."""
    config_entry = await _setup_entry(hass, mock_zones=[])

    registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and "analog_sensor" in e.unique_id
    }
    assert unique_ids == {
        "test_analog_sensor_500_analog_temperature",
        "test_analog_sensor_501_analog_humidity",
    }


async def test_no_analog_sensors(hass):
    """Test no analog sensor entities when list is empty."""
    config_entry = await _setup_entry(hass, mock_zones=[], mock_analog_sensors=[])

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and "analog_sensor" in e.unique_id
    ]
    assert len(entries) == 0


async def test_analog_sensor_disappears(hass):
    """Test analog sensor returns unknown when sensor disappears from data."""
    initial = [_mock_analog_sensor(500, "Outdoor Temperature", 15.5)]
    config_entry = await _setup_entry(hass, mock_zones=[], mock_analog_sensors=initial)

    coordinator = config_entry.runtime_data.coordinator
    empty_data = CameDomoticServerData(server_info=_mock_server_info())

    with patch.object(coordinator, "_async_update_data", return_value=empty_data):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("sensor.outdoor_temperature")
    assert state is not None
    assert state.state == "unknown"


async def test_analog_sensor_unknown_type(hass):
    """Test UNKNOWN sensor type creates a generic sensor entity."""
    sensors = [
        _mock_analog_sensor(
            600,
            "Mystery Sensor",
            42.0,
            unit="ppm",
            sensor_type=AnalogSensorType.UNKNOWN,
        )
    ]
    await _setup_entry(hass, mock_zones=[], mock_analog_sensors=sensors)

    state = hass.states.get("sensor.mystery_sensor")
    assert state is not None
    assert state.state == "42.0"
    assert state.attributes.get("device_class") is None
    assert state.attributes["unit_of_measurement"] == "ppm"


async def test_analog_sensor_pressure(hass):
    """Test pressure analog sensor attributes."""
    sensors = [
        _mock_analog_sensor(
            700,
            "Barometer",
            1013.25,
            unit="hPa",
            sensor_type=AnalogSensorType.PRESSURE,
        )
    ]
    await _setup_entry(hass, mock_zones=[], mock_analog_sensors=sensors)

    state = hass.states.get("sensor.barometer")
    assert state is not None
    assert state.state == "1013.25"
    assert state.attributes["device_class"] == SensorDeviceClass.ATMOSPHERIC_PRESSURE
    assert state.attributes["unit_of_measurement"] == UnitOfPressure.HPA


# --- Analog input tests ---


async def test_analog_input_created(hass):
    """Test analog input entities are created."""
    config_entry = await _setup_entry(hass, mock_zones=[], mock_analog_sensors=[])

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id
        and e.domain == "sensor"
        and "analog_input" in e.unique_id
    ]
    assert len(entries) == 2


async def test_analog_input_state(hass):
    """Test analog input states match sensor values."""
    await _setup_entry(hass, mock_zones=[], mock_analog_sensors=[])

    state = hass.states.get("sensor.garden_thermometer")
    assert state is not None
    assert state.state == "22.5"

    state = hass.states.get("sensor.basement_hygrometer")
    assert state is not None
    assert state.state == "65.0"


async def test_analog_input_temperature_attributes(hass):
    """Test temperature analog input attributes are correctly set."""
    await _setup_entry(hass, mock_zones=[], mock_analog_sensors=[])

    state = hass.states.get("sensor.garden_thermometer")
    assert state.attributes["device_class"] == SensorDeviceClass.TEMPERATURE
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert state.attributes["unit_of_measurement"] == UnitOfTemperature.CELSIUS


async def test_analog_input_humidity_attributes(hass):
    """Test humidity analog input attributes are correctly set."""
    await _setup_entry(hass, mock_zones=[], mock_analog_sensors=[])

    state = hass.states.get("sensor.basement_hygrometer")
    assert state.attributes["device_class"] == SensorDeviceClass.HUMIDITY
    assert state.attributes["state_class"] == SensorStateClass.MEASUREMENT
    assert state.attributes["unit_of_measurement"] == PERCENTAGE


async def test_analog_input_unique_ids(hass):
    """Test analog input unique IDs follow the expected pattern."""
    config_entry = await _setup_entry(hass, mock_zones=[], mock_analog_sensors=[])

    registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and "analog_input" in e.unique_id
    }
    assert unique_ids == {
        "test_analog_input_800_analog_input_temperature",
        "test_analog_input_801_analog_input_humidity",
    }


async def test_no_analog_inputs(hass):
    """Test no analog input entities when list is empty."""
    config_entry = await _setup_entry(
        hass, mock_zones=[], mock_analog_sensors=[], mock_analog_inputs=[]
    )

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and "analog_input" in e.unique_id
    ]
    assert len(entries) == 0


async def test_analog_input_disappears(hass):
    """Test analog input returns unknown when sensor disappears from data."""
    initial = [_mock_analog_input(800, "Garden Thermometer", 22.5)]
    config_entry = await _setup_entry(
        hass, mock_zones=[], mock_analog_sensors=[], mock_analog_inputs=initial
    )

    coordinator = config_entry.runtime_data.coordinator
    empty_data = CameDomoticServerData(server_info=_mock_server_info())

    with patch.object(coordinator, "_async_update_data", return_value=empty_data):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("sensor.garden_thermometer")
    assert state is not None
    assert state.state == "unknown"


async def test_analog_input_generic_unit(hass):
    """Test unknown unit creates a generic sensor with raw unit string."""
    inputs = [_mock_analog_input(900, "Air Quality", 42.0, unit="ppm")]
    await _setup_entry(
        hass, mock_zones=[], mock_analog_sensors=[], mock_analog_inputs=inputs
    )

    state = hass.states.get("sensor.air_quality")
    assert state is not None
    assert state.state == "42.0"
    assert state.attributes.get("device_class") is None
    assert state.attributes["unit_of_measurement"] == "ppm"


async def test_analog_input_empty_unit(hass):
    """Test empty unit string creates sensor with no unit of measurement."""
    inputs = [_mock_analog_input(901, "Raw Sensor", 100.0, unit="")]
    await _setup_entry(
        hass, mock_zones=[], mock_analog_sensors=[], mock_analog_inputs=inputs
    )

    state = hass.states.get("sensor.raw_sensor")
    assert state is not None
    assert state.state == "100.0"
    assert state.attributes.get("device_class") is None
    assert state.attributes.get("unit_of_measurement") is None


async def test_analog_input_pressure(hass):
    """Test pressure analog input attributes."""
    inputs = [_mock_analog_input(902, "Barometer Input", 1013.25, unit="hPa")]
    await _setup_entry(
        hass, mock_zones=[], mock_analog_sensors=[], mock_analog_inputs=inputs
    )

    state = hass.states.get("sensor.barometer_input")
    assert state is not None
    assert state.state == "1013.25"
    assert state.attributes["device_class"] == SensorDeviceClass.ATMOSPHERIC_PRESSURE
    assert state.attributes["unit_of_measurement"] == UnitOfPressure.HPA


# --- Scenario status sensor tests ---


async def test_scenario_status_sensor_created(hass):
    """Test scenario status sensor entities are created."""
    scenarios = list(MOCK_SCENARIOS)
    config_entry = await _setup_entry(
        hass,
        mock_zones=[],
        mock_analog_sensors=[],
        mock_analog_inputs=[],
        mock_scenarios=scenarios,
    )

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id
        and "scenario_status" in e.unique_id
    ]
    assert len(entries) == 2


async def test_scenario_status_sensor_state(hass):
    """Test scenario status sensor state reflects scenario_status."""
    scenarios = [_mock_scenario(10, "Good Morning", scenario_status="OFF")]
    await _setup_entry(
        hass,
        mock_zones=[],
        mock_analog_sensors=[],
        mock_analog_inputs=[],
        mock_scenarios=scenarios,
    )

    state = hass.states.get("sensor.good_morning_status")
    assert state is not None
    assert state.state == "OFF"


async def test_scenario_status_sensor_attributes(hass):
    """Test scenario status sensor exposes allowed_values and last_triggered."""
    scenarios = [_mock_scenario(10, "Good Morning", scenario_status="OFF")]
    await _setup_entry(
        hass,
        mock_zones=[],
        mock_analog_sensors=[],
        mock_analog_inputs=[],
        mock_scenarios=scenarios,
    )

    state = hass.states.get("sensor.good_morning_status")
    assert state is not None
    assert state.attributes["allowed_values"] == ["OFF", "TRIGGERED", "ACTIVE"]
    assert state.attributes["last_triggered"] is None


async def test_scenario_status_sensor_unique_id(hass):
    """Test scenario status sensor unique IDs follow the expected pattern."""
    scenarios = list(MOCK_SCENARIOS)
    config_entry = await _setup_entry(
        hass,
        mock_zones=[],
        mock_analog_sensors=[],
        mock_analog_inputs=[],
        mock_scenarios=scenarios,
    )

    registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id
        and "scenario_status" in e.unique_id
    }
    assert unique_ids == {
        "test_scenario_status_10",
        "test_scenario_status_20",
    }


async def test_scenario_status_sensor_disappears(hass):
    """Test scenario status sensor returns unknown when scenario disappears."""
    scenarios = [_mock_scenario(10, "Good Morning")]
    config_entry = await _setup_entry(
        hass,
        mock_zones=[],
        mock_analog_sensors=[],
        mock_analog_inputs=[],
        mock_scenarios=scenarios,
    )

    coordinator = config_entry.runtime_data.coordinator
    empty_data = CameDomoticServerData(server_info=_mock_server_info())

    with patch.object(coordinator, "_async_update_data", return_value=empty_data):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("sensor.good_morning_status")
    assert state is not None
    assert state.state == "unknown"
    assert "allowed_values" not in state.attributes


async def test_scenario_status_sensor_last_triggered_on_transition(hass):
    """Test last_triggered updates when status transitions to TRIGGERED."""
    scenarios = [_mock_scenario(10, "Good Morning", scenario_status="OFF")]
    config_entry = await _setup_entry(
        hass,
        mock_zones=[],
        mock_analog_sensors=[],
        mock_analog_inputs=[],
        mock_scenarios=scenarios,
    )

    # Verify initially None
    state = hass.states.get("sensor.good_morning_status")
    assert state.attributes["last_triggered"] is None

    # Simulate status change to TRIGGERED
    coordinator = config_entry.runtime_data.coordinator
    triggered_scenario = _mock_scenario(10, "Good Morning", scenario_status="TRIGGERED")
    updated_data = CameDomoticServerData(
        server_info=_mock_server_info(),
        scenarios={triggered_scenario.id: triggered_scenario},
    )

    with patch.object(coordinator, "_async_update_data", return_value=updated_data):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("sensor.good_morning_status")
    assert state.state == "TRIGGERED"
    assert state.attributes["last_triggered"] is not None


async def test_no_scenario_status_sensors(hass):
    """Test no scenario status sensors created when there are no scenarios."""
    config_entry = await _setup_entry(
        hass,
        mock_zones=[],
        mock_analog_sensors=[],
        mock_analog_inputs=[],
        mock_scenarios=[],
    )

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id
        and "scenario_status" in e.unique_id
    ]
    assert len(entries) == 0
