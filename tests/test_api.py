"""Tests for CAME Domotic API client."""

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

from custom_components.came_domotic.api import (
    CameDomoticApiClient,
    CameDomoticApiClientAuthenticationError,
    CameDomoticApiClientCommunicationError,
    CameDomoticApiClientError,
)

_PATCH_ASYNC_CREATE = "custom_components.came_domotic.api.CameDomoticAPI.async_create"


def _make_client(hass):
    """Create an API client for testing."""
    session = async_get_clientsession(hass)
    return CameDomoticApiClient("192.168.1.1", "user", "pass", session)


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
        pytest.raises(CameDomoticApiClientCommunicationError),
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
        pytest.raises(CameDomoticApiClientError),
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

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_server_info()


async def test_async_get_server_info_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_server_info.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_server_info()


async def test_async_get_server_info_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_server_info.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_server_info()


async def test_async_get_server_info_not_initialized(hass):
    """Test async_get_server_info raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
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

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_thermo_zones()


async def test_async_get_thermo_zones_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_thermo_zones.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_thermo_zones()


async def test_async_get_thermo_zones_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_thermo_zones.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_thermo_zones()


async def test_async_get_thermo_zones_not_initialized(hass):
    """Test async_get_thermo_zones raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_get_thermo_zones()


# --- async_get_scenarios ---


async def test_async_get_scenarios_success(hass):
    """Test successful scenarios retrieval."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_scenarios = [MagicMock(), MagicMock()]
    mock_api.async_get_scenarios.return_value = mock_scenarios

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_scenarios()
    assert result is mock_scenarios


async def test_async_get_scenarios_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_scenarios.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_scenarios()


async def test_async_get_scenarios_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_scenarios.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_scenarios()


async def test_async_get_scenarios_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_scenarios.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_scenarios()


async def test_async_get_scenarios_not_initialized(hass):
    """Test async_get_scenarios raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_get_scenarios()


# --- async_activate_scenario ---


async def test_async_activate_scenario_success(hass):
    """Test successful scenario activation."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_scenario = MagicMock()
    mock_scenario.name = "Good Morning"
    mock_scenario.id = 10
    mock_scenario.async_activate = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    await client.async_activate_scenario(mock_scenario)
    mock_scenario.async_activate.assert_awaited_once()


async def test_async_activate_scenario_auth_error(hass):
    """Test CameDomoticAuthError during activation raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_scenario = MagicMock()
    mock_scenario.name = "Good Morning"
    mock_scenario.id = 10
    mock_scenario.async_activate = AsyncMock(
        side_effect=CameDomoticAuthError("bad creds")
    )

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_activate_scenario(mock_scenario)


async def test_async_activate_scenario_server_error(hass):
    """Test CameDomoticServerError during activation raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_scenario = MagicMock()
    mock_scenario.name = "Good Morning"
    mock_scenario.id = 10
    mock_scenario.async_activate = AsyncMock(
        side_effect=CameDomoticServerError("server err")
    )

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_activate_scenario(mock_scenario)


async def test_async_activate_scenario_generic_error(hass):
    """Test CameDomoticError during activation raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_scenario = MagicMock()
    mock_scenario.name = "Good Morning"
    mock_scenario.id = 10
    mock_scenario.async_activate = AsyncMock(side_effect=CameDomoticError("generic"))

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_activate_scenario(mock_scenario)


async def test_async_activate_scenario_not_initialized(hass):
    """Test async_activate_scenario raises ApiClientError when not connected."""
    client = _make_client(hass)
    mock_scenario = MagicMock()

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_activate_scenario(mock_scenario)


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

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_updates()


async def test_async_get_updates_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_updates.side_effect = CameDomoticServerError("timeout")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_updates()


async def test_async_get_updates_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_updates.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_updates()


async def test_async_get_updates_not_initialized(hass):
    """Test async_get_updates raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
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


# --- async_get_openings ---


async def test_async_get_openings_success(hass):
    """Test successful openings retrieval."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_openings = [MagicMock(), MagicMock()]
    mock_api.async_get_openings.return_value = mock_openings

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_openings()
    assert result is mock_openings


async def test_async_get_openings_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_openings.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_openings()


async def test_async_get_openings_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_openings.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_openings()


async def test_async_get_openings_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_openings.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_openings()


