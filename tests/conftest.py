"""Global fixtures for CAME Domotic Unofficial integration."""
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest

from custom_components.came_domotic_unofficial.api import (
    CameDomoticUnofficialApiClientAuthenticationError,
    CameDomoticUnofficialApiClientCommunicationError,
)

from .const import MOCK_KEYCODE

pytest_plugins = "pytest_homeassistant_custom_component"

_API_CLIENT = (
    "custom_components.came_domotic_unofficial.api."
    "CameDomoticUnofficialApiClient"
)

# Mock data matching what async_get_data() returns from the CAME server
MOCK_API_DATA = {
    "keycode": MOCK_KEYCODE,
    "software_version": "1.2.3",
    "server_type": "ETI/Domo",
    "board": "board_v1",
}


def _mock_server_info():
    """Create a mock ServerInfo object."""
    info = MagicMock()
    info.keycode = MOCK_KEYCODE
    info.swver = "1.2.3"
    info.type = "ETI/Domo"
    info.board = "board_v1"
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
