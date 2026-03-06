"""CAME Domotic Unofficial API Client."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp
from aiocamedomotic import CameDomoticAPI
from aiocamedomotic.errors import CameDomoticAuthError
from aiocamedomotic.errors import CameDomoticError
from aiocamedomotic.errors import CameDomoticServerError
from aiocamedomotic.errors import CameDomoticServerNotFoundError

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
        try:
            self._api = await CameDomoticAPI.async_create(
                self._host,
                self._username,
                self._password,
                websession=self._websession,
                close_websession_on_disposal=False,
            )
        except CameDomoticServerNotFoundError as err:
            raise CameDomoticUnofficialApiClientCommunicationError(
                f"Unable to reach server at {self._host}",
            ) from err
        except CameDomoticError as err:
            raise CameDomoticUnofficialApiClientError(
                f"Error connecting to server at {self._host}",
            ) from err

    async def async_get_server_info(self) -> Any:
        """Get server info (triggers lazy auth on first call)."""
        if self._api is None:
            raise CameDomoticUnofficialApiClientError("Not initialized")
        try:
            return await self._api.async_get_server_info()
        except CameDomoticAuthError as err:
            raise CameDomoticUnofficialApiClientAuthenticationError(
                "Invalid credentials",
            ) from err
        except CameDomoticServerError as err:
            raise CameDomoticUnofficialApiClientCommunicationError(
                "Server error while fetching server info",
            ) from err
        except CameDomoticError as err:
            raise CameDomoticUnofficialApiClientError(
                "Error fetching server info",
            ) from err

    async def async_get_data(self) -> dict[str, Any]:
        """Fetch data from the CAME Domotic server."""
        if self._api is None:
            raise CameDomoticUnofficialApiClientError("Not initialized")
        try:
            server_info = await self._api.async_get_server_info()
            return {
                "keycode": server_info.keycode,
                "software_version": server_info.swver,
                "server_type": server_info.type,
                "board": server_info.board,
            }
        except CameDomoticAuthError as err:
            raise CameDomoticUnofficialApiClientAuthenticationError(
                "Invalid credentials",
            ) from err
        except CameDomoticServerError as err:
            raise CameDomoticUnofficialApiClientCommunicationError(
                "Server error while fetching data",
            ) from err
        except CameDomoticError as err:
            raise CameDomoticUnofficialApiClientError(
                "Error fetching data",
            ) from err

    async def async_dispose(self) -> None:
        """Clean up the API connection."""
        if self._api:
            await self._api.async_dispose()
            self._api = None