async def test_async_get_openings_not_initialized(hass):
    """Test async_get_openings raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_get_openings()


# --- async_set_opening_status ---


async def test_async_set_opening_status_success(hass):
    """Test successful opening status change."""
    from aiocamedomotic.models import OpeningStatus

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_opening = MagicMock()
    mock_opening.name = "Living Room Shutter"
    mock_opening.open_act_id = 100
    mock_opening.async_set_status = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    await client.async_set_opening_status(mock_opening, OpeningStatus.OPENING)
    mock_opening.async_set_status.assert_awaited_once_with(OpeningStatus.OPENING)


async def test_async_set_opening_status_auth_error(hass):
    """Test CameDomoticAuthError during status change raises AuthenticationError."""
    from aiocamedomotic.models import OpeningStatus

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_opening = MagicMock()
    mock_opening.name = "Living Room Shutter"
    mock_opening.open_act_id = 100
    mock_opening.async_set_status = AsyncMock(
        side_effect=CameDomoticAuthError("bad creds")
    )

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_set_opening_status(mock_opening, OpeningStatus.OPENING)


async def test_async_set_opening_status_server_error(hass):
    """Test CameDomoticServerError during status change raises CommunicationError."""
    from aiocamedomotic.models import OpeningStatus

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_opening = MagicMock()
    mock_opening.name = "Living Room Shutter"
    mock_opening.open_act_id = 100
    mock_opening.async_set_status = AsyncMock(
        side_effect=CameDomoticServerError("server err")
    )

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_set_opening_status(mock_opening, OpeningStatus.OPENING)


async def test_async_set_opening_status_generic_error(hass):
    """Test CameDomoticError during status change raises ApiClientError."""
    from aiocamedomotic.models import OpeningStatus

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_opening = MagicMock()
    mock_opening.name = "Living Room Shutter"
    mock_opening.open_act_id = 100
    mock_opening.async_set_status = AsyncMock(side_effect=CameDomoticError("generic"))

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_set_opening_status(mock_opening, OpeningStatus.OPENING)


async def test_async_set_opening_status_not_initialized(hass):
    """Test async_set_opening_status raises ApiClientError when not connected."""
    from aiocamedomotic.models import OpeningStatus

    client = _make_client(hass)
    mock_opening = MagicMock()

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_set_opening_status(mock_opening, OpeningStatus.OPENING)


# --- async_get_lights ---


async def test_async_get_lights_success(hass):
    """Test successful lights retrieval."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_lights = [MagicMock(), MagicMock()]
    mock_api.async_get_lights.return_value = mock_lights

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_lights()
    assert result is mock_lights


async def test_async_get_lights_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_lights.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_lights()


async def test_async_get_lights_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_lights.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_lights()


async def test_async_get_lights_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_lights.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_lights()


async def test_async_get_lights_not_initialized(hass):
    """Test async_get_lights raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_get_lights()


# --- async_set_light_status ---


async def test_async_set_light_status_success(hass):
    """Test successful light status change with brightness and RGB."""
    from aiocamedomotic.models import LightStatus

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_light = MagicMock()
    mock_light.name = "Living Room Dimmer"
    mock_light.act_id = 301
    mock_light.async_set_status = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    await client.async_set_light_status(
        mock_light, LightStatus.ON, brightness=75, rgb=[255, 128, 0]
    )
    mock_light.async_set_status.assert_awaited_once_with(
        LightStatus.ON, brightness=75, rgb=[255, 128, 0]
    )


async def test_async_set_light_status_no_optional_params(hass):
    """Test light status change without optional brightness/RGB."""
    from aiocamedomotic.models import LightStatus

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_light = MagicMock()
    mock_light.name = "Hallway Light"
    mock_light.act_id = 300
    mock_light.async_set_status = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    await client.async_set_light_status(mock_light, LightStatus.OFF)
    mock_light.async_set_status.assert_awaited_once_with(
        LightStatus.OFF, brightness=None, rgb=None
    )


async def test_async_set_light_status_auth_error(hass):
    """Test CameDomoticAuthError during light status change raises AuthenticationError."""
    from aiocamedomotic.models import LightStatus

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_light = MagicMock()
    mock_light.name = "Hallway Light"
    mock_light.act_id = 300
    mock_light.async_set_status = AsyncMock(
        side_effect=CameDomoticAuthError("bad creds")
    )

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_set_light_status(mock_light, LightStatus.ON)


async def test_async_set_light_status_server_error(hass):
    """Test CameDomoticServerError during light status change raises CommunicationError."""
    from aiocamedomotic.models import LightStatus

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_light = MagicMock()
    mock_light.name = "Hallway Light"
    mock_light.act_id = 300
    mock_light.async_set_status = AsyncMock(
        side_effect=CameDomoticServerError("server err")
    )

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_set_light_status(mock_light, LightStatus.ON)


async def test_async_set_light_status_generic_error(hass):
    """Test CameDomoticError during light status change raises ApiClientError."""
    from aiocamedomotic.models import LightStatus

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_light = MagicMock()
    mock_light.name = "Hallway Light"
    mock_light.act_id = 300
    mock_light.async_set_status = AsyncMock(side_effect=CameDomoticError("generic"))

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_set_light_status(mock_light, LightStatus.ON)


async def test_async_set_light_status_not_initialized(hass):
    """Test async_set_light_status raises ApiClientError when not connected."""
    from aiocamedomotic.models import LightStatus

    client = _make_client(hass)
    mock_light = MagicMock()

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_set_light_status(mock_light, LightStatus.ON)


# --- async_get_digital_inputs ---


async def test_async_get_digital_inputs_success(hass):
    """Test successful digital inputs retrieval."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_digital_inputs = [MagicMock(), MagicMock()]
    mock_api.async_get_digital_inputs.return_value = mock_digital_inputs

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_digital_inputs()
    assert result is mock_digital_inputs


