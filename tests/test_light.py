"""Test CAME Domotic light platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from aiocamedomotic.models import LightStatus, LightType
from homeassistant.components.light import ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ColorMode
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic.api import (
    CameDomoticApiClientCommunicationError,
)
from custom_components.came_domotic.const import DOMAIN
from custom_components.came_domotic.models import CameDomoticServerData

from .conftest import _mock_light, _mock_server_info, _mock_topology
from .const import MOCK_CONFIG

_API_CLIENT = "custom_components.came_domotic.api.CameDomoticApiClient"

_COORDINATOR = (
    "custom_components.came_domotic.coordinator.CameDomoticDataUpdateCoordinator"
)


async def _setup_entry(hass, mock_lights):
    """Set up a config entry with the given mock lights list."""
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
        patch(
            f"{_API_CLIENT}.async_get_lights",
            return_value=mock_lights,
        ),
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


async def test_light_entities_created(hass, bypass_get_data):
    """Test that one light entity is created per light."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "light"
    ]
    assert len(entries) == 3


async def test_light_unique_id(hass, bypass_get_data):
    """Test light unique IDs follow the expected pattern."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "light"
    }
    assert unique_ids == {
        "test_light_300",
        "test_light_301",
        "test_light_302",
    }


async def test_light_state(hass, bypass_get_data):
    """Test light entities exist with expected entity IDs."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    hallway = hass.states.get("light.hallway_light")
    assert hallway is not None

    dimmer = hass.states.get("light.living_room_dimmer")
    assert dimmer is not None

    rgb = hass.states.get("light.bedroom_rgb")
    assert rgb is not None


async def test_no_lights(hass):
    """Test no light entities created when there are no lights."""
    config_entry = await _setup_entry(hass, [])

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "light"
    ]
    assert len(entries) == 0


# --- State properties ---


async def test_light_is_on(hass):
    """Test is_on returns True when status is ON."""
    lights = [
        _mock_light(300, "Hallway Light", status=LightStatus.ON),
    ]
    await _setup_entry(hass, lights)

    state = hass.states.get("light.hallway_light")
    assert state is not None
    assert state.state == "on"


async def test_light_is_off(hass):
    """Test is_on returns False when status is OFF."""
    lights = [
        _mock_light(300, "Hallway Light", status=LightStatus.OFF),
    ]
    await _setup_entry(hass, lights)

    state = hass.states.get("light.hallway_light")
    assert state is not None
    assert state.state == "off"


async def test_light_is_on_not_found(hass):
    """Test is_on returns None when light disappears from data."""
    lights = [_mock_light(300, "Hallway Light")]
    config_entry = await _setup_entry(hass, lights)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.lights.clear()

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

    state = hass.states.get("light.hallway_light")
    assert state is not None


async def test_light_brightness_dimmer(hass):
    """Test brightness converts CAME 75% to HA scale (191)."""
    lights = [
        _mock_light(
            301,
            "Living Room Dimmer",
            status=LightStatus.ON,
            light_type=LightType.DIMMER,
            perc=75,
        ),
    ]
    await _setup_entry(hass, lights)

    state = hass.states.get("light.living_room_dimmer")
    assert state is not None
    # round(75 * 255 / 100) = 191
    assert state.attributes[ATTR_BRIGHTNESS] == 191


async def test_light_brightness_none_for_step_step(hass):
    """Test STEP_STEP light has no brightness attribute."""
    lights = [
        _mock_light(300, "Hallway Light", status=LightStatus.ON),
    ]
    await _setup_entry(hass, lights)

    state = hass.states.get("light.hallway_light")
    assert state is not None
    assert ATTR_BRIGHTNESS not in state.attributes


async def test_light_brightness_not_found(hass):
    """Test brightness returns None when light disappears from data."""
    lights = [
        _mock_light(
            301,
            "Living Room Dimmer",
            light_type=LightType.DIMMER,
            perc=75,
        ),
    ]
    config_entry = await _setup_entry(hass, lights)

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

    state = hass.states.get("light.living_room_dimmer")
    assert state is not None
    assert state.attributes.get(ATTR_BRIGHTNESS) is None


