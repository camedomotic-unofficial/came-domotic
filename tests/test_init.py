"""Test CAME Domotic Unofficial setup process."""

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic_unofficial import async_remove_config_entry_device
from custom_components.came_domotic_unofficial.api import (
    CameDomoticUnofficialApiClient,
)
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
    assert isinstance(
        config_entry.runtime_data.client,
        CameDomoticUnofficialApiClient,
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


async def test_remove_config_entry_device(hass, bypass_get_data):
    """Test removing a device entry always returns True."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await async_remove_config_entry_device(hass, config_entry, None)  # type: ignore[arg-type]
    assert result is True


async def test_unload_entry_failure(hass, bypass_get_data):
    """Test unload when platform unload fails skips API disposal."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        return_value=False,
    ):
        result = await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is False


async def test_unload_stops_long_poll(hass, bypass_get_data):
    """Test that unloading the entry stops the long-poll task."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    with patch.object(coordinator, "stop_long_poll") as mock_stop:
        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    mock_stop.assert_awaited_once()