async def test_async_get_digital_inputs_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_digital_inputs.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_digital_inputs()


async def test_async_get_digital_inputs_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_digital_inputs.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_digital_inputs()


async def test_async_get_digital_inputs_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_digital_inputs.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_digital_inputs()


async def test_async_get_digital_inputs_not_initialized(hass):
    """Test async_get_digital_inputs raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_get_digital_inputs()


# --- async_get_analog_sensors ---


async def test_async_get_analog_sensors_success(hass):
    """Test successful analog sensors retrieval."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_sensors = [MagicMock(), MagicMock()]
    mock_api.async_get_analog_sensors.return_value = mock_sensors

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_analog_sensors()
    assert result is mock_sensors


async def test_async_get_analog_sensors_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_analog_sensors.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_analog_sensors()


async def test_async_get_analog_sensors_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_analog_sensors.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_analog_sensors()


async def test_async_get_analog_sensors_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_analog_sensors.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_analog_sensors()


async def test_async_get_analog_sensors_not_initialized(hass):
    """Test async_get_analog_sensors raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_get_analog_sensors()


# --- async_get_analog_inputs ---


async def test_async_get_analog_inputs_success(hass):
    """Test successful analog inputs retrieval."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_inputs = [MagicMock(), MagicMock()]
    mock_api.async_get_analog_inputs.return_value = mock_inputs

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_analog_inputs()
    assert result is mock_inputs


async def test_async_get_analog_inputs_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_analog_inputs.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_analog_inputs()


async def test_async_get_analog_inputs_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_analog_inputs.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_analog_inputs()


async def test_async_get_analog_inputs_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_analog_inputs.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_analog_inputs()


async def test_async_get_analog_inputs_not_initialized(hass):
    """Test async_get_analog_inputs raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_get_analog_inputs()


# --- async_get_relays ---


async def test_async_get_relays_success(hass):
    """Test successful relays retrieval."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_relays = [MagicMock(), MagicMock()]
    mock_api.async_get_relays.return_value = mock_relays

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_relays()
    assert result is mock_relays


async def test_async_get_relays_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_relays.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_relays()


async def test_async_get_relays_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_relays.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_relays()


async def test_async_get_relays_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_relays.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_relays()


async def test_async_get_relays_not_initialized(hass):
    """Test async_get_relays raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_get_relays()


# --- async_get_cameras ---


async def test_async_get_cameras_success(hass):
    """Test successful cameras retrieval."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_cameras = [MagicMock(), MagicMock()]
    mock_api.async_get_cameras.return_value = mock_cameras

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_cameras()
    assert result is mock_cameras


async def test_async_get_cameras_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_cameras.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_cameras()


async def test_async_get_cameras_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_cameras.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_cameras()


async def test_async_get_cameras_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_cameras.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_cameras()


async def test_async_get_cameras_not_initialized(hass):
    """Test async_get_cameras raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_get_cameras()


# --- async_get_map_pages ---


async def test_async_get_map_pages_success(hass):
    """Test successful map pages retrieval."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_pages = [MagicMock(), MagicMock()]
    mock_api.async_get_map_pages.return_value = mock_pages

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_map_pages()
    assert result is mock_pages


async def test_async_get_map_pages_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_map_pages.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_map_pages()


async def test_async_get_map_pages_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_map_pages.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_map_pages()


async def test_async_get_map_pages_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_map_pages.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_map_pages()


