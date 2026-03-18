"""Global fixtures for CAME Domotic integration."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from aiocamedomotic.models import (
    AnalogSensorType,
    DigitalInputStatus,
    DigitalInputType,
    LightStatus,
    LightType,
    OpeningStatus,
    OpeningType,
    RelayStatus,
    ThermoZoneFanSpeed,
    ThermoZoneMode,
    ThermoZoneSeason,
    ThermoZoneStatus,
)
import pytest

from custom_components.came_domotic.api import (
    CameDomoticApiClientAuthenticationError,
    CameDomoticApiClientCommunicationError,
)
from custom_components.came_domotic.models import CameDomoticServerData

from .const import MOCK_KEYCODE

pytest_plugins = "pytest_homeassistant_custom_component"

_API_CLIENT = "custom_components.came_domotic.api.CameDomoticApiClient"
_COORDINATOR = (
    "custom_components.came_domotic.coordinator.CameDomoticDataUpdateCoordinator"
)


def _mock_thermo_zone(
    act_id,
    name,
    temperature,
    set_point=21.0,
    mode=ThermoZoneMode.AUTO,
    season=ThermoZoneSeason.WINTER,
    status=ThermoZoneStatus.ON,
    antifreeze=5.0,
    floor_ind=0,
    room_ind=0,
    leaf=True,
    fan_speed=ThermoZoneFanSpeed.AUTO,
    dehumidifier_enabled=False,
    dehumidifier_setpoint=None,
    t1=None,
    t2=None,
    t3=None,
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
    zone.mode = mode
    zone.season = season
    zone.status = status
    zone.antifreeze = antifreeze
    zone.floor_ind = floor_ind
    zone.room_ind = room_ind
    zone.leaf = leaf
    zone.fan_speed = fan_speed
    zone.dehumidifier_enabled = dehumidifier_enabled
    zone.dehumidifier_setpoint = dehumidifier_setpoint
    zone.t1 = t1
    zone.t2 = t2
    zone.t3 = t3
    zone.raw_data = {
        "act_id": act_id,
        "name": name,
        "temp_dec": int(temperature * 10),
        "set_point": int(set_point * 10),
        "mode": mode.value,
        "season": season.value,
        "status": status.value,
        "antifreeze": int(antifreeze * 10) if antifreeze is not None else 0,
        "leaf": int(leaf),
        "floor_ind": floor_ind,
        "room_ind": room_ind,
    }
    return zone


MOCK_THERMO_ZONES = [
    _mock_thermo_zone(1, "Living Room", 20.0, set_point=21.0, floor_ind=0, room_ind=0),
    _mock_thermo_zone(
        52,
        "Bedroom",
        19.5,
        set_point=20.0,
        mode=ThermoZoneMode.MANUAL,
        floor_ind=1,
        room_ind=1,
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


def _mock_digital_input(
    act_id,
    name,
    status=DigitalInputStatus.IDLE,
    input_type=DigitalInputType.STATUS,
    addr=0,
    utc_time=0,
):
    """Create a mock DigitalInput object with all required attributes.

    Includes a raw_data dict so that coordinator merge logic
    (raw_data.update) works correctly in tests.
    """
    di = MagicMock()
    di.act_id = act_id
    di.name = name
    di.status = status
    di.type = input_type
    di.addr = addr
    di.utc_time = utc_time
    di.raw_data = {
        "act_id": act_id,
        "name": name,
        "status": status.value,
        "type": input_type.value,
        "addr": addr,
        "utc_time": utc_time,
    }
    return di


MOCK_DIGITAL_INPUTS = [
    _mock_digital_input(400, "Front Door Sensor"),
    _mock_digital_input(
        401, "Window Contact", status=DigitalInputStatus.ACTIVE, utc_time=1700000000
    ),
]


def _mock_analog_sensor(
    act_id,
    name,
    value,
    unit="C",
    sensor_type=AnalogSensorType.TEMPERATURE,
):
    """Create a mock AnalogSensor object with all required attributes.

    Includes a raw_data dict so that coordinator logic works correctly in tests.
    """
    sensor = MagicMock()
    sensor.act_id = act_id
    sensor.name = name
    sensor.value = value
    sensor.unit = unit
    sensor.sensor_type = sensor_type
    sensor.raw_data = {
        "act_id": act_id,
        "name": name,
        "value": value,
        "unit": unit,
    }
    return sensor


MOCK_ANALOG_SENSORS = [
    _mock_analog_sensor(
        500,
        "Outdoor Temperature",
        15.5,
        unit="C",
        sensor_type=AnalogSensorType.TEMPERATURE,
    ),
    _mock_analog_sensor(
        501,
        "Indoor Humidity",
        45.0,
        unit="%",
        sensor_type=AnalogSensorType.HUMIDITY,
    ),
]


def _mock_analog_input(act_id, name, value, unit="C"):
    """Create a mock AnalogIn object with all required attributes.

    Includes a raw_data dict so that coordinator merge logic works correctly
    in tests.
    """
    ai = MagicMock()
    ai.act_id = act_id
    ai.name = name
    ai.value = value
    ai.unit = unit
    ai.raw_data = {"act_id": act_id, "name": name, "value": value, "unit": unit}
    return ai


MOCK_ANALOG_INPUTS = [
    _mock_analog_input(800, "Garden Thermometer", 22.5, unit="C"),
    _mock_analog_input(801, "Basement Hygrometer", 65.0, unit="%"),
]


def _mock_relay(
    act_id,
    name,
    status=RelayStatus.OFF,
    floor_ind=0,
    room_ind=0,
):
    """Create a mock Relay object with all required attributes.

    Includes a raw_data dict so that coordinator merge logic
    (raw_data.update) works correctly in tests.
    """
    relay = MagicMock()
    relay.act_id = act_id
    relay.name = name
    relay.status = status
    relay.floor_ind = floor_ind
    relay.room_ind = room_ind
    relay.raw_data = {
        "act_id": act_id,
        "name": name,
        "status": status.value,
        "floor_ind": floor_ind,
        "room_ind": room_ind,
    }
    return relay


MOCK_RELAYS = [
    _mock_relay(600, "Pump Control"),
    _mock_relay(601, "Heating Relay", floor_ind=1, room_ind=1),
]


def _mock_timer_time_slot(
    index,
    start_hour=8,
    start_min=0,
    start_sec=0,
    stop_hour=12,
    stop_min=0,
    stop_sec=0,
    active=True,
):
    """Create a mock TimerTimeSlot object."""
    slot = MagicMock()
    slot.index = index
    slot.start_hour = start_hour
    slot.start_min = start_min
    slot.start_sec = start_sec
    slot.stop_hour = stop_hour
    slot.stop_min = stop_min
    slot.stop_sec = stop_sec
    slot.active = active
    return slot


def _mock_timer(
    timer_id,
    name,
    enabled=True,
    days=0b0011111,
    bars=1,
    timetable=None,
    active_days=None,
):
    """Create a mock Timer object with all required attributes.

    Includes a raw_data dict so that coordinator merge logic
    (raw_data.update) works correctly in tests.
    """
    day_names = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    if active_days is None:
        active_days = [day_names[i] for i in range(7) if days & (1 << i)]
    timer = MagicMock()
    timer.id = timer_id
    timer.name = name
    timer.enabled = enabled
    timer.days = days
    timer.active_days = active_days
    timer.bars = bars
    timer.timetable = timetable or []
    timer.raw_data = {
        "id": timer_id,
        "name": name,
        "enabled": int(enabled),
        "days": days,
        "bars": bars,
    }
    return timer


MOCK_TIMERS = [
    _mock_timer(
        900,
        "Morning Timer",
        enabled=True,
        days=0b0011111,
        bars=1,
        timetable=[_mock_timer_time_slot(0, 8, 0, 0, 12, 0, 0)],
    ),
    _mock_timer(
        901,
        "Weekend Timer",
        enabled=False,
        days=0b1100000,
        bars=2,
        timetable=[
            _mock_timer_time_slot(0, 9, 0, 0, 13, 0, 0),
            _mock_timer_time_slot(1, 15, 30, 0, 18, 0, 0),
        ],
    ),
]


def _mock_camera(
    camera_id,
    name,
    uri="",
    uri_still="",
    stream_type="mjpeg",
    is_flash=False,
):
    """Create a mock Camera object with all required attributes.

    Includes a raw_data dict for consistency with other mock factories.
    """
    camera = MagicMock()
    camera.id = camera_id
    camera.name = name
    camera.uri = uri
    camera.uri_still = uri_still
    camera.stream_type = stream_type
    camera.is_flash = is_flash
    camera.raw_data = {
        "id": camera_id,
        "name": name,
    }
    return camera


MOCK_CAMERAS = [
    _mock_camera(
        700,
        "Front Door Camera",
        uri="rtsp://192.168.1.50/stream1",
        uri_still="http://192.168.1.50/snapshot.jpg",
    ),
    _mock_camera(
        701,
        "Garden Camera",
        uri_still="http://192.168.1.51/snapshot.jpg",
        stream_type="swf",
        is_flash=True,
    ),
]


def _mock_map_page(
    page_id,
    page_label,
    background="images/floor plan.jpg",
    page_scale=1024,
    elements=None,
):
    """Create a mock MapPage object with all required attributes."""
    page = MagicMock()
    page.page_id = page_id
    page.page_label = page_label
    page.background = background
    page.page_scale = page_scale
    page.elements = elements or []
    return page


MOCK_MAP_PAGES = [
    _mock_map_page(0, "Ground Floor", background="images/ground floor.jpg"),
    _mock_map_page(1, "First Floor", background="images/first_floor.png"),
]


def _mock_topology_room(room_id, name):
    """Create a mock TopologyRoom object."""
    room = MagicMock()
    room.id = room_id
    room.name = name
    return room


def _mock_topology_floor(floor_id, name, rooms=None):
    """Create a mock TopologyFloor object."""
    floor = MagicMock()
    floor.id = floor_id
    floor.name = name
    floor.rooms = rooms or []
    return floor


def _mock_topology():
    """Create a mock PlantTopology object."""
    topology = MagicMock()
    topology.floors = [
        _mock_topology_floor(
            0,
            "Ground Floor",
            rooms=[_mock_topology_room(0, "Living Room")],
        ),
        _mock_topology_floor(
            1,
            "First Floor",
            rooms=[_mock_topology_room(1, "Bedroom")],
        ),
    ]
    return topology


MOCK_TOPOLOGY = _mock_topology()


def _mock_server_info(
    features=None,
):
    """Create a mock ServerInfo object.

    Args:
        features: List of feature strings the server supports.
            Defaults to all known features so existing tests keep working.
    """
    if features is None:
        features = [
            "lights",
            "openings",
            "thermoregulation",
            "scenarios",
            "digitalin",
            "analogin",
            "relays",
            "timers",
        ]
    info = MagicMock()
    info.keycode = MOCK_KEYCODE
    info.swver = "1.2.3"
    info.type = "ETI/Domo"
    info.board = "board_v1"
    info.serial = "0011FFEE"
    info.features = features
    return info


MOCK_SERVER_INFO = _mock_server_info()

MOCK_SERVER_DATA = CameDomoticServerData(
    server_info=MOCK_SERVER_INFO,
    thermo_zones={z.act_id: z for z in MOCK_THERMO_ZONES},
    scenarios={s.id: s for s in MOCK_SCENARIOS},
    openings={o.open_act_id: o for o in MOCK_OPENINGS},
    lights={lt.act_id: lt for lt in MOCK_LIGHTS},
    digital_inputs={di.act_id: di for di in MOCK_DIGITAL_INPUTS},
    analog_sensors={s.act_id: s for s in MOCK_ANALOG_SENSORS},
    analog_inputs={ai.act_id: ai for ai in MOCK_ANALOG_INPUTS},
    relays={r.act_id: r for r in MOCK_RELAYS},
    timers={t.id: t for t in MOCK_TIMERS},
    cameras={c.id: c for c in MOCK_CAMERAS},
    maps={p.page_id: p for p in MOCK_MAP_PAGES},
    topology=MOCK_TOPOLOGY,
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
        patch(
            f"{_API_CLIENT}.async_get_digital_inputs",
            return_value=list(MOCK_DIGITAL_INPUTS),
        ),
        patch(
            f"{_API_CLIENT}.async_get_analog_sensors",
            return_value=list(MOCK_ANALOG_SENSORS),
        ),
        patch(
            f"{_API_CLIENT}.async_get_analog_inputs",
            return_value=list(MOCK_ANALOG_INPUTS),
        ),
        patch(
            f"{_API_CLIENT}.async_get_relays",
            return_value=list(MOCK_RELAYS),
        ),
        patch(
            f"{_API_CLIENT}.async_get_timers",
            return_value=list(MOCK_TIMERS),
        ),
        patch(
            f"{_API_CLIENT}.async_get_cameras",
            return_value=list(MOCK_CAMERAS),
        ),
        patch(
            f"{_API_CLIENT}.async_get_map_pages",
            return_value=list(MOCK_MAP_PAGES),
        ),
        patch(
            f"{_API_CLIENT}.async_get_topology",
            return_value=_mock_topology(),
        ),
        patch(f"{_API_CLIENT}.async_ping", return_value=10.0),
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
            side_effect=CameDomoticApiClientCommunicationError("Connection error"),
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
            side_effect=CameDomoticApiClientAuthenticationError("Invalid credentials"),
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