async def test_light_brightness_none_when_perc_is_none(hass):
    """Test brightness returns None when light.perc is None."""
    lights = [
        _mock_light(
            301,
            "Living Room Dimmer",
            status=LightStatus.ON,
            light_type=LightType.DIMMER,
            perc=None,
        ),
    ]
    await _setup_entry(hass, lights)

    state = hass.states.get("light.living_room_dimmer")
    assert state is not None
    assert state.attributes.get(ATTR_BRIGHTNESS) is None


async def test_light_rgb_color(hass):
    """Test RGB color is returned as tuple for RGB lights."""
    lights = [
        _mock_light(
            302,
            "Bedroom RGB",
            status=LightStatus.ON,
            light_type=LightType.RGB,
            perc=50,
            rgb=[255, 128, 0],
        ),
    ]
    await _setup_entry(hass, lights)

    state = hass.states.get("light.bedroom_rgb")
    assert state is not None
    assert state.attributes[ATTR_RGB_COLOR] == (255, 128, 0)


async def test_light_rgb_color_none_when_rgb_is_none(hass):
    """Test rgb_color returns None when light.rgb is None."""
    lights = [
        _mock_light(
            302,
            "Bedroom RGB",
            status=LightStatus.ON,
            light_type=LightType.RGB,
            perc=50,
            rgb=None,
        ),
    ]
    await _setup_entry(hass, lights)

    state = hass.states.get("light.bedroom_rgb")
    assert state is not None
    assert state.attributes.get(ATTR_RGB_COLOR) is None


async def test_light_rgb_color_none_for_dimmer(hass):
    """Test DIMMER light has no rgb_color attribute."""
    lights = [
        _mock_light(
            301,
            "Living Room Dimmer",
            status=LightStatus.ON,
            light_type=LightType.DIMMER,
            perc=75,
        ),
    ]
    await _setup_entry(hass, lights)

    state = hass.states.get("light.living_room_dimmer")
    assert state is not None
    assert ATTR_RGB_COLOR not in state.attributes


async def test_light_rgb_color_not_found(hass):
    """Test rgb_color returns None when light disappears from data."""
    lights = [
        _mock_light(
            302,
            "Bedroom RGB",
            light_type=LightType.RGB,
            perc=50,
            rgb=[255, 128, 0],
        ),
    ]
    config_entry = await _setup_entry(hass, lights)

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

    state = hass.states.get("light.bedroom_rgb")
    assert state is not None
    assert state.attributes.get(ATTR_RGB_COLOR) is None


# --- Color mode ---


async def test_light_color_mode_onoff(hass):
    """Test STEP_STEP light has ColorMode.ONOFF."""
    lights = [
        _mock_light(300, "Hallway Light", status=LightStatus.ON),
    ]
    await _setup_entry(hass, lights)

    state = hass.states.get("light.hallway_light")
    assert state is not None
    assert state.attributes["color_mode"] == ColorMode.ONOFF


async def test_light_color_mode_brightness(hass):
    """Test DIMMER light has ColorMode.BRIGHTNESS."""
    lights = [
        _mock_light(
            301,
            "Living Room Dimmer",
            status=LightStatus.ON,
            light_type=LightType.DIMMER,
            perc=75,
        ),
    ]
    await _setup_entry(hass, lights)

    state = hass.states.get("light.living_room_dimmer")
    assert state is not None
    assert state.attributes["color_mode"] == ColorMode.BRIGHTNESS


async def test_light_color_mode_rgb(hass):
    """Test RGB light has ColorMode.RGB."""
    lights = [
        _mock_light(
            302,
            "Bedroom RGB",
            status=LightStatus.ON,
            light_type=LightType.RGB,
            perc=50,
            rgb=[255, 128, 0],
        ),
    ]
    await _setup_entry(hass, lights)

    state = hass.states.get("light.bedroom_rgb")
    assert state is not None
    assert state.attributes["color_mode"] == ColorMode.RGB