async def test_async_get_map_pages_not_initialized(hass):
    """Test async_get_map_pages raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_get_map_pages()


# --- async_set_relay_status ---


async def test_async_set_relay_status_success(hass):
    """Test successful relay status change."""
    from aiocamedomotic.models import RelayStatus

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_relay = MagicMock()
    mock_relay.name = "Pump Control"
    mock_relay.act_id = 600
    mock_relay.async_set_status = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    await client.async_set_relay_status(mock_relay, RelayStatus.ON)
    mock_relay.async_set_status.assert_awaited_once_with(RelayStatus.ON)


async def test_async_set_relay_status_off(hass):
    """Test relay status change to OFF."""
    from aiocamedomotic.models import RelayStatus

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_relay = MagicMock()
    mock_relay.name = "Pump Control"
    mock_relay.act_id = 600
    mock_relay.async_set_status = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    await client.async_set_relay_status(mock_relay, RelayStatus.OFF)
    mock_relay.async_set_status.assert_awaited_once_with(RelayStatus.OFF)


async def test_async_set_relay_status_auth_error(hass):
    """Test CameDomoticAuthError during relay status change raises AuthenticationError."""
    from aiocamedomotic.models import RelayStatus

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_relay = MagicMock()
    mock_relay.name = "Pump Control"
    mock_relay.act_id = 600
    mock_relay.async_set_status = AsyncMock(
        side_effect=CameDomoticAuthError("bad creds")
    )

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_set_relay_status(mock_relay, RelayStatus.ON)


async def test_async_set_relay_status_server_error(hass):
    """Test CameDomoticServerError during relay status change raises CommunicationError."""
    from aiocamedomotic.models import RelayStatus

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_relay = MagicMock()
    mock_relay.name = "Pump Control"
    mock_relay.act_id = 600
    mock_relay.async_set_status = AsyncMock(
        side_effect=CameDomoticServerError("server err")
    )

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_set_relay_status(mock_relay, RelayStatus.ON)


async def test_async_set_relay_status_generic_error(hass):
    """Test CameDomoticError during relay status change raises ApiClientError."""
    from aiocamedomotic.models import RelayStatus

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_relay = MagicMock()
    mock_relay.name = "Pump Control"
    mock_relay.act_id = 600
    mock_relay.async_set_status = AsyncMock(side_effect=CameDomoticError("generic"))

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_set_relay_status(mock_relay, RelayStatus.ON)


async def test_async_set_relay_status_not_initialized(hass):
    """Test async_set_relay_status raises ApiClientError when not connected."""
    from aiocamedomotic.models import RelayStatus

    client = _make_client(hass)
    mock_relay = MagicMock()

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_set_relay_status(mock_relay, RelayStatus.ON)


# --- async_get_users ---


async def test_async_get_users_success(hass):
    """Test successful users retrieval."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_users = [MagicMock(), MagicMock()]
    mock_api.async_get_users.return_value = mock_users

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_users()
    assert result is mock_users


async def test_async_get_users_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_users.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_users()


async def test_async_get_users_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_users.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_users()


async def test_async_get_users_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_users.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_users()


async def test_async_get_users_not_initialized(hass):
    """Test async_get_users raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_get_users()


# --- async_add_user ---


async def test_async_add_user_success(hass):
    """Test successful user creation."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_user = MagicMock()
    mock_api.async_add_user.return_value = mock_user

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_add_user("newuser", "newpass", group="ETI/Domo")
    assert result is mock_user
    mock_api.async_add_user.assert_awaited_once_with(
        "newuser", "newpass", group="ETI/Domo"
    )


async def test_async_add_user_default_group(hass):
    """Test user creation with default group."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_user = MagicMock()
    mock_api.async_add_user.return_value = mock_user

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_add_user("newuser", "newpass")
    assert result is mock_user
    mock_api.async_add_user.assert_awaited_once_with("newuser", "newpass", group="*")


async def test_async_add_user_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_add_user.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_add_user("newuser", "newpass")


async def test_async_add_user_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_add_user.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_add_user("newuser", "newpass")


async def test_async_add_user_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_add_user.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_add_user("newuser", "newpass")


async def test_async_add_user_not_initialized(hass):
    """Test async_add_user raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_add_user("newuser", "newpass")


# --- async_delete_user ---


async def test_async_delete_user_success(hass):
    """Test successful user deletion."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_user = MagicMock()
    mock_user.name = "olduser"
    mock_user.async_delete = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    await client.async_delete_user(mock_user)
    mock_user.async_delete.assert_awaited_once()


async def test_async_delete_user_auth_error(hass):
    """Test CameDomoticAuthError during deletion raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_user = MagicMock()
    mock_user.name = "olduser"
    mock_user.async_delete = AsyncMock(side_effect=CameDomoticAuthError("bad creds"))

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_delete_user(mock_user)


async def test_async_delete_user_server_error(hass):
    """Test CameDomoticServerError during deletion raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_user = MagicMock()
    mock_user.name = "olduser"
    mock_user.async_delete = AsyncMock(side_effect=CameDomoticServerError("server err"))

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_delete_user(mock_user)


async def test_async_delete_user_generic_error(hass):
    """Test CameDomoticError during deletion raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_user = MagicMock()
    mock_user.name = "olduser"
    mock_user.async_delete = AsyncMock(side_effect=CameDomoticError("generic"))

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_delete_user(mock_user)


