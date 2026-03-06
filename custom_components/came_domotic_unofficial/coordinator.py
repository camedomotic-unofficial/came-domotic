"""DataUpdateCoordinator for CAME Domotic Unofficial."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    CameDomoticUnofficialApiClient,
    CameDomoticUnofficialApiClientAuthenticationError,
    CameDomoticUnofficialApiClientError,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER: logging.Logger = logging.getLogger(__name__)


class CameDomoticUnofficialDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching data from the API."""

    data: dict[str, Any]

    def __init__(
        self,
        hass: HomeAssistant,
        client: CameDomoticUnofficialApiClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize."""
        self.api = client
        poll_interval = config_entry.options.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            update_interval=timedelta(seconds=poll_interval),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> Any:
        """Update data via library."""
        try:
            return await self.api.async_get_data()
        except CameDomoticUnofficialApiClientAuthenticationError as exception:
            raise ConfigEntryAuthFailed(exception) from exception
        except CameDomoticUnofficialApiClientError as exception:
            raise UpdateFailed(exception) from exception
