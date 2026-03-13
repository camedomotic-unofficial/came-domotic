"""
Custom integration to integrate CAME Domotic with Home Assistant.

For more details about this integration, please refer to
https://github.com/camedomotic-unofficial/came-domotic
"""

from __future__ import annotations

from dataclasses import dataclass
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.typing import ConfigType

from .api import CameDomoticApiClient, CameDomoticApiClientCommunicationError
from .const import DOMAIN, PING_UPDATE_INTERVAL_DISCONNECTED
from .coordinator import CameDomoticDataUpdateCoordinator, CameDomoticPingCoordinator
from .models import CameDomoticServerData, PingResult
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.LIGHT,
    Platform.SCENE,
    Platform.SENSOR,
]

type CameDomoticConfigEntry = ConfigEntry[RuntimeData]


@dataclass
class RuntimeData:
    """Class to hold runtime data."""

    coordinator: CameDomoticDataUpdateCoordinator
    client: CameDomoticApiClient
    ping_coordinator: CameDomoticPingCoordinator


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the CAME Domotic integration."""
    await async_setup_services(hass)
    return True


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticConfigEntry,
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
    client = CameDomoticApiClient(host, username, password, session)

    # Attempt connection — if the server is offline, continue setup gracefully.
    # The ping coordinator will keep retrying and reload the entry on recovery.
    try:
        await client.async_connect()
        connected = True
        _LOGGER.debug("Connected to CAME server at %s", host)
    except CameDomoticApiClientCommunicationError:
        connected = False
        _LOGGER.warning(
            "CAME server at %s is not reachable; "
            "setting up in offline mode (will retry via ping)",
            host,
        )

    coordinator = CameDomoticDataUpdateCoordinator(
        hass,
        client=client,
        config_entry=entry,
    )

    if connected:
        try:
            await coordinator.async_config_entry_first_refresh()
            _LOGGER.debug("Initial data refresh completed")
            coordinator.start_long_poll()
        except ConfigEntryNotReady:
            connected = False
            _LOGGER.warning(
                "CAME server at %s dropped during initial data fetch; "
                "continuing in offline mode (will retry via ping)",
                host,
            )

    if not connected:
        # Set empty data so platforms can set up (no device entities yet).
        # The entry will be reloaded once the server becomes reachable.
        coordinator.async_set_updated_data(CameDomoticServerData())
        coordinator._server_available = False  # noqa: SLF001
        coordinator._started_offline = True  # noqa: SLF001

    ping_coordinator = CameDomoticPingCoordinator(
        hass, client=client, config_entry=entry
    )
    if connected:
        await ping_coordinator.async_config_entry_first_refresh()
    else:
        ping_coordinator.update_interval = PING_UPDATE_INTERVAL_DISCONNECTED
        ping_coordinator.async_set_updated_data(
            PingResult(connected=False, latency_ms=None)
        )

    # Ping is the single authority on connectivity: it drives entity availability
    # and the long-poll lifecycle (stop on disconnect, restart on recovery).
    coordinator.attach_ping_coordinator(ping_coordinator)

    entry.runtime_data = RuntimeData(
        coordinator=coordinator, client=client, ping_coordinator=ping_coordinator
    )

    # Ensure services are registered (idempotent — covers edge cases where
    # async_setup was not called, e.g. after a failed first load attempt).
    await async_setup_services(hass)

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
    entry: CameDomoticConfigEntry,
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
        await async_unload_services(hass)
        _LOGGER.info("CAME Domotic integration unloaded successfully")
    else:
        _LOGGER.warning("Failed to unload platforms, skipping API disposal")
    return unload_ok