async def test_light_supported_color_modes(hass):
    """Test each light type has exactly one supported color mode."""
    lights = [
        _mock_light(300, "Hallway Light", status=LightStatus.ON),
        _mock_light(
            301,
            "Living Room Dimmer",
            status=LightStatus.ON,
            light_type=LightType.DIMMER,
            perc=75,
        ),
        _mock_light(
            302,
            "Bedroom RGB",
            status=LightStatus.ON,
            light_type=LightType.RGB,
            perc=50,
            rgb=[255, 128, 0],
        ),
    ]
    await _setup_entry(hass, lights)

    hallway = hass.states.get("light.hallway_light")
    assert hallway.attributes["supported_color_modes"] == [ColorMode.ONOFF]

    dimmer = hass.states.get("light.living_room_dimmer")
    assert dimmer.attributes["supported_color_modes"] == [ColorMode.BRIGHTNESS]

    rgb = hass.states.get("light.bedroom_rgb")
    assert rgb.attributes["supported_color_modes"] == [ColorMode.RGB]


# --- Light actions ---


async def test_light_turn_on(hass):
    """Test turning on a light calls async_set_light_status with ON."""
    lights = [_mock_light(300, "Hallway Light")]
    config_entry = await _setup_entry(hass, lights)

    coordinator = config_entry.runtime_data.coordinator
    mock_set_status = AsyncMock()

    with patch.object(coordinator.api, "async_set_light_status", mock_set_status):
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": "light.hallway_light"},
            blocking=True,
        )

    mock_set_status.assert_awaited_once()
    called_light = mock_set_status.call_args[0][0]
    called_status = mock_set_status.call_args[0][1]
    assert called_light.act_id == 300
    assert called_status == LightStatus.ON
    # No brightness or RGB when not provided
    assert mock_set_status.call_args[1]["brightness"] is None
    assert mock_set_status.call_args[1]["rgb"] is None


async def test_light_turn_on_with_brightness(hass):
    """Test turning on with brightness converts HA scale to CAME scale."""
    lights = [
        _mock_light(
            301,
            "Living Room Dimmer",
            light_type=LightType.DIMMER,
            perc=0,
        ),
    ]
    config_entry = await _setup_entry(hass, lights)

    coordinator = config_entry.runtime_data.coordinator
    mock_set_status = AsyncMock()

    with patch.object(coordinator.api, "async_set_light_status", mock_set_status):
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": "light.living_room_dimmer", ATTR_BRIGHTNESS: 191},
            blocking=True,
        )

    mock_set_status.assert_awaited_once()
    # round(191 * 100 / 255) = 75
    assert mock_set_status.call_args[1]["brightness"] == 75


async def test_light_turn_on_with_rgb(hass):
    """Test turning on with RGB passes color as list."""
    lights = [
        _mock_light(
            302,
            "Bedroom RGB",
            light_type=LightType.RGB,
            perc=50,
            rgb=[0, 0, 0],
        ),
    ]
    config_entry = await _setup_entry(hass, lights)

    coordinator = config_entry.runtime_data.coordinator
    mock_set_status = AsyncMock()

    with patch.object(coordinator.api, "async_set_light_status", mock_set_status):
        await hass.services.async_call(
            "light",
            "turn_on",
            {"entity_id": "light.bedroom_rgb", ATTR_RGB_COLOR: (255, 128, 0)},
            blocking=True,
        )

    mock_set_status.assert_awaited_once()
    assert mock_set_status.call_args[1]["rgb"] == [255, 128, 0]


async def test_light_turn_on_with_brightness_and_rgb(hass):
    """Test turning on with both brightness and RGB."""
    lights = [
        _mock_light(
            302,
            "Bedroom RGB",
            light_type=LightType.RGB,
            perc=0,
            rgb=[0, 0, 0],
        ),
    ]
    config_entry = await _setup_entry(hass, lights)

    coordinator = config_entry.runtime_data.coordinator
    mock_set_status = AsyncMock()

    with patch.object(coordinator.api, "async_set_light_status", mock_set_status):
        await hass.services.async_call(
            "light",
            "turn_on",
            {
                "entity_id": "light.bedroom_rgb",
                ATTR_BRIGHTNESS: 128,
                ATTR_RGB_COLOR: (255, 0, 0),
            },
            blocking=True,
        )

    mock_set_status.assert_awaited_once()
    # round(128 * 100 / 255) = 50
    assert mock_set_status.call_args[1]["brightness"] == 50
    assert mock_set_status.call_args[1]["rgb"] == [255, 0, 0]


