"""Test CAME Domotic climate platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from aiocamedomotic.models import (
    ThermoZoneFanSpeed,
    ThermoZoneMode,
    ThermoZoneSeason,
    ThermoZoneStatus,
)
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    ATTR_TEMPERATURE,
    PRESET_NONE,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic.api import CameDomoticApiClientError
from custom_components.came_domotic.climate import CameDomoticClimate
from custom_components.came_domotic.const import DOMAIN
from custom_components.came_domotic.models import CameDomoticServerData

from .conftest import (
    MOCK_THERMO_ZONES,
    _mock_server_info,
    _mock_thermo_zone,
    _mock_topology,
)
from .const import MOCK_CONFIG

_API_CLIENT = "custom_components.came_domotic.api.CameDomoticApiClient"

_COORDINATOR = (
    "custom_components.came_domotic.coordinator.CameDomoticDataUpdateCoordinator"
)

# Entity IDs are generated from zone name by HA: "climate.<slugified_name>"
_ENTITY_LIVING_ROOM = "climate.living_room"
_ENTITY_BEDROOM = "climate.bedroom"


async def _setup_entry(hass, mock_zones=None):
    """Set up a config entry with the given mock thermo zones."""
    if mock_zones is None:
        mock_zones = list(MOCK_THERMO_ZONES)
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
        patch(f"{_API_CLIENT}.async_get_lights", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_digital_inputs", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_analog_sensors", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_analog_inputs", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_relays", return_value=[]),
        patch(
            f"{_API_CLIENT}.async_get_topology",
            return_value=_mock_topology(),
        ),
        patch(f"{_API_CLIENT}.async_ping", return_value=10.0),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch(f"{_COORDINATOR}.start_long_poll"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


def _get_climate_entity(hass, config_entry_id: str = "test") -> CameDomoticClimate:
    """Look up the first climate entity for the given config entry."""
    registry = er.async_get(hass)
    entry = next(
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry_id and e.domain == "climate"
    )
    entity = hass.data["entity_components"]["climate"].get_entity(entry.entity_id)
    assert isinstance(entity, CameDomoticClimate)
    return entity


# --- Entity creation ---


async def test_climate_entities_created(hass):
    """Test that one climate entity is created per thermo zone."""
    await _setup_entry(hass)

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == "test" and e.domain == "climate"
    ]
    assert len(entries) == 2


async def test_climate_unique_ids(hass):
    """Test climate entity unique IDs follow the expected pattern."""
    await _setup_entry(hass)

    registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in registry.entities.values()
        if e.config_entry_id == "test" and e.domain == "climate"
    }
    assert unique_ids == {"test_climate_1", "test_climate_52"}


async def test_no_climate_entities_when_no_zones(hass):
    """Test no climate entities are created when there are no thermo zones."""
    await _setup_entry(hass, mock_zones=[])

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == "test" and e.domain == "climate"
    ]
    assert len(entries) == 0


# --- Suggested area ---


async def test_suggested_area_none_when_topology_missing(hass):
    """Test device has no suggested_area when topology is unavailable."""
    zones = [_mock_thermo_zone(1, "Zone A", 20.0, room_ind=0)]
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            return_value=_mock_server_info(),
        ),
        patch(f"{_API_CLIENT}.async_get_thermo_zones", return_value=zones),
        patch(f"{_API_CLIENT}.async_get_scenarios", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_openings", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_lights", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_digital_inputs", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_analog_sensors", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_analog_inputs", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_relays", return_value=[]),
        patch(
            f"{_API_CLIENT}.async_get_topology",
            side_effect=CameDomoticApiClientError("unavailable"),
        ),
        patch(f"{_API_CLIENT}.async_ping", return_value=10.0),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch(f"{_COORDINATOR}.start_long_poll"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("climate.zone_a")
    assert state is not None


async def test_suggested_area_none_when_room_ind_not_found(hass):
    """Test device has no suggested_area when room_ind doesn't match topology."""
    zones = [_mock_thermo_zone(1, "Zone B", 20.0, room_ind=999)]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_b")
    assert state is not None


