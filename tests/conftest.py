"""Global fixtures for CAME Domotic Unofficial integration."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.came_domotic_unofficial.api import (
    CameDomoticUnofficialApiClientAuthenticationError,
    CameDomoticUnofficialApiClientCommunicationError,
)

from .const import MOCK_KEYCODE

pytest_plugins = "pytest_homeassistant_custom_component"

_API_CLIENT = (
    "custom_components.came_domotic_unofficial.api." "CameDomoticUnofficialApiClient"
)


def _mock_thermo_zone(
    act_id,
    name,
    temperature,
    set_point=21.0,
    mode="AUTO",
    season="winter",
    status=1,
    antifreeze=5.0,
    floor_ind=0,
    room_ind=0,
):
    """Create a mock ThermoZone object."""
    zone = MagicMock()
    zone.act_id = act_id
    zone.name = name
    zone.temperature = temperature
    zone.set_point = set_point
    zone.mode.name = mode
    zone.season.name = season
    zone.status.name = "ON" if status else "OFF"
    zone.antifreeze = antifreeze
    zone.floor_ind = floor_ind
    zone.room_ind = room_ind
    return zone


MOCK_THERMO_ZONES = [
    _mock_thermo_zone(1, "Living Room", 20.0, set_point=21.0, floor_ind=0, room_ind=0),
    _mock_thermo_zone(
        52, "Bedroom", 19.5, set_point=20.0, mode="MANUAL", floor_ind=1, room_ind=1
    ),
]

# Mock data matching what async_get_data() returns from the CAME server
MOCK_API_DATA = {
    "keycode": MOCK_KEYCODE,
    "software_version": "1.2.3",
    "server_type": "ETI/Domo",
    "board": "board_v1",
    "serial_number": "0011FFEE",
    "thermo_zones": MOCK_THERMO_ZONES,
}


def _mock_server_info():
    """Create a mock ServerInfo object."""
    info = MagicMock()
    info.keycode = MOCK_KEYCODE
    info.swver = "1.2.3"
    info.type = "ETI/Domo"
    info.board = "board_v1"
    info.serial = "0011FFEE"
    return info


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests via the plugin fixture."""
    return


@pytest.fixture(name="bypass_get_data")
def bypass_get_data_fixture():
    """Skip calls to get data from API, returning realistic mock data."""
    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(f"{_API_CLIENT}.async_get_data", return_value=MOCK_API_DATA),
        patch(f"{_API_CLIENT}.async_dispose"),
    ):
        yield


@pytest.fixture(name="error_on_get_data")
def error_get_data_fixture():
    """Simulate communication error when retrieving data from API."""
    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_data",
            side_effect=CameDomoticUnofficialApiClientCommunicationError(
                "Connection error"
            ),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
    ):
        yield


@pytest.fixture(name="auth_error_on_get_data")
def auth_error_get_data_fixture():
    """Simulate authentication error when retrieving data from API."""
    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_data",
            side_effect=CameDomoticUnofficialApiClientAuthenticationError(
                "Invalid credentials"
            ),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
    ):
        yield


@pytest.fixture(name="bypass_test_credentials")
def bypass_test_credentials_fixture():
    """Mock credential validation (async_connect + async_get_server_info)."""
    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            return_value=_mock_server_info(),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
    ):
        yield