async def test_light_turn_off(hass):
    """Test turning off a light calls async_set_light_status with OFF."""
    lights = [_mock_light(300, "Hallway Light", status=LightStatus.ON)]
    config_entry = await _setup_entry(hass, lights)

    coordinator = config_entry.runtime_data.coordinator
    mock_set_status = AsyncMock()

    with patch.object(coordinator.api, "async_set_light_status", mock_set_status):
        await hass.services.async_call(
            "light",
            "turn_off",
            {"entity_id": "light.hallway_light"},
            blocking=True,
        )

    mock_set_status.assert_awaited_once()
    called_status = mock_set_status.call_args[0][1]
    assert called_status == LightStatus.OFF


# --- Not-found edge cases ---


async def test_light_turn_on_not_found(hass):
    """Test turning on a light when it disappears does not raise."""
    lights = [_mock_light(300, "Hallway Light")]
    config_entry = await _setup_entry(hass, lights)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.lights.clear()

    # Should not raise — just logs a warning
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": "light.hallway_light"},
        blocking=True,
    )


async def test_light_turn_off_not_found(hass):
    """Test turning off a light when it disappears does not raise."""
    lights = [_mock_light(300, "Hallway Light", status=LightStatus.ON)]
    config_entry = await _setup_entry(hass, lights)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.lights.clear()

    await hass.services.async_call(
        "light",
        "turn_off",
        {"entity_id": "light.hallway_light"},
        blocking=True,
    )


# --- Extra attributes ---


async def test_light_extra_attributes(hass):
    """Test light exposes extra light_type attribute."""
    lights = [_mock_light(300, "Hallway Light", status=LightStatus.ON)]
    await _setup_entry(hass, lights)

    state = hass.states.get("light.hallway_light")
    assert state is not None
    assert state.attributes["light_type"] == "STEP_STEP"


async def test_light_extra_attributes_dimmer(hass):
    """Test dimmer light exposes DIMMER as light_type."""
    lights = [
        _mock_light(
            301,
            "Living Room Dimmer",
            status=LightStatus.ON,
            light_type=LightType.DIMMER,
            perc=75,
        ),
    ]
    await _setup_entry(hass, lights)

    state = hass.states.get("light.living_room_dimmer")
    assert state is not None
    assert state.attributes["light_type"] == "DIMMER"


async def test_light_extra_attributes_not_found(hass):
    """Test light returns no extra attributes when light disappears."""
    lights = [_mock_light(300, "Hallway Light")]
    config_entry = await _setup_entry(hass, lights)

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

    state = hass.states.get("light.hallway_light")
    assert state is not None
    assert "light_type" not in state.attributes


# --- Optimistic state updates ---