# --- HVAC mode property ---


async def test_hvac_mode_off_when_zone_mode_off(hass):
    """Test hvac_mode is OFF when zone mode is OFF."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, mode=ThermoZoneMode.OFF),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state is not None
    assert state.state == HVACMode.OFF


async def test_hvac_mode_off_when_plant_off(hass):
    """Test hvac_mode is OFF when season is PLANT_OFF regardless of zone mode."""
    zones = [
        _mock_thermo_zone(
            1,
            "Zone A",
            20.0,
            mode=ThermoZoneMode.AUTO,
            season=ThermoZoneSeason.PLANT_OFF,
        ),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state is not None
    assert state.state == HVACMode.OFF


async def test_hvac_mode_heat_in_winter_manual(hass):
    """Test hvac_mode is HEAT when MANUAL mode in WINTER season."""
    zones = [
        _mock_thermo_zone(
            1,
            "Zone A",
            20.0,
            mode=ThermoZoneMode.MANUAL,
            season=ThermoZoneSeason.WINTER,
        ),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state is not None
    assert state.state == HVACMode.HEAT


async def test_hvac_mode_cool_in_summer_manual(hass):
    """Test hvac_mode is COOL when MANUAL mode in SUMMER season."""
    zones = [
        _mock_thermo_zone(
            1,
            "Zone A",
            20.0,
            mode=ThermoZoneMode.MANUAL,
            season=ThermoZoneSeason.SUMMER,
        ),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state is not None
    assert state.state == HVACMode.COOL


async def test_hvac_mode_auto_in_auto_mode(hass):
    """Test hvac_mode is AUTO when zone is in AUTO mode."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, mode=ThermoZoneMode.AUTO),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state is not None
    assert state.state == HVACMode.AUTO


async def test_hvac_mode_auto_in_jolly_mode(hass):
    """Test hvac_mode is AUTO when zone is in JOLLY mode."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, mode=ThermoZoneMode.JOLLY),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state is not None
    assert state.state == HVACMode.AUTO


async def test_hvac_mode_none_for_unknown_mode(hass):
    """Test hvac_mode returns None when zone mode is UNKNOWN."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, mode=ThermoZoneMode.UNKNOWN),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state is not None
    assert state.state == "unknown"


# --- Dynamic hvac_modes ---


async def test_hvac_modes_winter(hass):
    """Test available HVAC modes in WINTER season."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, season=ThermoZoneSeason.WINTER),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state is not None
    assert set(state.attributes["hvac_modes"]) == {
        HVACMode.OFF,
        HVACMode.HEAT,
        HVACMode.AUTO,
    }


async def test_hvac_modes_summer(hass):
    """Test available HVAC modes in SUMMER season."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, season=ThermoZoneSeason.SUMMER),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state is not None
    assert set(state.attributes["hvac_modes"]) == {
        HVACMode.OFF,
        HVACMode.COOL,
        HVACMode.AUTO,
    }


