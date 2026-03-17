"""Test CAME Domotic select platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from aiocamedomotic.models import ThermoZoneSeason
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

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

_ENTITY_ID = "select.came_eti_domo_server_192_168_1_100_thermo_season"


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


async def test_thermo_season_select_created(hass):
    """Test that select entity is created when thermo zones exist."""
    await _setup_entry(hass)

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == "test" and e.domain == "select"
    ]
    assert len(entries) == 1
    assert entries[0].unique_id == "test_thermo_season"


async def test_thermo_season_select_not_created_when_no_zones(hass):
    """Test that no select entity is created when thermo zones are empty."""
    await _setup_entry(hass, mock_zones=[])

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == "test" and e.domain == "select"
    ]
    assert len(entries) == 0


async def test_thermo_season_select_current_option(hass):
    """Test current_option reads season from first thermo zone."""
    await _setup_entry(hass)

    state = hass.states.get(_ENTITY_ID)
    assert state is not None
    assert state.state == "winter"


async def test_thermo_season_select_current_option_summer(hass):
    """Test current_option with summer season."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, season=ThermoZoneSeason.SUMMER),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get(_ENTITY_ID)
    assert state is not None
    assert state.state == "summer"


async def test_thermo_season_select_current_option_plant_off(hass):
    """Test current_option with plant_off season."""
    zones = [
        _mock_thermo_zone(1, "Zone A", 20.0, season=ThermoZoneSeason.PLANT_OFF),
    ]
    await _setup_entry(hass, mock_zones=zones)

    state = hass.states.get(_ENTITY_ID)
    assert state is not None
    assert state.state == "plant_off"


async def test_thermo_season_select_current_option_no_zones(hass):
    """Test current_option returns unknown when zones disappear from data."""
    config_entry = await _setup_entry(hass)

    coordinator = config_entry.runtime_data.coordinator
    empty_data = CameDomoticServerData(server_info=_mock_server_info())

    with patch.object(
        coordinator,
        "_async_update_data",
        return_value=empty_data,
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get(_ENTITY_ID)
    assert state is not None
    assert state.state == "unknown"


async def test_thermo_season_select_option_winter(hass):
    """Test selecting winter season calls the API."""
    config_entry = await _setup_entry(hass)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_season = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": _ENTITY_ID,
            "option": "winter",
        },
        blocking=True,
    )

    coordinator.api.async_set_thermo_season.assert_awaited_once_with(
        ThermoZoneSeason.WINTER
    )


async def test_thermo_season_select_option_summer(hass):
    """Test selecting summer season calls the API."""
    config_entry = await _setup_entry(hass)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_season = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": _ENTITY_ID,
            "option": "summer",
        },
        blocking=True,
    )

    coordinator.api.async_set_thermo_season.assert_awaited_once_with(
        ThermoZoneSeason.SUMMER
    )


async def test_thermo_season_select_option_plant_off(hass):
    """Test selecting plant_off season calls the API."""
    config_entry = await _setup_entry(hass)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_season = AsyncMock()
    coordinator.async_request_refresh = AsyncMock()

    await hass.services.async_call(
        "select",
        "select_option",
        {
            "entity_id": _ENTITY_ID,
            "option": "plant_off",
        },
        blocking=True,
    )

    coordinator.api.async_set_thermo_season.assert_awaited_once_with(
        ThermoZoneSeason.PLANT_OFF
    )


async def test_thermo_season_select_options_list(hass):
    """Test the select entity exposes the correct options."""
    await _setup_entry(hass)

    state = hass.states.get(_ENTITY_ID)
    assert state is not None
    assert state.attributes["options"] == ["winter", "summer", "plant_off"]


async def test_thermo_season_select_unknown_option(hass, caplog):
    """Test selecting an unknown option logs warning and does not call API."""
    config_entry = await _setup_entry(hass)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.api.async_set_thermo_season = AsyncMock()

    # Call async_select_option directly to bypass HA option validation
    from custom_components.came_domotic.select import CameDomoticThermoSeasonSelect

    registry = er.async_get(hass)
    entry = next(
        e
        for e in registry.entities.values()
        if e.config_entry_id == "test" and e.domain == "select"
    )
    entity = hass.data["entity_components"]["select"].get_entity(entry.entity_id)
    assert isinstance(entity, CameDomoticThermoSeasonSelect)

    await entity.async_select_option("invalid_season")
    coordinator.api.async_set_thermo_season.assert_not_awaited()
    assert "Unknown thermo season option: invalid_season" in caplog.text


async def test_thermo_season_select_unavailable_when_disconnected(hass):
    """Test the select entity becomes unavailable when the server disconnects."""
    config_entry = await _setup_entry(hass)

    state = hass.states.get(_ENTITY_ID)
    assert state is not None
    assert state.state != "unavailable"

    coordinator = config_entry.runtime_data.coordinator
    coordinator._server_available = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(_ENTITY_ID)
    assert state is not None
    assert state.state == "unavailable"
