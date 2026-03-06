"""Test CAME Domotic Unofficial binary sensor."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.const import Platform
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic_unofficial.const import DOMAIN

from .const import MOCK_CONFIG

_API_CLIENT = (
    "custom_components.came_domotic_unofficial.api." "CameDomoticUnofficialApiClient"
)


async def test_binary_sensor_state_on(hass, bypass_get_data):
    """Test binary sensor is on when keycode is present."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity_id = f"{Platform.BINARY_SENSOR}.{DOMAIN}_connectivity"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


async def test_binary_sensor_state_off(hass):
    """Test binary sensor is off when keycode is None."""
    mock_data = {
        "keycode": None,
        "software_version": "1.2.3",
        "server_type": "ETI/Domo",
        "board": "board_v1",
    }
    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(f"{_API_CLIENT}.async_get_data", return_value=mock_data),
        patch(f"{_API_CLIENT}.async_dispose"),
    ):
        config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = f"{Platform.BINARY_SENSOR}.{DOMAIN}_connectivity"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"
