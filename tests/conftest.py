"""Global fixtures for CAME Domotic Unofficial integration."""

from unittest.mock import MagicMock, patch

from aiocamedomotic.models import LightStatus, LightType, OpeningStatus, OpeningType
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


def _mock_opening(
    open_act_id,
    close_act_id,
    name,
    status=OpeningStatus.STOPPED,
    opening_type=OpeningType.SHUTTER,
    floor_ind=0,
    room_ind=0,
):
    """Create a mock Opening object with all required attributes.

    Includes a raw_data dict so that coordinator merge logic
    (raw_data.update) works correctly in tests.
    """
    opening = MagicMock()
    opening.open_act_id = open_act_id
    opening.close_act_id = close_act_id
    opening.name = name
    opening.status = status
    opening.type = opening_type
    opening.floor_ind = floor_ind
    opening.room_ind = room_ind
    opening.raw_data = {
        "open_act_id": open_act_id,
        "close_act_id": close_act_id,
        "name": name,
        "status": status.value,
        "type": opening_type.value,
        "floor_ind": floor_ind,
        "room_ind": room_ind,
    }
    return opening


MOCK_OPENINGS = [
    _mock_opening(100, 101, "Living Room Shutter"),
    _mock_opening(200, 201, "Bedroom Shutter", floor_ind=1, room_ind=1),
]


def _mock_light(
    act_id,
    name,
    status=LightStatus.OFF,
    light_type=LightType.STEP_STEP,
    perc=None,
    rgb=None,
    floor_ind=0,
    room_ind=0,
):
    """Create a mock Light object with all required attributes.

    Includes a raw_data dict so that coordinator merge logic
    (raw_data.update) works correctly in tests.
    """
    light = MagicMock()
    light.act_id = act_id
    light.name = name
    light.status = status
    light.type = light_type
    light.perc = perc
    light.rgb = rgb
    light.floor_ind = floor_ind
    light.room_ind = room_ind
    light.raw_data = {
        "act_id": act_id,
        "name": name,
        "status": status.value,
        "type": light_type.value,
        "perc": perc if perc is not None else 0,
        "floor_ind": floor_ind,
        "room_ind": room_ind,
    }
    if rgb is not None:
        light.raw_data["rgb"] = list(rgb)
    return light


MOCK_LIGHTS = [
    _mock_light(300, "Hallway Light"),
    _mock_light(
        301,
        "Living Room Dimmer",
        light_type=LightType.DIMMER,
        perc=75,
    ),
    _mock_light(
        302,
        "Bedroom RGB",
        light_type=LightType.RGB,
        perc=50,
        rgb=[255, 128, 0],
    ),
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
    openings={o.open_act_id: o for o in MOCK_OPENINGS},
    lights={lt.act_id: lt for lt in MOCK_LIGHTS},
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
        patch(
            f"{_API_CLIENT}.async_get_openings",
            return_value=list(MOCK_OPENINGS),
        ),
        patch(
            f"{_API_CLIENT}.async_get_lights",
            return_value=list(MOCK_LIGHTS),
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