async def test_async_delete_user_value_error(hass):
    """Test ValueError propagates when deleting the current user."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_user = MagicMock()
    mock_user.name = "currentuser"
    mock_user.async_delete = AsyncMock(
        side_effect=ValueError("Cannot delete current user")
    )

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(ValueError, match="Cannot delete current user"):
        await client.async_delete_user(mock_user)


async def test_async_delete_user_not_initialized(hass):
    """Test async_delete_user raises ApiClientError when not connected."""
    client = _make_client(hass)
    mock_user = MagicMock()

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_delete_user(mock_user)


# --- async_change_user_password ---


async def test_async_change_user_password_success(hass):
    """Test successful password change."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_user = MagicMock()
    mock_user.name = "testuser"
    mock_user.async_change_password = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    await client.async_change_user_password(mock_user, "oldpass", "newpass")
    mock_user.async_change_password.assert_awaited_once_with("oldpass", "newpass")


async def test_async_change_user_password_auth_error(hass):
    """Test CameDomoticAuthError during password change raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_user = MagicMock()
    mock_user.name = "testuser"
    mock_user.async_change_password = AsyncMock(
        side_effect=CameDomoticAuthError("bad creds")
    )

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_change_user_password(mock_user, "oldpass", "newpass")


async def test_async_change_user_password_server_error(hass):
    """Test CameDomoticServerError during password change raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_user = MagicMock()
    mock_user.name = "testuser"
    mock_user.async_change_password = AsyncMock(
        side_effect=CameDomoticServerError("server err")
    )

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_change_user_password(mock_user, "oldpass", "newpass")


async def test_async_change_user_password_generic_error(hass):
    """Test CameDomoticError during password change raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_user = MagicMock()
    mock_user.name = "testuser"
    mock_user.async_change_password = AsyncMock(side_effect=CameDomoticError("generic"))

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_change_user_password(mock_user, "oldpass", "newpass")


async def test_async_change_user_password_not_initialized(hass):
    """Test async_change_user_password raises ApiClientError when not connected."""
    client = _make_client(hass)
    mock_user = MagicMock()

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_change_user_password(mock_user, "oldpass", "newpass")


# --- async_get_terminal_groups ---


async def test_async_get_terminal_groups_success(hass):
    """Test successful terminal groups retrieval."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_groups = [MagicMock(), MagicMock()]
    mock_api.async_get_terminal_groups.return_value = mock_groups

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_terminal_groups()
    assert result is mock_groups


async def test_async_get_terminal_groups_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_terminal_groups.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_terminal_groups()


async def test_async_get_terminal_groups_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_terminal_groups.side_effect = CameDomoticServerError(
        "server err"
    )

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_terminal_groups()


async def test_async_get_terminal_groups_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_terminal_groups.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_terminal_groups()


async def test_async_get_terminal_groups_not_initialized(hass):
    """Test async_get_terminal_groups raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_get_terminal_groups()


# --- async_ping ---


async def test_async_ping_success(hass):
    """Test successful ping returns float latency in ms."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_ping.return_value = 12.5

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_ping()
    assert result == 12.5
    mock_api.async_ping.assert_awaited_once()


async def test_async_ping_auth_error(hass):
    """Test CameDomoticAuthError during ping raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_ping.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_ping()


async def test_async_ping_server_error(hass):
    """Test CameDomoticServerError during ping raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_ping.side_effect = CameDomoticServerError("timeout")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_ping()


async def test_async_ping_generic_error(hass):
    """Test CameDomoticError during ping raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_ping.side_effect = CameDomoticError("unexpected")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_ping()


async def test_async_ping_not_initialized(hass):
    """Test async_ping raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_ping()


# --- async_get_topology ---


async def test_async_get_topology_success(hass):
    """Test successful topology retrieval."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_topology = MagicMock()
    mock_topology.floors = [MagicMock(), MagicMock()]
    mock_api.async_get_topology.return_value = mock_topology

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_topology()
    assert result is mock_topology


async def test_async_get_topology_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_topology.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_topology()


async def test_async_get_topology_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_topology.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_topology()


async def test_async_get_topology_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_topology.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_topology()


async def test_async_get_topology_not_initialized(hass):
    """Test async_get_topology raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_get_topology()


# --- async_set_thermo_season ---


async def test_async_set_thermo_season_success(hass):
    """Test successful thermo season setting."""
    from aiocamedomotic.models import ThermoZoneSeason

    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    await client.async_set_thermo_season(ThermoZoneSeason.WINTER)
    mock_api.async_set_thermo_season.assert_awaited_once_with(ThermoZoneSeason.WINTER)


