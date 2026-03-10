"""CAME Domotic Unofficial API Client."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
import functools
import logging
import time
from typing import Any, TypeVar

from aiocamedomotic import CameDomoticAPI
from aiocamedomotic.errors import (
    CameDomoticAuthError,
    CameDomoticError,
    CameDomoticServerError,
    CameDomoticServerNotFoundError,
)
from aiocamedomotic.models import (
    Light,
    LightStatus,
    Opening,
    OpeningStatus,
    Scenario,
    ServerInfo,
    ThermoZone,
    UpdateList,
)
import aiohttp

_LOGGER: logging.Logger = logging.getLogger(__package__)

_T = TypeVar("_T")


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


def _translate_errors(
    func: Callable[..., Coroutine[Any, Any, _T]],
) -> Callable[..., Coroutine[Any, Any, _T]]:
    """Translate aiocamedomotic errors to integration errors."""

    @functools.wraps(func)
    async def wrapper(
        self: CameDomoticUnofficialApiClient, *args: Any, **kwargs: Any
    ) -> _T:
        if self._api is None:
            raise CameDomoticUnofficialApiClientError("Not initialized")
        try:
            return await func(self, *args, **kwargs)
        except CameDomoticAuthError as err:
            raise CameDomoticUnofficialApiClientAuthenticationError(
                "Invalid credentials",
            ) from err
        except CameDomoticServerError as err:
            raise CameDomoticUnofficialApiClientCommunicationError(
                f"Server error: {err}",
            ) from err
        except CameDomoticError as err:
            raise CameDomoticUnofficialApiClientError(
                f"Error: {err}",
            ) from err

    return wrapper


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

    @_translate_errors
    async def async_get_server_info(self) -> ServerInfo:
        """Get server info (triggers lazy auth on first call)."""
        assert self._api is not None  # noqa: S101  # nosec B101
        _LOGGER.debug("Fetching server info from %s", self._host)
        return await self._api.async_get_server_info()

    @_translate_errors
    async def async_get_thermo_zones(self) -> list[ThermoZone]:
        """Fetch thermoregulation zones from the CAME Domotic server."""
        assert self._api is not None  # noqa: S101  # nosec B101
        _LOGGER.debug("Fetching thermo zones from %s", self._host)
        zones = await self._api.async_get_thermo_zones()
        _LOGGER.debug("Fetched %d thermo zone(s)", len(zones))
        return zones

    @_translate_errors
    async def async_get_openings(self) -> list[Opening]:
        """Fetch openings from the CAME Domotic server."""
        assert self._api is not None  # noqa: S101  # nosec B101
        _LOGGER.debug("Fetching openings from %s", self._host)
        openings = await self._api.async_get_openings()
        _LOGGER.debug("Fetched %d opening(s)", len(openings))
        return openings

    @_translate_errors
    async def async_set_opening_status(
        self, opening: Opening, status: OpeningStatus
    ) -> None:
        """Set the status (motor direction) of an opening.

        Args:
            opening: The Opening object to control.
            status: The desired OpeningStatus (STOPPED, OPENING, CLOSING,
                    SLAT_OPEN, SLAT_CLOSE).
        """
        assert self._api is not None  # noqa: S101  # nosec B101
        _LOGGER.debug(
            "Setting opening '%s' (open_act_id=%d) to %s",
            opening.name,
            opening.open_act_id,
            status.name,
        )
        await opening.async_set_status(status)

    @_translate_errors
    async def async_get_lights(self) -> list[Light]:
        """Fetch lights from the CAME Domotic server."""
        assert self._api is not None  # noqa: S101  # nosec B101
        _LOGGER.debug("Fetching lights from %s", self._host)
        lights = await self._api.async_get_lights()
        _LOGGER.debug("Fetched %d light(s)", len(lights))
        return lights

    @_translate_errors
    async def async_set_light_status(
        self,
        light: Light,
        status: LightStatus,
        brightness: int | None = None,
        rgb: list[int] | None = None,
    ) -> None:
        """Set the status of a light.

        Args:
            light: The Light object to control.
            status: The desired LightStatus (ON, OFF).
            brightness: Optional brightness percentage (0-100) for dimmers/RGB.
            rgb: Optional [R, G, B] color values (0-255) for RGB lights.
        """
        assert self._api is not None  # noqa: S101  # nosec B101
        _LOGGER.debug(
            "Setting light '%s' (act_id=%d) to %s (brightness=%s, rgb=%s)",
            light.name,
            light.act_id,
            status.name,
            brightness,
            rgb,
        )
        await light.async_set_status(status, brightness=brightness, rgb=rgb)

    @_translate_errors
    async def async_get_scenarios(self) -> list[Scenario]:
        """Fetch scenarios from the CAME Domotic server."""
        assert self._api is not None  # noqa: S101  # nosec B101
        _LOGGER.debug("Fetching scenarios from %s", self._host)
        scenarios = await self._api.async_get_scenarios()
        _LOGGER.debug("Fetched %d scenario(s)", len(scenarios))
        return scenarios

    @_translate_errors
    async def async_activate_scenario(self, scenario: Scenario) -> None:
        """Activate a scenario on the CAME Domotic server.

        Args:
            scenario: The Scenario object to activate.
        """
        assert self._api is not None  # noqa: S101  # nosec B101
        _LOGGER.debug("Activating scenario '%s' (id=%d)", scenario.name, scenario.id)
        await scenario.async_activate()

    @_translate_errors
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
        assert self._api is not None  # noqa: S101  # nosec B101
        _LOGGER.debug("Starting long-poll for updates (timeout=%ds)", timeout)
        start = time.monotonic()
        result = await self._api.async_get_updates(timeout=timeout)
        elapsed = time.monotonic() - start
        _LOGGER.debug("Long-poll returned updates after %.1fs", elapsed)
        return result

    async def async_dispose(self) -> None:
        """Clean up the API connection."""
        _LOGGER.debug("Disposing API connection")
        if self._api:
            await self._api.async_dispose()
            self._api = None
