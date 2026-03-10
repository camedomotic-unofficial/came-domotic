"""Tests for CAME Domotic Unofficial API client."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from aiocamedomotic.errors import (
    CameDomoticAuthError,
    CameDomoticError,
    CameDomoticServerError,
    CameDomoticServerNotFoundError,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import pytest

from custom_components.came_domotic_unofficial.api import (
    CameDomoticUnofficialApiClient,
    CameDomoticUnofficialApiClientAuthenticationError,
    CameDomoticUnofficialApiClientCommunicationError,
    CameDomoticUnofficialApiClientError,
)

_PATCH_ASYNC_CREATE = (
    "custom_components.came_domotic_unofficial.api.CameDomoticAPI.async_create"
)


def _make_client(hass):
    """Create an API client for testing."""
    session = async_get_clientsession(hass)
    return CameDomoticUnofficialApiClient("192.168.1.1", "user", "pass", session)


def _mock_server_info():
    """Create a mock ServerInfo object."""
    info = MagicMock()
    info.keycode = "AA:BB:CC:DD:EE:FF"
    info.swver = "1.2.3"
    info.type = "ETI/Domo"
    info.board = "board_v1"
    return info


# --- async_connect ---


async def test_async_connect_success(hass):
    """Test successful connection creates the API instance."""
    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    assert client._api is mock_api


async def test_async_connect_server_not_found(hass):
    """Test CameDomoticServerNotFoundError raises CommunicationError."""
    client = _make_client(hass)

    with (
        patch(
            _PATCH_ASYNC_CREATE,
            side_effect=CameDomoticServerNotFoundError("not found"),
        ),
        pytest.raises(CameDomoticUnofficialApiClientCommunicationError),
    ):
        await client.async_connect()


async def test_async_connect_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)

    with (
        patch(
            _PATCH_ASYNC_CREATE,
            side_effect=CameDomoticError("generic"),
        ),
        pytest.raises(CameDomoticUnofficialApiClientError),
    ):
        await client.async_connect()


# --- async_get_server_info ---


async def test_async_get_server_info_success(hass):
    """Test successful server info retrieval."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_info = _mock_server_info()
    mock_api.async_get_server_info.return_value = mock_info

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_server_info()
    assert result is mock_info


async def test_async_get_server_info_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_server_info.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticUnofficialApiClientAuthenticationError):
        await client.async_get_server_info()


async def test_async_get_server_info_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_server_info.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticUnofficialApiClientCommunicationError):
        await client.async_get_server_info()


async def test_async_get_server_info_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_server_info.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticUnofficialApiClientError):
        await client.async_get_server_info()


async def test_async_get_server_info_not_initialized(hass):
    """Test async_get_server_info raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticUnofficialApiClientError, match="Not initialized"):
        await client.async_get_server_info()


# --- async_get_thermo_zones ---


async def test_async_get_thermo_zones_success(hass):
    """Test successful thermo zones retrieval."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_zones = [MagicMock(), MagicMock()]
    mock_api.async_get_thermo_zones.return_value = mock_zones

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_thermo_zones()
    assert result is mock_zones


async def test_async_get_thermo_zones_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_thermo_zones.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticUnofficialApiClientAuthenticationError):
        await client.async_get_thermo_zones()


async def test_async_get_thermo_zones_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_thermo_zones.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticUnofficialApiClientCommunicationError):
        await client.async_get_thermo_zones()


async def test_async_get_thermo_zones_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_thermo_zones.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticUnofficialApiClientError):
        await client.async_get_thermo_zones()


async def test_async_get_thermo_zones_not_initialized(hass):
    """Test async_get_thermo_zones raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticUnofficialApiClientError, match="Not initialized"):
        await client.async_get_thermo_zones()


# --- async_get_updates ---


async def test_async_get_updates_success(hass):
    """Test successful long-poll returns UpdateList."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_update_list = MagicMock()
    mock_api.async_get_updates.return_value = mock_update_list

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_updates(timeout=60)
    assert result is mock_update_list
    mock_api.async_get_updates.assert_awaited_once_with(timeout=60)


async def test_async_get_updates_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_updates.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticUnofficialApiClientAuthenticationError):
        await client.async_get_updates()


async def test_async_get_updates_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_updates.side_effect = CameDomoticServerError("timeout")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticUnofficialApiClientCommunicationError):
        await client.async_get_updates()


async def test_async_get_updates_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_updates.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticUnofficialApiClientError):
        await client.async_get_updates()


async def test_async_get_updates_not_initialized(hass):
    """Test async_get_updates raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticUnofficialApiClientError, match="Not initialized"):
        await client.async_get_updates()


# --- async_dispose ---


async def test_async_dispose(hass):
    """Test dispose cleans up the API connection."""
    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    await client.async_dispose()
    mock_api.async_dispose.assert_awaited_once()
    assert client._api is None


async def test_async_dispose_no_api(hass):
    """Test dispose without prior connect does not raise."""
    client = _make_client(hass)
    await client.async_dispose()