async def test_async_set_thermo_season_auth_error(hass):
    """Test CameDomoticAuthError during set_thermo_season raises AuthenticationError."""
    from aiocamedomotic.models import ThermoZoneSeason

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_set_thermo_season.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_set_thermo_season(ThermoZoneSeason.WINTER)


async def test_async_set_thermo_season_server_error(hass):
    """Test CameDomoticServerError during set_thermo_season raises CommunicationError."""
    from aiocamedomotic.models import ThermoZoneSeason

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_set_thermo_season.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_set_thermo_season(ThermoZoneSeason.SUMMER)


async def test_async_set_thermo_season_generic_error(hass):
    """Test CameDomoticError during set_thermo_season raises ApiClientError."""
    from aiocamedomotic.models import ThermoZoneSeason

    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_set_thermo_season.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_set_thermo_season(ThermoZoneSeason.PLANT_OFF)


async def test_async_set_thermo_season_not_initialized(hass):
    """Test async_set_thermo_season raises ApiClientError when not connected."""
    from aiocamedomotic.models import ThermoZoneSeason

    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_set_thermo_season(ThermoZoneSeason.WINTER)


# --- async_set_thermo_zone_mode ---


def _mock_zone():
    """Create a mock ThermoZone for zone-level API tests."""
    zone = MagicMock()
    zone.name = "Test Zone"
    zone.act_id = 1
    zone.async_set_mode = AsyncMock()
    zone.async_set_config = AsyncMock()
    zone.async_set_fan_speed = AsyncMock()
    return zone


async def test_async_set_thermo_zone_mode_success(hass):
    """Test successful zone mode setting."""
    from aiocamedomotic.models import ThermoZoneMode

    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    zone = _mock_zone()
    await client.async_set_thermo_zone_mode(zone, ThermoZoneMode.MANUAL)
    zone.async_set_mode.assert_awaited_once_with(ThermoZoneMode.MANUAL)


async def test_async_set_thermo_zone_mode_auth_error(hass):
    """Test CameDomoticAuthError during zone mode setting raises AuthenticationError."""
    from aiocamedomotic.models import ThermoZoneMode

    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    zone = _mock_zone()
    zone.async_set_mode.side_effect = CameDomoticAuthError("bad creds")

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_set_thermo_zone_mode(zone, ThermoZoneMode.OFF)


async def test_async_set_thermo_zone_mode_server_error(hass):
    """Test CameDomoticServerError during zone mode setting raises CommunicationError."""
    from aiocamedomotic.models import ThermoZoneMode

    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    zone = _mock_zone()
    zone.async_set_mode.side_effect = CameDomoticServerError("server err")

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_set_thermo_zone_mode(zone, ThermoZoneMode.AUTO)


async def test_async_set_thermo_zone_mode_generic_error(hass):
    """Test CameDomoticError during zone mode setting raises ApiClientError."""
    from aiocamedomotic.models import ThermoZoneMode

    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    zone = _mock_zone()
    zone.async_set_mode.side_effect = CameDomoticError("generic")

    with pytest.raises(CameDomoticApiClientError):
        await client.async_set_thermo_zone_mode(zone, ThermoZoneMode.MANUAL)


async def test_async_set_thermo_zone_mode_not_initialized(hass):
    """Test async_set_thermo_zone_mode raises ApiClientError when not connected."""
    from aiocamedomotic.models import ThermoZoneMode

    client = _make_client(hass)
    zone = _mock_zone()

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_set_thermo_zone_mode(zone, ThermoZoneMode.AUTO)


# --- async_set_thermo_zone_config ---


async def test_async_set_thermo_zone_config_success(hass):
    """Test successful zone config setting."""
    from aiocamedomotic.models import ThermoZoneFanSpeed, ThermoZoneMode

    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    zone = _mock_zone()
    await client.async_set_thermo_zone_config(
        zone, ThermoZoneMode.MANUAL, 22.5, fan_speed=ThermoZoneFanSpeed.AUTO
    )
    zone.async_set_config.assert_awaited_once_with(
        ThermoZoneMode.MANUAL, 22.5, fan_speed=ThermoZoneFanSpeed.AUTO
    )


async def test_async_set_thermo_zone_config_without_fan_speed(hass):
    """Test zone config setting without fan_speed parameter."""
    from aiocamedomotic.models import ThermoZoneMode

    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    zone = _mock_zone()
    await client.async_set_thermo_zone_config(zone, ThermoZoneMode.MANUAL, 21.0)
    zone.async_set_config.assert_awaited_once_with(
        ThermoZoneMode.MANUAL, 21.0, fan_speed=None
    )


