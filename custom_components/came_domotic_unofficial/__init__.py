"""
Custom integration to integrate CAME Domotic Unofficial with Home Assistant.

For more details about this integration, please refer to
https://github.com/camedomotic-unofficial/came-domotic-unofficial
"""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.const import CONF_PASSWORD
from homeassistant.const import CONF_USERNAME
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntry

from .api import CameDomoticUnofficialApiClient
from .coordinator import CameDomoticUnofficialDataUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]

type CameDomoticUnofficialConfigEntry = ConfigEntry[RuntimeData]


@dataclass
class RuntimeData:
    """Class to hold runtime data."""

    coordinator: CameDomoticUnofficialDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticUnofficialConfigEntry,
) -> bool:
    """Set up this integration using UI."""
    host = entry.data[CONF_HOST]
    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]

    session = async_get_clientsession(hass)
    client = CameDomoticUnofficialApiClient(host, username, password, session)
    await client.async_connect()

    coordinator = CameDomoticUnofficialDataUpdateCoordinator(
        hass,
        client=client,
        config_entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    entry.runtime_data = RuntimeData(coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(
    hass: HomeAssistant,
    entry: CameDomoticUnofficialConfigEntry,
) -> None:
    """Handle config options update."""
    await hass.config_entries.async_reload(entry.entry_id)


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
    """Handle removal of an entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await entry.runtime_data.coordinator.api.async_dispose()
    return unload_ok