async def test_hvac_modes_plant_off(hass):
    """Test available HVAC modes when season is PLANT_OFF."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, season=ThermoZoneSeason.PLANT_OFF),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state is not None
    assert state.attributes["hvac_modes"] == [HVACMode.OFF]


# --- HVAC action ---


async def test_hvac_action_heating(hass):
    """Test hvac_action is HEATING when status is ON in WINTER."""
    zones = [
        _mock_thermo_zone(
            1,
            "Zone A",
            20.0,
            mode=ThermoZoneMode.AUTO,
            status=ThermoZoneStatus.ON,
            season=ThermoZoneSeason.WINTER,
        ),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state.attributes["hvac_action"] == HVACAction.HEATING


async def test_hvac_action_cooling(hass):
    """Test hvac_action is COOLING when status is ON in SUMMER."""
    zones = [
        _mock_thermo_zone(
            1,
            "Zone A",
            20.0,
            mode=ThermoZoneMode.AUTO,
            status=ThermoZoneStatus.ON,
            season=ThermoZoneSeason.SUMMER,
        ),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state.attributes["hvac_action"] == HVACAction.COOLING


async def test_hvac_action_idle(hass):
    """Test hvac_action is IDLE when status is OFF but zone mode is not OFF."""
    zones = [
        _mock_thermo_zone(
            1,
            "Zone A",
            20.0,
            mode=ThermoZoneMode.AUTO,
            status=ThermoZoneStatus.OFF,
            season=ThermoZoneSeason.WINTER,
        ),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state.attributes["hvac_action"] == HVACAction.IDLE


async def test_hvac_action_off(hass):
    """Test hvac_action is OFF when zone mode is OFF."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, mode=ThermoZoneMode.OFF),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state.attributes["hvac_action"] == HVACAction.OFF


async def test_hvac_action_off_when_plant_off(hass):
    """Test hvac_action is OFF when season is PLANT_OFF."""
    zones = [
        _mock_thermo_zone(
            1,
            "Zone A",
            20.0,
            mode=ThermoZoneMode.AUTO,
            status=ThermoZoneStatus.ON,
            season=ThermoZoneSeason.PLANT_OFF,
        ),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state.attributes["hvac_action"] == HVACAction.OFF


# --- Temperature properties ---


async def test_current_temperature(hass):
    """Test current_temperature returns zone temperature."""
    zones = [_mock_thermo_zone(1, "Zone A", 22.5)]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state.attributes["current_temperature"] == 22.5


async def test_target_temperature(hass):
    """Test target_temperature returns zone set_point."""
    zones = [_mock_thermo_zone(1, "Zone A", 20.0, set_point=23.0)]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state.attributes["temperature"] == 23.0


async def test_temperature_none_when_zone_missing(hass):
    """Test temperature returns unknown when zone disappears from data."""
    zones = [_mock_thermo_zone(1, "Zone A", 20.0)]
    config_entry = await _setup_entry(hass, mock_zones=zones)

    coordinator = config_entry.runtime_data.coordinator
    empty_data = CameDomoticServerData(server_info=_mock_server_info())

    with patch.object(coordinator, "_async_update_data", return_value=empty_data):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("climate.zone_a")
    assert state is not None
    assert state.state == "unknown"


# --- Fan mode ---


@pytest.mark.parametrize(
    ("fan_speed", "expected_mode"),
    [
        (ThermoZoneFanSpeed.OFF, "off"),
        (ThermoZoneFanSpeed.SLOW, "low"),
        (ThermoZoneFanSpeed.MEDIUM, "medium"),
        (ThermoZoneFanSpeed.FAST, "high"),
        (ThermoZoneFanSpeed.AUTO, "auto"),
    ],
)
async def test_fan_mode_mapping(hass, fan_speed, expected_mode):
    """Test fan mode maps correctly from ThermoZoneFanSpeed."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, fan_speed=fan_speed),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state.attributes["fan_mode"] == expected_mode


async def test_fan_mode_none_when_no_fan_support(hass):
    """Test fan_mode property returns None when zone has no fan (UNKNOWN)."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, fan_speed=ThermoZoneFanSpeed.UNKNOWN),
    ]
    await _setup_entry(hass, mock_zones=zones)

    entity = _get_climate_entity(hass)
    assert entity.fan_mode is None


