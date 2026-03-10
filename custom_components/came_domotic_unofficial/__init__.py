"""
Custom integration to integrate CAME Domotic Unofficial with Home Assistant.

For more details about this integration, please refer to
https://github.com/camedomotic-unofficial/came-domotic-unofficial
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .api import CameDomoticUnofficialApiClient
from .coordinator import CameDomoticUnofficialDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SCENE, Platform.SENSOR]

type CameDomoticUnofficialConfigEntry = ConfigEntry[RuntimeData]


@dataclass
class RuntimeData:
    """Class to hold runtime data."""

    coordinator: CameDomoticUnofficialDataUpdateCoordinator
    client: CameDomoticUnofficialApiClient


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticUnofficialConfigEntry,
) -> bool:
    """Set up this integration using UI.

    Creates the API client, performs initial data fetch, and starts the
    background long-polling task for real-time updates.
    """
    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    _LOGGER.debug("Setting up CAME Domotic integration for host %s", host)

    session = async_get_clientsession(hass)
    client = CameDomoticUnofficialApiClient(host, username, password, session)
    await client.async_connect()
    _LOGGER.debug("Connected to CAME server at %s", host)

    coordinator = CameDomoticUnofficialDataUpdateCoordinator(
        hass,
        client=client,
        config_entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.debug("Initial data refresh completed")

    # Start the long-polling background task for real-time updates
    coordinator.start_long_poll()

    entry.runtime_data = RuntimeData(coordinator=coordinator, client=client)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("CAME Domotic integration setup complete for %s", host)
    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Delete device if selected from UI.

    Removing a device/entity is permitted without need of further actions.
    """
    return True


async def async_unload_entry(
    hass: HomeAssistant,
    entry: CameDomoticUnofficialConfigEntry,
) -> bool:
    """Handle removal of an entry.

    Stops the long-polling task, unloads platforms, and disposes the
    API connection.
    """
    _LOGGER.debug("Unloading CAME Domotic integration")

    # Stop long-poll task before unloading platforms
    await entry.runtime_data.coordinator.stop_long_poll()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.client.async_dispose()
        _LOGGER.info("CAME Domotic integration unloaded successfully")
    else:
        _LOGGER.warning("Failed to unload platforms, skipping API disposal")
    return unload_ok