async def test_async_set_thermo_zone_config_auth_error(hass):
    """Test CameDomoticAuthError during zone config setting raises AuthenticationError."""
    from aiocamedomotic.models import ThermoZoneMode

    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    zone = _mock_zone()
    zone.async_set_config.side_effect = CameDomoticAuthError("bad creds")

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_set_thermo_zone_config(zone, ThermoZoneMode.MANUAL, 22.0)


async def test_async_set_thermo_zone_config_server_error(hass):
    """Test CameDomoticServerError during zone config setting raises CommunicationError."""
    from aiocamedomotic.models import ThermoZoneMode

    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    zone = _mock_zone()
    zone.async_set_config.side_effect = CameDomoticServerError("server err")

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_set_thermo_zone_config(zone, ThermoZoneMode.MANUAL, 22.0)


async def test_async_set_thermo_zone_config_generic_error(hass):
    """Test CameDomoticError during zone config setting raises ApiClientError."""
    from aiocamedomotic.models import ThermoZoneMode

    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    zone = _mock_zone()
    zone.async_set_config.side_effect = CameDomoticError("generic")

    with pytest.raises(CameDomoticApiClientError):
        await client.async_set_thermo_zone_config(zone, ThermoZoneMode.MANUAL, 22.0)


async def test_async_set_thermo_zone_config_not_initialized(hass):
    """Test async_set_thermo_zone_config raises ApiClientError when not connected."""
    from aiocamedomotic.models import ThermoZoneMode

    client = _make_client(hass)
    zone = _mock_zone()

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_set_thermo_zone_config(zone, ThermoZoneMode.MANUAL, 22.0)


# --- async_set_thermo_zone_fan_speed ---


async def test_async_set_thermo_zone_fan_speed_success(hass):
    """Test successful zone fan speed setting."""
    from aiocamedomotic.models import ThermoZoneFanSpeed

    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    zone = _mock_zone()
    await client.async_set_thermo_zone_fan_speed(zone, ThermoZoneFanSpeed.FAST)
    zone.async_set_fan_speed.assert_awaited_once_with(ThermoZoneFanSpeed.FAST)


async def test_async_set_thermo_zone_fan_speed_server_error(hass):
    """Test CameDomoticServerError during fan speed setting raises CommunicationError."""
    from aiocamedomotic.models import ThermoZoneFanSpeed

    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    zone = _mock_zone()
    zone.async_set_fan_speed.side_effect = CameDomoticServerError("server err")

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_set_thermo_zone_fan_speed(zone, ThermoZoneFanSpeed.SLOW)


async def test_async_set_thermo_zone_fan_speed_auth_error(hass):
    """Test CameDomoticAuthError during fan speed setting raises AuthenticationError."""
    from aiocamedomotic.models import ThermoZoneFanSpeed

    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    zone = _mock_zone()
    zone.async_set_fan_speed.side_effect = CameDomoticAuthError("bad creds")

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_set_thermo_zone_fan_speed(zone, ThermoZoneFanSpeed.FAST)


async def test_async_set_thermo_zone_fan_speed_generic_error(hass):
    """Test CameDomoticError during fan speed setting raises ApiClientError."""
    from aiocamedomotic.models import ThermoZoneFanSpeed

    client = _make_client(hass)
    mock_api = AsyncMock()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    zone = _mock_zone()
    zone.async_set_fan_speed.side_effect = CameDomoticError("generic")

    with pytest.raises(CameDomoticApiClientError):
        await client.async_set_thermo_zone_fan_speed(zone, ThermoZoneFanSpeed.MEDIUM)


async def test_async_set_thermo_zone_fan_speed_not_initialized(hass):
    """Test async_set_thermo_zone_fan_speed raises ApiClientError when not connected."""
    from aiocamedomotic.models import ThermoZoneFanSpeed

    client = _make_client(hass)
    zone = _mock_zone()

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_set_thermo_zone_fan_speed(zone, ThermoZoneFanSpeed.AUTO)


# --- async_get_timers ---


async def test_async_get_timers_success(hass):
    """Test successful timers retrieval."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_timers = [MagicMock(), MagicMock()]
    mock_api.async_get_timers.return_value = mock_timers

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    result = await client.async_get_timers()
    assert result is mock_timers


async def test_async_get_timers_auth_error(hass):
    """Test CameDomoticAuthError raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_timers.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_get_timers()


async def test_async_get_timers_server_error(hass):
    """Test CameDomoticServerError raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_timers.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_get_timers()


async def test_async_get_timers_generic_error(hass):
    """Test CameDomoticError raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    mock_api.async_get_timers.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_get_timers()