async def test_fan_mode_not_exposed_when_unknown(hass):
    """Test FAN_MODE feature is not exposed when fan_speed is UNKNOWN."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, fan_speed=ThermoZoneFanSpeed.UNKNOWN),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state is not None
    features = state.attributes["supported_features"]
    assert not features & ClimateEntityFeature.FAN_MODE
    assert "fan_mode" not in state.attributes


async def test_fan_mode_exposed_when_supported(hass):
    """Test FAN_MODE feature is exposed when fan_speed is not UNKNOWN."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, fan_speed=ThermoZoneFanSpeed.AUTO),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state is not None
    features = state.attributes["supported_features"]
    assert features & ClimateEntityFeature.FAN_MODE
    assert "fan_mode" in state.attributes
    assert state.attributes["fan_modes"] == ["off", "low", "medium", "high", "auto"]


# --- Preset mode ---


async def test_preset_mode_jolly(hass):
    """Test preset_mode is 'Jolly' when zone is in JOLLY mode."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, mode=ThermoZoneMode.JOLLY),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state.attributes["preset_mode"] == "Jolly"


async def test_preset_mode_none(hass):
    """Test preset_mode is 'none' when zone is not in JOLLY mode."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, mode=ThermoZoneMode.AUTO),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state.attributes["preset_mode"] == PRESET_NONE


# --- Extra state attributes ---


