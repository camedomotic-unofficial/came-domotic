"""Polling-based DataUpdateCoordinator for CAME Domotic server connectivity.

Periodically pings the CAME server to monitor reachability and measure
round-trip latency. Adjusts the polling interval based on connectivity
state (faster when disconnected to detect recovery sooner).
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import (
    CameDomoticApiClient,
    CameDomoticApiClientAuthenticationError,
    CameDomoticApiClientError,
)
from .const import DOMAIN, PING_UPDATE_INTERVAL, PING_UPDATE_INTERVAL_DISCONNECTED
from .models import PingResult

_LOGGER: logging.Logger = logging.getLogger(__name__)


class CameDomoticPingCoordinator(DataUpdateCoordinator[PingResult]):
    """Coordinator for periodic server connectivity and latency diagnostics.

    Polls the CAME server via async_ping() on a fixed interval and exposes
    the result as a PingResult (connected flag + latency in ms). Communication
    errors are caught and returned as PingResult(connected=False, latency_ms=None)
    so the connectivity binary sensor shows OFF rather than unavailable.
    Auth errors raise ConfigEntryAuthFailed to trigger a reauth flow.
    """

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: CameDomoticApiClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the ping coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_ping",
            update_interval=PING_UPDATE_INTERVAL,
            config_entry=config_entry,
        )
        self._client = client

    async def _async_update_data(self) -> PingResult:
        """Ping the server and return connectivity status and latency.

        When the API client is not connected (e.g. server was offline at
        startup), attempts to establish the connection before pinging.
        """
        if not self._client.is_connected:
            try:
                await self._client.async_connect()
                _LOGGER.info("API connection established during ping recovery")
            except CameDomoticApiClientAuthenticationError as err:
                raise ConfigEntryAuthFailed(
                    "Authentication failed during ping"
                ) from err
            except CameDomoticApiClientError:
                _LOGGER.debug("Ping: connection attempt failed, server still offline")
                self.update_interval = PING_UPDATE_INTERVAL_DISCONNECTED
                return PingResult(connected=False, latency_ms=None)

        try:
            latency_ms = await self._client.async_ping()
            _LOGGER.debug("Ping succeeded: %.1f ms", latency_ms)
            self.update_interval = PING_UPDATE_INTERVAL
            return PingResult(connected=True, latency_ms=latency_ms)
        except CameDomoticApiClientAuthenticationError as err:
            raise ConfigEntryAuthFailed("Authentication failed during ping") from err
        except CameDomoticApiClientError:
            _LOGGER.debug("Ping failed: server unreachable")
            self.update_interval = PING_UPDATE_INTERVAL_DISCONNECTED
            return PingResult(connected=False, latency_ms=None)
