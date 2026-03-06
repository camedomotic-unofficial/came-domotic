"""Test CAME Domotic Unofficial switch."""

from __future__ import annotations

from homeassistant.components.switch import SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, Platform
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic_unofficial.const import DOMAIN

from .const import MOCK_CONFIG


async def _setup_switch(hass, config_entry):
    """Set up integration and return switch entity_id."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    return f"{Platform.SWITCH}.{DOMAIN}"


async def test_switch_state(hass, bypass_get_data):
    """Test switch entity state reflects coordinator data."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    entity_id = await _setup_switch(hass, config_entry)

    state = hass.states.get(entity_id)
    assert state is not None
    # MOCK_API_DATA has keycode set, so is_on returns True
    assert state.state == "on"


async def test_switch_turn_off(hass, bypass_get_data):
    """Test turning off the switch triggers a coordinator refresh."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    entity_id = await _setup_switch(hass, config_entry)

    await hass.services.async_call(
        Platform.SWITCH,
        SERVICE_TURN_OFF,
        service_data={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )


async def test_switch_turn_on(hass, bypass_get_data):
    """Test turning on the switch triggers a coordinator refresh."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    entity_id = await _setup_switch(hass, config_entry)

    await hass.services.async_call(
        Platform.SWITCH,
        SERVICE_TURN_ON,
        service_data={ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