async def test_extra_state_attributes(hass):
    """Test extra attributes expose dehumidifier and sensor readings."""
    zones = [
        _mock_thermo_zone(
            1,
            "Zone A",
            20.0,
            dehumidifier_enabled=True,
            dehumidifier_setpoint=55.0,
            antifreeze=5.0,
            t1=20.1,
            t2=19.8,
            t3=None,
        ),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    assert state.attributes["dehumidifier_enabled"] is True
    assert state.attributes["dehumidifier_setpoint"] == 55.0
    assert state.attributes["antifreeze"] == 5.0
    assert state.attributes["t1"] == 20.1
    assert state.attributes["t2"] == 19.8
    assert state.attributes["t3"] is None


async def test_extra_state_attributes_none_when_zone_missing(hass):
    """Test extra attributes are absent when zone is missing."""
    zones = [_mock_thermo_zone(1, "Zone A", 20.0)]
    config_entry = await _setup_entry(hass, mock_zones=zones)

    coordinator = config_entry.runtime_data.coordinator
    empty_data = CameDomoticServerData(server_info=_mock_server_info())

    with patch.object(coordinator, "_async_update_data", return_value=empty_data):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("climate.zone_a")
    assert state is not None
    # When zone is missing, extra attributes should not be present
    assert "dehumidifier_enabled" not in state.attributes


# --- Supported features ---


async def test_supported_features_with_fan(hass):
    """Test supported features include FAN_MODE when fan is available."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, fan_speed=ThermoZoneFanSpeed.AUTO),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    expected = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
        | ClimateEntityFeature.FAN_MODE
    )
    assert state.attributes["supported_features"] == expected


async def test_supported_features_without_fan(hass):
    """Test supported features exclude FAN_MODE when fan is UNKNOWN."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, fan_speed=ThermoZoneFanSpeed.UNKNOWN),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get("climate.zone_a")
    expected = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.PRESET_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    assert state.attributes["supported_features"] == expected


# --- set_hvac_mode ---


async def test_set_hvac_mode_off(hass):
    """Test set_hvac_mode(OFF) calls async_set_thermo_zone_mode(OFF)."""
    config_entry = await _setup_entry(hass)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_mode = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": _ENTITY_LIVING_ROOM, ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    coordinator.api.async_set_thermo_zone_mode.assert_awaited_once()
    call_args = coordinator.api.async_set_thermo_zone_mode.call_args
    assert call_args[0][1] == ThermoZoneMode.OFF


async def test_set_hvac_mode_heat(hass):
    """Test set_hvac_mode(HEAT) calls async_set_thermo_zone_mode(MANUAL)."""
    config_entry = await _setup_entry(hass)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_mode = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": _ENTITY_LIVING_ROOM, ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    coordinator.api.async_set_thermo_zone_mode.assert_awaited_once()
    call_args = coordinator.api.async_set_thermo_zone_mode.call_args
    assert call_args[0][1] == ThermoZoneMode.MANUAL


async def test_set_hvac_mode_cool(hass):
    """Test set_hvac_mode(COOL) calls async_set_thermo_zone_mode(MANUAL)."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, season=ThermoZoneSeason.SUMMER),
    ]
    config_entry = await _setup_entry(hass, mock_zones=zones)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_mode = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": "climate.zone_a", ATTR_HVAC_MODE: HVACMode.COOL},
        blocking=True,
    )

    coordinator.api.async_set_thermo_zone_mode.assert_awaited_once()
    call_args = coordinator.api.async_set_thermo_zone_mode.call_args
    assert call_args[0][1] == ThermoZoneMode.MANUAL


async def test_set_hvac_mode_auto(hass):
    """Test set_hvac_mode(AUTO) calls async_set_thermo_zone_mode(AUTO)."""
    config_entry = await _setup_entry(hass)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_mode = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_hvac_mode",
        {"entity_id": _ENTITY_LIVING_ROOM, ATTR_HVAC_MODE: HVACMode.AUTO},
        blocking=True,
    )

    coordinator.api.async_set_thermo_zone_mode.assert_awaited_once()
    call_args = coordinator.api.async_set_thermo_zone_mode.call_args
    assert call_args[0][1] == ThermoZoneMode.AUTO


async def test_set_hvac_mode_zone_missing(hass, caplog):
    """Test set_hvac_mode logs warning when zone is missing."""
    zones = [_mock_thermo_zone(1, "Zone A", 20.0)]
    config_entry = await _setup_entry(hass, mock_zones=zones)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_mode = AsyncMock()

    # Remove the zone from data
    coordinator.data.thermo_zones.clear()
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    # Call directly on the entity since HA may reject service calls for unknown state
    entity = _get_climate_entity(hass)
    await entity.async_set_hvac_mode(HVACMode.OFF)

    coordinator.api.async_set_thermo_zone_mode.assert_not_awaited()
    assert "not found in coordinator data" in caplog.text


async def test_set_hvac_mode_unhandled(hass, caplog):
    """Test set_hvac_mode logs warning for unhandled HVAC mode."""
    zones = [_mock_thermo_zone(1, "Zone A", 20.0)]
    config_entry = await _setup_entry(hass, mock_zones=zones)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_mode = AsyncMock()

    entity = _get_climate_entity(hass)
    await entity.async_set_hvac_mode(HVACMode.FAN_ONLY)

    coordinator.api.async_set_thermo_zone_mode.assert_not_awaited()
    assert "Unhandled HVAC mode" in caplog.text


# --- set_temperature ---


async def test_set_temperature(hass):
    """Test set_temperature calls async_set_thermo_zone_config(MANUAL, temp)."""
    config_entry = await _setup_entry(hass)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_config = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": _ENTITY_LIVING_ROOM, ATTR_TEMPERATURE: 22.5},
        blocking=True,
    )

    coordinator.api.async_set_thermo_zone_config.assert_awaited_once()
    call_args = coordinator.api.async_set_thermo_zone_config.call_args
    assert call_args[0][1] == ThermoZoneMode.MANUAL
    assert call_args[0][2] == 22.5


async def test_set_temperature_switches_to_manual_from_auto(hass):
    """Test set_temperature switches zone from AUTO to MANUAL."""
    zones = [_mock_thermo_zone(1, "Zone A", 20.0, mode=ThermoZoneMode.AUTO)]
    config_entry = await _setup_entry(hass, mock_zones=zones)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_config = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_temperature",
        {"entity_id": "climate.zone_a", ATTR_TEMPERATURE: 25.0},
        blocking=True,
    )

    coordinator.api.async_set_thermo_zone_config.assert_awaited_once()
    call_args = coordinator.api.async_set_thermo_zone_config.call_args
    assert call_args[0][1] == ThermoZoneMode.MANUAL
    assert call_args[0][2] == 25.0


async def test_set_temperature_no_temp_kwarg(hass):
    """Test set_temperature does nothing when temperature kwarg is missing."""
    config_entry = await _setup_entry(hass)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_config = AsyncMock()

    entity = _get_climate_entity(hass)
    await entity.async_set_temperature()

    coordinator.api.async_set_thermo_zone_config.assert_not_awaited()


async def test_set_temperature_zone_missing(hass, caplog):
    """Test set_temperature logs warning when zone is missing."""
    zones = [_mock_thermo_zone(1, "Zone A", 20.0)]
    config_entry = await _setup_entry(hass, mock_zones=zones)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_config = AsyncMock()

    coordinator.data.thermo_zones.clear()
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    entity = _get_climate_entity(hass)
    await entity.async_set_temperature(temperature=22.5)

    coordinator.api.async_set_thermo_zone_config.assert_not_awaited()
    assert "not found in coordinator data" in caplog.text


# --- set_fan_mode ---


async def test_set_fan_mode(hass):
    """Test set_fan_mode calls async_set_thermo_zone_fan_speed with mapped enum."""
    config_entry = await _setup_entry(hass)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_fan_speed = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_fan_mode",
        {"entity_id": _ENTITY_LIVING_ROOM, ATTR_FAN_MODE: "high"},
        blocking=True,
    )

    coordinator.api.async_set_thermo_zone_fan_speed.assert_awaited_once()
    call_args = coordinator.api.async_set_thermo_zone_fan_speed.call_args
    assert call_args[0][1] == ThermoZoneFanSpeed.FAST


async def test_set_fan_mode_zone_missing(hass, caplog):
    """Test set_fan_mode logs warning when zone is missing."""
    zones = [_mock_thermo_zone(1, "Zone A", 20.0)]
    config_entry = await _setup_entry(hass, mock_zones=zones)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_fan_speed = AsyncMock()

    coordinator.data.thermo_zones.clear()
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    entity = _get_climate_entity(hass)
    await entity.async_set_fan_mode("high")

    coordinator.api.async_set_thermo_zone_fan_speed.assert_not_awaited()
    assert "not found in coordinator data" in caplog.text


async def test_set_fan_mode_unknown(hass, caplog):
    """Test set_fan_mode with unknown value logs warning."""
    zones = [_mock_thermo_zone(1, "Zone A", 20.0)]
    config_entry = await _setup_entry(hass, mock_zones=zones)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_fan_speed = AsyncMock()

    entity = _get_climate_entity(hass)
    await entity.async_set_fan_mode("turbo_invalid")

    coordinator.api.async_set_thermo_zone_fan_speed.assert_not_awaited()
    assert "Unknown fan mode: turbo_invalid" in caplog.text


# --- set_preset_mode ---


async def test_set_preset_jolly(hass):
    """Test set_preset_mode('Jolly') calls async_set_thermo_zone_mode(JOLLY)."""
    config_entry = await _setup_entry(hass)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_mode = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": _ENTITY_LIVING_ROOM, ATTR_PRESET_MODE: "Jolly"},
        blocking=True,
    )

    coordinator.api.async_set_thermo_zone_mode.assert_awaited_once()
    call_args = coordinator.api.async_set_thermo_zone_mode.call_args
    assert call_args[0][1] == ThermoZoneMode.JOLLY


async def test_set_preset_none_from_jolly(hass):
    """Test set_preset_mode('none') from JOLLY reverts to AUTO."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, mode=ThermoZoneMode.JOLLY),
    ]
    config_entry = await _setup_entry(hass, mock_zones=zones)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_mode = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.zone_a", ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )

    coordinator.api.async_set_thermo_zone_mode.assert_awaited_once()
    call_args = coordinator.api.async_set_thermo_zone_mode.call_args
    assert call_args[0][1] == ThermoZoneMode.AUTO


