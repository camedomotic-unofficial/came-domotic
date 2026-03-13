"""Test CAME Domotic scene platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic.const import DOMAIN
from custom_components.came_domotic.models import CameDomoticServerData

from .conftest import _mock_scenario, _mock_server_info
from .const import MOCK_CONFIG

_API_CLIENT = "custom_components.came_domotic.api.CameDomoticApiClient"

_COORDINATOR = (
    "custom_components.came_domotic.coordinator.CameDomoticDataUpdateCoordinator"
)


async def _setup_entry(hass, mock_scenarios):
    """Set up a config entry with the given mock scenarios list."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            return_value=_mock_server_info(),
        ),
        patch(f"{_API_CLIENT}.async_get_thermo_zones", return_value=[]),
        patch(
            f"{_API_CLIENT}.async_get_scenarios",
            return_value=mock_scenarios,
        ),
        patch(f"{_API_CLIENT}.async_get_openings", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_lights", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_digital_inputs", return_value=[]),
        patch(
            f"{_API_CLIENT}.async_get_floors",
            return_value=[],
        ),
        patch(
            f"{_API_CLIENT}.async_get_rooms",
            return_value=[],
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch(f"{_COORDINATOR}.start_long_poll"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


async def test_scenario_scenes_created(hass, bypass_get_data):
    """Test that one scene entity is created per scenario."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "scene"
    ]
    assert len(entries) == 2


async def test_scenario_scene_unique_id(hass, bypass_get_data):
    """Test scene unique IDs follow the expected pattern."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "scene"
    }
    assert unique_ids == {
        "test_scenario_10",
        "test_scenario_20",
    }


async def test_scenario_scene_state(hass, bypass_get_data):
    """Test scene entities exist with expected names."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    good_morning = hass.states.get("scene.good_morning")
    assert good_morning is not None

    good_night = hass.states.get("scene.good_night")
    assert good_night is not None


async def test_scenario_scene_extra_attributes(hass, bypass_get_data):
    """Test scene exposes extra scenario attributes."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # User-defined scenario
    state = hass.states.get("scene.good_morning")
    assert state is not None
    assert state.attributes["scenario_status"] == "OFF"
    assert state.attributes["user_defined"] is True

    # System-defined scenario
    state = hass.states.get("scene.good_night")
    assert state is not None
    assert state.attributes["user_defined"] is False


async def test_no_scenarios(hass):
    """Test no scene entities created when there are no scenarios."""
    config_entry = await _setup_entry(hass, [])

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "scene"
    ]
    assert len(entries) == 0


async def test_scenario_scene_activate(hass):
    """Test activating a scene calls async_activate_scenario on the API."""
    scenarios = [_mock_scenario(10, "Good Morning")]
    config_entry = await _setup_entry(hass, scenarios)

    coordinator = config_entry.runtime_data.coordinator
    mock_activate = AsyncMock()

    with patch.object(coordinator.api, "async_activate_scenario", mock_activate):
        await hass.services.async_call(
            "scene",
            "turn_on",
            {"entity_id": "scene.good_morning"},
            blocking=True,
        )

    mock_activate.assert_awaited_once()
    # Verify the correct scenario object was passed
    called_scenario = mock_activate.call_args[0][0]
    assert called_scenario.id == 10


async def test_scenario_scene_activate_not_found(hass):
    """Test activating a scene when scenario disappears from data."""
    scenarios = [_mock_scenario(10, "Good Morning")]
    config_entry = await _setup_entry(hass, scenarios)

    # Remove the scenario from coordinator data
    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.scenarios.clear()

    # Should not raise — just logs a warning
    await hass.services.async_call(
        "scene",
        "turn_on",
        {"entity_id": "scene.good_morning"},
        blocking=True,
    )


async def test_scenario_scene_zone_not_found_attributes(hass):
    """Test scene returns no extra attributes when scenario disappears."""
    scenarios = [_mock_scenario(10, "Good Morning")]
    config_entry = await _setup_entry(hass, scenarios)

    # Simulate scenario disappearing
    coordinator = config_entry.runtime_data.coordinator
    empty_data = CameDomoticServerData(
        server_info=_mock_server_info(),
        thermo_zones={},
        scenarios={},
    )

    with patch.object(
        coordinator,
        "_async_update_data",
        return_value=empty_data,
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("scene.good_morning")
    assert state is not None
    # Extra attributes should not contain scenario-specific keys
    assert "scenario_status" not in state.attributes