class TestLightOptimisticState:
    """Tests for optimistic state update behaviour on lights."""

    async def test_light_turn_on_optimistic_state(self, hass):
        """Test state shows 'on' immediately after successful turn_on."""
        lights = [_mock_light(300, "Hallway Light", status=LightStatus.OFF)]
        config_entry = await _setup_entry(hass, lights)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_set_light_status", AsyncMock()):
            await hass.services.async_call(
                "light",
                "turn_on",
                {"entity_id": "light.hallway_light"},
                blocking=True,
            )

        state = hass.states.get("light.hallway_light")
        assert state is not None
        assert state.state == "on"

    async def test_light_turn_off_optimistic_state(self, hass):
        """Test state shows 'off' immediately after successful turn_off."""
        lights = [_mock_light(300, "Hallway Light", status=LightStatus.ON)]
        config_entry = await _setup_entry(hass, lights)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_set_light_status", AsyncMock()):
            await hass.services.async_call(
                "light",
                "turn_off",
                {"entity_id": "light.hallway_light"},
                blocking=True,
            )

        state = hass.states.get("light.hallway_light")
        assert state is not None
        assert state.state == "off"

    async def test_light_turn_on_with_brightness_optimistic(self, hass):
        """Test brightness updates immediately after successful turn_on."""
        lights = [
            _mock_light(
                301,
                "Living Room Dimmer",
                status=LightStatus.OFF,
                light_type=LightType.DIMMER,
                perc=0,
            ),
        ]
        config_entry = await _setup_entry(hass, lights)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_set_light_status", AsyncMock()):
            await hass.services.async_call(
                "light",
                "turn_on",
                {"entity_id": "light.living_room_dimmer", ATTR_BRIGHTNESS: 191},
                blocking=True,
            )

        state = hass.states.get("light.living_room_dimmer")
        assert state is not None
        assert state.state == "on"
        assert state.attributes[ATTR_BRIGHTNESS] == 191

    async def test_light_turn_on_with_rgb_optimistic(self, hass):
        """Test rgb_color updates immediately after successful turn_on."""
        lights = [
            _mock_light(
                302,
                "Bedroom RGB",
                status=LightStatus.OFF,
                light_type=LightType.RGB,
                perc=50,
                rgb=[0, 0, 0],
            ),
        ]
        config_entry = await _setup_entry(hass, lights)

        coordinator = config_entry.runtime_data.coordinator

        with patch.object(coordinator.api, "async_set_light_status", AsyncMock()):
            await hass.services.async_call(
                "light",
                "turn_on",
                {"entity_id": "light.bedroom_rgb", ATTR_RGB_COLOR: (255, 128, 0)},
                blocking=True,
            )

        state = hass.states.get("light.bedroom_rgb")
        assert state is not None
        assert state.state == "on"
        assert state.attributes[ATTR_RGB_COLOR] == (255, 128, 0)

    async def test_light_optimistic_cleared_on_coordinator_update(self, hass):
        """Test optimistic state is cleared when coordinator data catches up."""
        lights = [_mock_light(300, "Hallway Light", status=LightStatus.OFF)]
        config_entry = await _setup_entry(hass, lights)

        coordinator = config_entry.runtime_data.coordinator

        # Set optimistic state
        with patch.object(coordinator.api, "async_set_light_status", AsyncMock()):
            await hass.services.async_call(
                "light",
                "turn_on",
                {"entity_id": "light.hallway_light"},
                blocking=True,
            )

        state = hass.states.get("light.hallway_light")
        assert state.state == "on"

        # Simulate server catching up: light status changes to ON
        coordinator.data.lights[300].status = LightStatus.ON
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

        # State still "on" from real data, but optimistic is cleared
        state = hass.states.get("light.hallway_light")
        assert state.state == "on"

        # Push light back to OFF to prove optimistic was truly cleared
        coordinator.data.lights[300].status = LightStatus.OFF
        coordinator.async_set_updated_data(coordinator.data)
        await hass.async_block_till_done()

        state = hass.states.get("light.hallway_light")
        assert state.state == "off"

    async def test_light_turn_on_api_error_no_optimistic(self, hass):
        """Test no optimistic update when API call fails."""
        lights = [_mock_light(300, "Hallway Light", status=LightStatus.OFF)]
        config_entry = await _setup_entry(hass, lights)

        coordinator = config_entry.runtime_data.coordinator
        mock_set_status = AsyncMock(
            side_effect=CameDomoticApiClientCommunicationError("fail"),
        )

        with (
            patch.object(coordinator.api, "async_set_light_status", mock_set_status),
            pytest.raises(CameDomoticApiClientCommunicationError),
        ):
            await hass.services.async_call(
                "light",
                "turn_on",
                {"entity_id": "light.hallway_light"},
                blocking=True,
            )

        state = hass.states.get("light.hallway_light")
        assert state is not None
        assert state.state == "off"

    async def test_light_turn_off_api_error_no_optimistic(self, hass):
        """Test no optimistic update when API call fails on turn_off."""
        lights = [_mock_light(300, "Hallway Light", status=LightStatus.ON)]
        config_entry = await _setup_entry(hass, lights)

        coordinator = config_entry.runtime_data.coordinator
        mock_set_status = AsyncMock(
            side_effect=CameDomoticApiClientCommunicationError("fail"),
        )

        with (
            patch.object(coordinator.api, "async_set_light_status", mock_set_status),
            pytest.raises(CameDomoticApiClientCommunicationError),
        ):
            await hass.services.async_call(
                "light",
                "turn_off",
                {"entity_id": "light.hallway_light"},
                blocking=True,
            )

        state = hass.states.get("light.hallway_light")
        assert state is not None
        assert state.state == "on"