async def test_set_preset_none_when_not_jolly(hass):
    """Test set_preset_mode('none') is a no-op when not in JOLLY mode."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, mode=ThermoZoneMode.AUTO),
    ]
    config_entry = await _setup_entry(hass, mock_zones=zones)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_mode = AsyncMock()

    await hass.services.async_call(
        "climate",
        "set_preset_mode",
        {"entity_id": "climate.zone_a", ATTR_PRESET_MODE: PRESET_NONE},
        blocking=True,
    )

    coordinator.api.async_set_thermo_zone_mode.assert_not_awaited()


async def test_set_preset_zone_missing(hass, caplog):
    """Test set_preset_mode logs warning when zone is missing."""
    zones = [_mock_thermo_zone(1, "Zone A", 20.0)]
    config_entry = await _setup_entry(hass, mock_zones=zones)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_mode = AsyncMock()

    coordinator.data.thermo_zones.clear()
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    entity = _get_climate_entity(hass)
    await entity.async_set_preset_mode("Jolly")

    coordinator.api.async_set_thermo_zone_mode.assert_not_awaited()
    assert "not found in coordinator data" in caplog.text


# --- turn_on / turn_off ---


async def test_turn_on(hass):
    """Test turn_on sets zone to AUTO mode."""
    zones = [_mock_thermo_zone(1, "Zone A", 20.0, mode=ThermoZoneMode.OFF)]
    config_entry = await _setup_entry(hass, mock_zones=zones)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_mode = AsyncMock()

    await hass.services.async_call(
        "climate",
        "turn_on",
        {"entity_id": "climate.zone_a"},
        blocking=True,
    )

    coordinator.api.async_set_thermo_zone_mode.assert_awaited_once()
    call_args = coordinator.api.async_set_thermo_zone_mode.call_args
    assert call_args[0][1] == ThermoZoneMode.AUTO


async def test_turn_off(hass):
    """Test turn_off sets zone to OFF mode."""
    config_entry = await _setup_entry(hass)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_mode = AsyncMock()

    await hass.services.async_call(
        "climate",
        "turn_off",
        {"entity_id": _ENTITY_LIVING_ROOM},
        blocking=True,
    )

    coordinator.api.async_set_thermo_zone_mode.assert_awaited_once()
    call_args = coordinator.api.async_set_thermo_zone_mode.call_args
    assert call_args[0][1] == ThermoZoneMode.OFF


async def test_turn_on_zone_missing(hass, caplog):
    """Test turn_on logs warning when zone is missing."""
    zones = [_mock_thermo_zone(1, "Zone A", 20.0)]
    config_entry = await _setup_entry(hass, mock_zones=zones)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_mode = AsyncMock()

    coordinator.data.thermo_zones.clear()
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    entity = _get_climate_entity(hass)
    await entity.async_turn_on()

    coordinator.api.async_set_thermo_zone_mode.assert_not_awaited()
    assert "not found in coordinator data" in caplog.text


async def test_turn_off_zone_missing(hass, caplog):
    """Test turn_off logs warning when zone is missing."""
    zones = [_mock_thermo_zone(1, "Zone A", 20.0)]
    config_entry = await _setup_entry(hass, mock_zones=zones)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_zone_mode = AsyncMock()

    coordinator.data.thermo_zones.clear()
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    entity = _get_climate_entity(hass)
    await entity.async_turn_off()

    coordinator.api.async_set_thermo_zone_mode.assert_not_awaited()
    assert "not found in coordinator data" in caplog.text


# --- Availability ---


async def test_unavailable_when_disconnected(hass):
    """Test the climate entity becomes unavailable when server disconnects."""
    config_entry = await _setup_entry(hass)

    state = hass.states.get(_ENTITY_LIVING_ROOM)
    assert state is not None
    assert state.state != "unavailable"

    coordinator = config_entry.runtime_data.coordinator
    coordinator._server_available = False  # noqa: SLF001
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(_ENTITY_LIVING_ROOM)
    assert state is not None
    assert state.state == "unavailable"
