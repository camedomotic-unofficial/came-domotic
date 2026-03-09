"""CAME Domotic Unofficial API Client."""

from __future__ import annotations

import logging
import time
from typing import Any

from aiocamedomotic import CameDomoticAPI
from aiocamedomotic.errors import (
    CameDomoticAuthError,
    CameDomoticError,
    CameDomoticServerError,
    CameDomoticServerNotFoundError,
)
from aiocamedomotic.models import ServerInfo, ThermoZone, UpdateList
import aiohttp

_LOGGER: logging.Logger = logging.getLogger(__package__)


class CameDomoticUnofficialApiClientError(Exception):
    """Base exception for API client errors."""


class CameDomoticUnofficialApiClientCommunicationError(
    CameDomoticUnofficialApiClientError,
):
    """Exception for communication errors."""


class CameDomoticUnofficialApiClientAuthenticationError(
    CameDomoticUnofficialApiClientError,
):
    """Exception for authentication errors."""


class CameDomoticUnofficialApiClient:
    """CAME Domotic Unofficial API Client wrapping aiocamedomotic."""

    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        websession: aiohttp.ClientSession,
    ) -> None:
        """Initialize the API client."""
        self._host = host
        self._username = username
        self._password = password
        self._websession = websession
        self._api: CameDomoticAPI | None = None

    async def async_connect(self) -> None:
        """Create the CameDomoticAPI instance (validates host reachability)."""
        _LOGGER.debug("Connecting to CAME server at %s", self._host)
        try:
            self._api = await CameDomoticAPI.async_create(
                self._host,
                self._username,
                self._password,
                websession=self._websession,
                close_websession_on_disposal=False,
            )
        except CameDomoticServerNotFoundError as err:
            _LOGGER.debug("Server not found at %s", self._host)
            raise CameDomoticUnofficialApiClientCommunicationError(
                f"Unable to reach server at {self._host}",
            ) from err
        except CameDomoticError as err:
            _LOGGER.debug("Error connecting to server at %s: %s", self._host, err)
            raise CameDomoticUnofficialApiClientError(
                f"Error connecting to server at {self._host}",
            ) from err
        _LOGGER.debug("Successfully connected to CAME server at %s", self._host)

    async def async_get_server_info(self) -> ServerInfo:
        """Get server info (triggers lazy auth on first call)."""
        if self._api is None:
            raise CameDomoticUnofficialApiClientError("Not initialized")
        _LOGGER.debug("Fetching server info from %s", self._host)
        try:
            return await self._api.async_get_server_info()
        except CameDomoticAuthError as err:
            _LOGGER.debug("Authentication failed while fetching server info")
            raise CameDomoticUnofficialApiClientAuthenticationError(
                "Invalid credentials",
            ) from err
        except CameDomoticServerError as err:
            _LOGGER.debug("Server error while fetching server info: %s", err)
            raise CameDomoticUnofficialApiClientCommunicationError(
                "Server error while fetching server info",
            ) from err
        except CameDomoticError as err:
            _LOGGER.debug("Error fetching server info: %s", err)
            raise CameDomoticUnofficialApiClientError(
                "Error fetching server info",
            ) from err

    async def async_get_thermo_zones(self) -> list[ThermoZone]:
        """Fetch thermoregulation zones from the CAME Domotic server."""
        if self._api is None:
            raise CameDomoticUnofficialApiClientError("Not initialized")
        _LOGGER.debug("Fetching thermo zones from %s", self._host)
        try:
            zones = await self._api.async_get_thermo_zones()
        except CameDomoticAuthError as err:
            _LOGGER.debug("Authentication failed while fetching thermo zones")
            raise CameDomoticUnofficialApiClientAuthenticationError(
                "Invalid credentials",
            ) from err
        except CameDomoticServerError as err:
            _LOGGER.debug("Server error while fetching thermo zones: %s", err)
            raise CameDomoticUnofficialApiClientCommunicationError(
                "Server error while fetching thermo zones",
            ) from err
        except CameDomoticError as err:
            _LOGGER.debug("Error fetching thermo zones: %s", err)
            raise CameDomoticUnofficialApiClientError(
                "Error fetching thermo zones",
            ) from err
        _LOGGER.debug("Fetched %d thermo zone(s)", len(zones))
        return zones

    async def async_get_data(self) -> dict[str, Any]:
        """Fetch data from the CAME Domotic server."""
        if self._api is None:
            raise CameDomoticUnofficialApiClientError("Not initialized")
        _LOGGER.debug("Fetching data from CAME server")
        try:
            server_info = await self._api.async_get_server_info()
            thermo_zones = await self._api.async_get_thermo_zones()
            _LOGGER.debug("Fetched data: %d thermo zone(s)", len(thermo_zones))
            return {
                "keycode": server_info.keycode,
                "software_version": server_info.swver,
                "server_type": server_info.type,
                "board": server_info.board,
                "serial_number": server_info.serial,
                "thermo_zones": thermo_zones,
            }
        except CameDomoticAuthError as err:
            _LOGGER.warning("Authentication failed while fetching data")
            raise CameDomoticUnofficialApiClientAuthenticationError(
                "Invalid credentials",
            ) from err
        except CameDomoticServerError as err:
            _LOGGER.debug("Server error while fetching data: %s", err)
            raise CameDomoticUnofficialApiClientCommunicationError(
                "Server error while fetching data",
            ) from err
        except CameDomoticError as err:
            _LOGGER.debug("Error fetching data: %s", err)
            raise CameDomoticUnofficialApiClientError(
                "Error fetching data",
            ) from err

    async def async_get_updates(self, timeout: int = 120) -> UpdateList:
        """Long-poll the CAME server for device state changes.

        Blocks until the server reports one or more state changes or the
        timeout expires. On timeout the server raises CameDomoticServerError
        which is translated to CommunicationError by this wrapper.

        Args:
            timeout: Maximum seconds to wait for updates from the server.

        Returns:
            An UpdateList containing all pending device updates.
        """
        if self._api is None:
            raise CameDomoticUnofficialApiClientError("Not initialized")
        _LOGGER.debug("Starting long-poll for updates (timeout=%ds)", timeout)
        start = time.monotonic()
        try:
            result = await self._api.async_get_updates(timeout=timeout)
        except CameDomoticAuthError as err:
            _LOGGER.debug("Authentication failed during long poll")
            raise CameDomoticUnofficialApiClientAuthenticationError(
                "Invalid credentials",
            ) from err
        except CameDomoticServerError as err:
            _LOGGER.debug("Server error during long poll: %s", err)
            raise CameDomoticUnofficialApiClientCommunicationError(
                "Server error during long poll",
            ) from err
        except CameDomoticError as err:
            _LOGGER.debug("Error during long poll: %s", err)
            raise CameDomoticUnofficialApiClientError(
                "Error during long poll",
            ) from err
        elapsed = time.monotonic() - start
        _LOGGER.debug("Long-poll returned updates after %.1fs", elapsed)
        return result

    async def async_dispose(self) -> None:
        """Clean up the API connection."""
        _LOGGER.debug("Disposing API connection")
        if self._api:
            await self._api.async_dispose()
            self._api = None
