"""Test CAME Domotic Unofficial coordinator."""

from unittest.mock import patch

from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic_unofficial.api import (
    CameDomoticUnofficialApiClientAuthenticationError,
    CameDomoticUnofficialApiClientCommunicationError,
)
from custom_components.came_domotic_unofficial.const import DOMAIN

from .const import MOCK_CONFIG


async def test_coordinator_update_success(hass, bypass_get_data):
    """Test coordinator fetches data successfully."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator
    assert coordinator.data is not None
    assert coordinator.data["keycode"] == "AA:BB:CC:DD:EE:FF"
    assert coordinator.data["software_version"] == "1.2.3"


async def test_coordinator_auth_error_raises_config_entry_auth_failed(
    hass, bypass_get_data
):
    """Test coordinator raises ConfigEntryAuthFailed on auth error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    with patch.object(
        coordinator.api,
        "async_get_data",
        side_effect=CameDomoticUnofficialApiClientAuthenticationError("Bad auth"),
    ), pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_coordinator_communication_error_raises_update_failed(
    hass, bypass_get_data
):
    """Test coordinator raises UpdateFailed on communication error."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    with patch.object(
        coordinator.api,
        "async_get_data",
        side_effect=CameDomoticUnofficialApiClientCommunicationError("Timeout"),
    ), pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
