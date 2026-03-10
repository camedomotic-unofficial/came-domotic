"""Global fixtures for CAME Domotic Unofficial integration."""

from unittest.mock import MagicMock, patch

import pytest

from custom_components.came_domotic_unofficial.api import (
    CameDomoticUnofficialApiClientAuthenticationError,
    CameDomoticUnofficialApiClientCommunicationError,
)
from custom_components.came_domotic_unofficial.models import CameDomoticServerData

from .const import MOCK_KEYCODE

pytest_plugins = "pytest_homeassistant_custom_component"

_API_CLIENT = (
    "custom_components.came_domotic_unofficial.api.CameDomoticUnofficialApiClient"
)
_COORDINATOR = (
    "custom_components.came_domotic_unofficial.coordinator"
    ".CameDomoticUnofficialDataUpdateCoordinator"
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
    leaf=True,
):
    """Create a mock ThermoZone object with all required attributes.

    Includes a raw_data dict so that coordinator merge logic
    (raw_data.update) works correctly in tests.
    """
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
    zone.leaf = leaf
    zone.raw_data = {
        "act_id": act_id,
        "name": name,
        "temp_dec": int(temperature * 10),
        "set_point": int(set_point * 10),
        "mode": 2 if mode == "AUTO" else 1,
        "season": 1 if season == "winter" else 2,
        "status": status,
        "antifreeze": int(antifreeze * 10) if antifreeze is not None else 0,
        "leaf": int(leaf),
        "floor_ind": floor_ind,
        "room_ind": room_ind,
    }
    return zone


MOCK_THERMO_ZONES = [
    _mock_thermo_zone(1, "Living Room", 20.0, set_point=21.0, floor_ind=0, room_ind=0),
    _mock_thermo_zone(
        52, "Bedroom", 19.5, set_point=20.0, mode="MANUAL", floor_ind=1, room_ind=1
    ),
]


def _mock_scenario(
    scenario_id,
    name,
    scenario_status="OFF",
    user_defined=1,
    icon_id=0,
    status=0,
):
    """Create a mock Scenario object with all required attributes.

    Includes a raw_data dict so that coordinator merge logic
    (raw_data.update) works correctly in tests.
    """
    scenario = MagicMock()
    scenario.id = scenario_id
    scenario.name = name
    scenario.scenario_status.name = scenario_status
    scenario.user_defined = user_defined
    scenario.icon_id = icon_id
    scenario.status = status
    scenario.raw_data = {
        "id": scenario_id,
        "name": name,
        "status": status,
        "icon_id": icon_id,
        "user_defined": user_defined,
    }
    return scenario


MOCK_SCENARIOS = [
    _mock_scenario(10, "Good Morning"),
    _mock_scenario(20, "Good Night", user_defined=0),
]


def _mock_server_info():
    """Create a mock ServerInfo object."""
    info = MagicMock()
    info.keycode = MOCK_KEYCODE
    info.swver = "1.2.3"
    info.type = "ETI/Domo"
    info.board = "board_v1"
    info.serial = "0011FFEE"
    return info


MOCK_SERVER_INFO = _mock_server_info()

MOCK_SERVER_DATA = CameDomoticServerData(
    server_info=MOCK_SERVER_INFO,
    thermo_zones={z.act_id: z for z in MOCK_THERMO_ZONES},
    scenarios={s.id: s for s in MOCK_SCENARIOS},
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests via the plugin fixture."""
    return


@pytest.fixture(name="bypass_get_data")
def bypass_get_data_fixture():
    """Skip calls to get data from API and suppress long-poll task."""
    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            return_value=_mock_server_info(),
        ),
        patch(
            f"{_API_CLIENT}.async_get_thermo_zones",
            return_value=list(MOCK_THERMO_ZONES),
        ),
        patch(
            f"{_API_CLIENT}.async_get_scenarios",
            return_value=list(MOCK_SCENARIOS),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch(f"{_COORDINATOR}.start_long_poll"),
    ):
        yield


@pytest.fixture(name="error_on_get_data")
def error_get_data_fixture():
    """Simulate communication error when retrieving data from API."""
    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            side_effect=CameDomoticUnofficialApiClientCommunicationError(
                "Connection error"
            ),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch(f"{_COORDINATOR}.start_long_poll"),
    ):
        yield


@pytest.fixture(name="auth_error_on_get_data")
def auth_error_get_data_fixture():
    """Simulate authentication error when retrieving data from API."""
    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            side_effect=CameDomoticUnofficialApiClientAuthenticationError(
                "Invalid credentials"
            ),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch(f"{_COORDINATOR}.start_long_poll"),
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
