"""Test CAME Domotic setup process."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.config_entries import ConfigEntryState
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic import async_remove_config_entry_device
from custom_components.came_domotic.api import (
    CameDomoticApiClient,
    CameDomoticApiClientCommunicationError,
)
from custom_components.came_domotic.const import (
    DOMAIN,
    PING_UPDATE_INTERVAL_DISCONNECTED,
)
from custom_components.came_domotic.coordinator import (
    CameDomoticDataUpdateCoordinator,
    CameDomoticPingCoordinator,
)

from .const import MOCK_CONFIG

_API_CLIENT = "custom_components.came_domotic.api.CameDomoticApiClient"
_COORDINATOR = (
    "custom_components.came_domotic.coordinator.CameDomoticDataUpdateCoordinator"
)


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
        CameDomoticDataUpdateCoordinator,
    )
    assert isinstance(
        config_entry.runtime_data.client,
        CameDomoticApiClient,
    )
    assert isinstance(
        config_entry.runtime_data.ping_coordinator,
        CameDomoticPingCoordinator,
    )

    # Unload the entry
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_communication_error(hass, error_on_get_data):
    """Test offline mode when API raises a communication error during first refresh."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Entry loaded in offline mode despite data fetch failure
    assert config_entry.state is ConfigEntryState.LOADED

    coordinator = config_entry.runtime_data.coordinator
    ping_coordinator = config_entry.runtime_data.ping_coordinator

    # Coordinator should be in offline state
    assert coordinator._started_offline is True  # noqa: SLF001
    assert coordinator.server_available is False

    # Ping should show disconnected with fast retry cadence
    assert ping_coordinator.data.connected is False
    assert ping_coordinator.update_interval == PING_UPDATE_INTERVAL_DISCONNECTED

    # Clean up
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


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


async def test_setup_entry_server_offline(hass):
    """Test entry sets up in offline mode when server is unreachable at startup."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    with (
        patch(
            f"{_API_CLIENT}.async_connect",
            side_effect=CameDomoticApiClientCommunicationError("Timeout"),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch(f"{_API_CLIENT}.async_ping", return_value=10.0),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Entry loaded successfully despite server being offline
    assert config_entry.state is ConfigEntryState.LOADED

    coordinator = config_entry.runtime_data.coordinator
    ping_coordinator = config_entry.runtime_data.ping_coordinator

    # Coordinator should be in offline state
    assert coordinator._started_offline is True  # noqa: SLF001
    assert coordinator.server_available is False

    # Ping should show disconnected with fast retry cadence
    assert ping_coordinator.data.connected is False
    assert ping_coordinator.data.latency_ms is None
    assert ping_coordinator.update_interval == PING_UPDATE_INTERVAL_DISCONNECTED

    # Data should be empty defaults
    assert coordinator.data.server_info is None
    assert coordinator.data.thermo_zones == {}

    # Clean up
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