async def test_async_get_timers_not_initialized(hass):
    """Test async_get_timers raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_get_timers()


# --- async_enable_timer ---


def _mock_timer():
    """Create a mock Timer object for API tests."""
    timer = MagicMock()
    timer.name = "Morning Timer"
    timer.id = 900
    timer.async_enable = AsyncMock()
    timer.async_disable = AsyncMock()
    timer.async_enable_day = AsyncMock()
    timer.async_disable_day = AsyncMock()
    timer.async_set_timetable = AsyncMock()
    return timer


async def test_async_enable_timer_success(hass):
    """Test successful timer enable."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    await client.async_enable_timer(timer)
    timer.async_enable.assert_awaited_once()


async def test_async_enable_timer_auth_error(hass):
    """Test CameDomoticAuthError during enable raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()
    timer.async_enable.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_enable_timer(timer)


async def test_async_enable_timer_server_error(hass):
    """Test CameDomoticServerError during enable raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()
    timer.async_enable.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_enable_timer(timer)


async def test_async_enable_timer_generic_error(hass):
    """Test CameDomoticError during enable raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()
    timer.async_enable.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_enable_timer(timer)


async def test_async_enable_timer_not_initialized(hass):
    """Test async_enable_timer raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_enable_timer(_mock_timer())


# --- async_disable_timer ---


async def test_async_disable_timer_success(hass):
    """Test successful timer disable."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    await client.async_disable_timer(timer)
    timer.async_disable.assert_awaited_once()


async def test_async_disable_timer_auth_error(hass):
    """Test CameDomoticAuthError during disable raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()
    timer.async_disable.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_disable_timer(timer)


async def test_async_disable_timer_server_error(hass):
    """Test CameDomoticServerError during disable raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()
    timer.async_disable.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_disable_timer(timer)


async def test_async_disable_timer_generic_error(hass):
    """Test CameDomoticError during disable raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()
    timer.async_disable.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_disable_timer(timer)


async def test_async_disable_timer_not_initialized(hass):
    """Test async_disable_timer raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_disable_timer(_mock_timer())


# --- async_enable_timer_day ---


async def test_async_enable_timer_day_success(hass):
    """Test successful day enable."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    await client.async_enable_timer_day(timer, 2)
    timer.async_enable_day.assert_awaited_once_with(2)


async def test_async_enable_timer_day_auth_error(hass):
    """Test CameDomoticAuthError during day enable raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()
    timer.async_enable_day.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_enable_timer_day(timer, 0)


async def test_async_enable_timer_day_not_initialized(hass):
    """Test async_enable_timer_day raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_enable_timer_day(_mock_timer(), 0)


# --- async_disable_timer_day ---


async def test_async_disable_timer_day_success(hass):
    """Test successful day disable."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    await client.async_disable_timer_day(timer, 5)
    timer.async_disable_day.assert_awaited_once_with(5)


async def test_async_disable_timer_day_auth_error(hass):
    """Test CameDomoticAuthError during day disable raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()
    timer.async_disable_day.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_disable_timer_day(timer, 0)


async def test_async_disable_timer_day_not_initialized(hass):
    """Test async_disable_timer_day raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_disable_timer_day(_mock_timer(), 0)


# --- async_set_timer_timetable ---


async def test_async_set_timer_timetable_success(hass):
    """Test successful timetable setting."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    slots = [(8, 0, 0), (12, 0, 0), None, None]
    await client.async_set_timer_timetable(timer, slots)
    timer.async_set_timetable.assert_awaited_once_with(slots)


async def test_async_set_timer_timetable_auth_error(hass):
    """Test CameDomoticAuthError during timetable set raises AuthenticationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()
    timer.async_set_timetable.side_effect = CameDomoticAuthError("bad creds")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientAuthenticationError):
        await client.async_set_timer_timetable(timer, [None, None, None, None])


async def test_async_set_timer_timetable_server_error(hass):
    """Test CameDomoticServerError during timetable set raises CommunicationError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()
    timer.async_set_timetable.side_effect = CameDomoticServerError("server err")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientCommunicationError):
        await client.async_set_timer_timetable(timer, [None, None, None, None])


async def test_async_set_timer_timetable_generic_error(hass):
    """Test CameDomoticError during timetable set raises ApiClientError."""
    client = _make_client(hass)
    mock_api = AsyncMock()
    timer = _mock_timer()
    timer.async_set_timetable.side_effect = CameDomoticError("generic")

    with patch(_PATCH_ASYNC_CREATE, return_value=mock_api):
        await client.async_connect()

    with pytest.raises(CameDomoticApiClientError):
        await client.async_set_timer_timetable(timer, [None, None, None, None])


async def test_async_set_timer_timetable_not_initialized(hass):
    """Test async_set_timer_timetable raises ApiClientError when not connected."""
    client = _make_client(hass)

    with pytest.raises(CameDomoticApiClientError, match="Not initialized"):
        await client.async_set_timer_timetable(_mock_timer(), [None, None, None, None])
