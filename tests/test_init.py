"""Test CAME Domotic Unofficial setup process."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_SCAN_INTERVAL
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic_unofficial import async_remove_config_entry_device
from custom_components.came_domotic_unofficial.const import DOMAIN
from custom_components.came_domotic_unofficial.coordinator import (
    CameDomoticUnofficialDataUpdateCoordinator,
)

from .const import MOCK_CONFIG


async def test_setup_and_unload_entry(hass, bypass_get_data):
    """Test entry setup and unload."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None
    assert isinstance(
        config_entry.runtime_data.coordinator,
        CameDomoticUnofficialDataUpdateCoordinator,
    )

    # Unload the entry
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_communication_error(hass, error_on_get_data):
    """Test ConfigEntryNotReady when API raises a communication error during setup."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_auth_error(hass, auth_error_on_get_data):
    """Test ConfigEntryAuthFailed when API raises auth error during setup."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_options_update_triggers_reload(hass, bypass_get_data):
    """Test that updating options triggers a reload."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    # Update options triggers _async_update_listener -> reload
    hass.config_entries.async_update_entry(
        config_entry, options={CONF_SCAN_INTERVAL: 60}
    )
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


async def test_remove_config_entry_device(hass, bypass_get_data):
    """Test removing a device entry always returns True."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await async_remove_config_entry_device(hass, config_entry, None)
    assert result is True
