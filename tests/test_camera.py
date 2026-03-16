"""Test CAME Domotic camera platform (TVCC cameras)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from homeassistant.components.camera import CameraEntityFeature
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic.api import (
    CameDomoticApiClientCommunicationError,
)
from custom_components.came_domotic.const import DOMAIN
from custom_components.came_domotic.models import CameDomoticServerData

from .conftest import _mock_camera, _mock_server_info, _mock_topology
from .const import MOCK_CONFIG

_API_CLIENT = "custom_components.came_domotic.api.CameDomoticApiClient"

_COORDINATOR = (
    "custom_components.came_domotic.coordinator.CameDomoticDataUpdateCoordinator"
)


def _mock_aiohttp_get(resp=None, side_effect=None):
    """Return a callable mimicking session.get() as an async context manager."""
    cm = MagicMock()
    if side_effect:
        cm.__aenter__ = AsyncMock(side_effect=side_effect)
    else:
        cm.__aenter__ = AsyncMock(return_value=resp)
    cm.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=cm)


def _get_camera_entity(hass, entity_id="camera.front_door_camera"):
    """Return the camera entity object for the given entity_id."""
    for state in hass.states.async_all("camera"):
        if state.entity_id == entity_id:
            return hass.data["camera"].get_entity(state.entity_id)
    return None


async def _setup_entry(hass, mock_cameras):
    """Set up a config entry with the given mock cameras list."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            return_value=_mock_server_info(),
        ),
        patch(f"{_API_CLIENT}.async_get_thermo_zones", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_scenarios", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_openings", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_lights", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_digital_inputs", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_analog_sensors", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_relays", return_value=[]),
        patch(
            f"{_API_CLIENT}.async_get_cameras",
            return_value=mock_cameras,
        ),
        patch(
            f"{_API_CLIENT}.async_get_topology",
            return_value=_mock_topology(),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch(f"{_COORDINATOR}.start_long_poll"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    return config_entry


# --- Entity creation ---


async def test_camera_entities_created(hass, bypass_get_data):
    """Test that one camera entity is created per TVCC camera."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "camera"
    ]
    assert len(entries) == 2


async def test_camera_unique_id(hass, bypass_get_data):
    """Test camera unique IDs follow the expected pattern."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "camera"
    }
    assert unique_ids == {
        "test_camera_700",
        "test_camera_701",
    }


async def test_camera_state(hass, bypass_get_data):
    """Test camera entities exist with expected entity IDs."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    front_door = hass.states.get("camera.front_door_camera")
    assert front_door is not None

    garden = hass.states.get("camera.garden_camera")
    assert garden is not None


async def test_no_cameras(hass):
    """Test no camera entities created when there are no cameras."""
    config_entry = await _setup_entry(hass, [])

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "camera"
    ]
    assert len(entries) == 0


# --- Stream source ---


async def test_stream_source_rtsp(hass):
    """Test stream_source returns RTSP URI when available."""
    cameras = [
        _mock_camera(
            700,
            "Front Door Camera",
            uri="rtsp://192.168.1.50/stream1",
            uri_still="http://192.168.1.50/snapshot.jpg",
        ),
    ]
    await _setup_entry(hass, cameras)

    state = hass.states.get("camera.front_door_camera")
    assert state is not None
    assert state.state == "streaming"


async def test_stream_source_none_when_flash(hass):
    """Test stream_source returns None for Flash (SWF) cameras."""
    cameras = [
        _mock_camera(
            700,
            "Flash Camera",
            uri="http://192.168.1.50/stream.swf",
            uri_still="http://192.168.1.50/snapshot.jpg",
            stream_type="swf",
            is_flash=True,
        ),
    ]
    await _setup_entry(hass, cameras)

    state = hass.states.get("camera.flash_camera")
    assert state is not None
    assert state.state == "idle"


async def test_stream_source_none_when_empty_uri(hass):
    """Test stream_source returns None when uri is empty."""
    cameras = [
        _mock_camera(
            700,
            "Still Camera",
            uri="",
            uri_still="http://192.168.1.50/snapshot.jpg",
        ),
    ]
    await _setup_entry(hass, cameras)

    state = hass.states.get("camera.still_camera")
    assert state is not None
    assert state.state == "idle"


async def test_stream_source_none_when_non_rtsp(hass):
    """Test stream_source returns None for non-RTSP URIs."""
    cameras = [
        _mock_camera(
            700,
            "HTTP Camera",
            uri="http://192.168.1.50/stream",
            uri_still="http://192.168.1.50/snapshot.jpg",
        ),
    ]
    await _setup_entry(hass, cameras)

    state = hass.states.get("camera.http_camera")
    assert state is not None
    assert state.state == "idle"


# --- Supported features ---


async def test_stream_source_async(hass):
    """Test the async stream_source method returns the RTSP URI."""
    cameras = [
        _mock_camera(
            700,
            "Front Door Camera",
            uri="rtsp://192.168.1.50/stream1",
        ),
    ]
    await _setup_entry(hass, cameras)

    entity = None
    for state in hass.states.async_all("camera"):
        if state.entity_id == "camera.front_door_camera":
            entity = hass.data["camera"].get_entity(state.entity_id)
            break
    assert entity is not None
    result = await entity.stream_source()
    assert result == "rtsp://192.168.1.50/stream1"


async def test_supported_features_stream(hass):
    """Test STREAM feature is set for RTSP cameras."""
    cameras = [
        _mock_camera(
            700,
            "Front Door Camera",
            uri="rtsp://192.168.1.50/stream1",
        ),
    ]
    await _setup_entry(hass, cameras)

    state = hass.states.get("camera.front_door_camera")
    assert state is not None
    assert state.attributes["supported_features"] & CameraEntityFeature.STREAM


async def test_supported_features_none_for_flash(hass):
    """Test no features are set for Flash cameras."""
    cameras = [
        _mock_camera(
            700,
            "Flash Camera",
            uri="http://192.168.1.50/stream.swf",
            stream_type="swf",
            is_flash=True,
        ),
    ]
    await _setup_entry(hass, cameras)

    state = hass.states.get("camera.flash_camera")
    assert state is not None
    assert state.attributes["supported_features"] == 0


# --- Snapshot / async_camera_image ---


async def test_camera_image_success(hass):
    """Test async_camera_image returns bytes on success."""
    cameras = [
        _mock_camera(
            700,
            "Front Door Camera",
            uri_still="http://192.168.1.50/snapshot.jpg",
        ),
    ]
    await _setup_entry(hass, cameras)

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.content_type = "image/jpeg"
    mock_resp.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0fake-jpeg")

    mock_session = MagicMock()
    mock_session.get = _mock_aiohttp_get(resp=mock_resp)

    entity = _get_camera_entity(hass)
    assert entity is not None

    with patch(
        "custom_components.came_domotic.camera.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await entity.async_camera_image()

    assert result == b"\xff\xd8\xff\xe0fake-jpeg"


async def test_camera_image_timeout(hass):
    """Test async_camera_image returns None on timeout."""
    cameras = [
        _mock_camera(
            700,
            "Front Door Camera",
            uri_still="http://192.168.1.50/snapshot.jpg",
        ),
    ]
    await _setup_entry(hass, cameras)

    mock_session = MagicMock()
    mock_session.get = _mock_aiohttp_get(side_effect=TimeoutError)

    entity = _get_camera_entity(hass)
    assert entity is not None

    with patch(
        "custom_components.came_domotic.camera.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await entity.async_camera_image()

    assert result is None


async def test_camera_image_client_error(hass):
    """Test async_camera_image returns None on aiohttp.ClientError."""
    cameras = [
        _mock_camera(
            700,
            "Front Door Camera",
            uri_still="http://192.168.1.50/snapshot.jpg",
        ),
    ]
    await _setup_entry(hass, cameras)

    mock_session = MagicMock()
    mock_session.get = _mock_aiohttp_get(side_effect=aiohttp.ClientError)

    entity = _get_camera_entity(hass)
    assert entity is not None

    with patch(
        "custom_components.came_domotic.camera.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await entity.async_camera_image()

    assert result is None


async def test_camera_image_non_200(hass):
    """Test async_camera_image returns None on non-200 status."""
    cameras = [
        _mock_camera(
            700,
            "Front Door Camera",
            uri_still="http://192.168.1.50/snapshot.jpg",
        ),
    ]
    await _setup_entry(hass, cameras)

    mock_resp = AsyncMock()
    mock_resp.status = 404
    mock_resp.content_type = "text/html"

    mock_session = MagicMock()
    mock_session.get = _mock_aiohttp_get(resp=mock_resp)

    entity = _get_camera_entity(hass)
    assert entity is not None

    with patch(
        "custom_components.came_domotic.camera.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await entity.async_camera_image()

    assert result is None


async def test_camera_image_bad_content_type(hass):
    """Test async_camera_image returns None for non-image content type."""
    cameras = [
        _mock_camera(
            700,
            "Front Door Camera",
            uri_still="http://192.168.1.50/snapshot.jpg",
        ),
    ]
    await _setup_entry(hass, cameras)

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.content_type = "text/html"

    mock_session = MagicMock()
    mock_session.get = _mock_aiohttp_get(resp=mock_resp)

    entity = _get_camera_entity(hass)
    assert entity is not None

    with patch(
        "custom_components.came_domotic.camera.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await entity.async_camera_image()

    assert result is None


async def test_camera_image_no_still_uri(hass):
    """Test async_camera_image returns None when uri_still is empty."""
    cameras = [
        _mock_camera(
            700,
            "Front Door Camera",
            uri="rtsp://192.168.1.50/stream1",
            uri_still="",
        ),
    ]
    await _setup_entry(hass, cameras)

    entity = _get_camera_entity(hass)
    assert entity is not None
    result = await entity.async_camera_image()
    assert result is None


# --- Extra state attributes ---


async def test_extra_state_attributes(hass):
    """Test extra_state_attributes exposes stream_type and is_flash."""
    cameras = [
        _mock_camera(
            700,
            "Front Door Camera",
            uri="rtsp://192.168.1.50/stream1",
            uri_still="http://192.168.1.50/snapshot.jpg",
            stream_type="mjpeg",
        ),
    ]
    await _setup_entry(hass, cameras)

    state = hass.states.get("camera.front_door_camera")
    assert state is not None
    assert state.attributes["stream_type"] == "mjpeg"
    assert state.attributes["is_flash"] is False


async def test_extra_state_attributes_camera_missing(hass):
    """Test extra_state_attributes returns None when camera disappears."""
    cameras = [_mock_camera(700, "Front Door Camera")]
    config_entry = await _setup_entry(hass, cameras)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.cameras.clear()

    empty_data = CameDomoticServerData(
        server_info=_mock_server_info(),
    )
    with patch.object(
        coordinator,
        "_async_update_data",
        return_value=empty_data,
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    state = hass.states.get("camera.front_door_camera")
    assert state is not None
    assert "stream_type" not in state.attributes
    assert "is_flash" not in state.attributes


# --- Edge cases ---


async def test_camera_disappeared_from_coordinator(hass):
    """Test camera properties return safe defaults when camera disappears."""
    cameras = [_mock_camera(700, "Front Door Camera")]
    config_entry = await _setup_entry(hass, cameras)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.cameras.clear()

    empty_data = CameDomoticServerData(
        server_info=_mock_server_info(),
    )
    with patch.object(
        coordinator,
        "_async_update_data",
        return_value=empty_data,
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    # Entity should still exist but with safe defaults
    state = hass.states.get("camera.front_door_camera")
    assert state is not None


async def test_cameras_not_fetched_on_api_error(hass):
    """Test camera fetch error doesn't crash setup; no camera entities created."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            return_value=_mock_server_info(),
        ),
        patch(f"{_API_CLIENT}.async_get_thermo_zones", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_scenarios", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_openings", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_lights", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_digital_inputs", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_analog_sensors", return_value=[]),
        patch(f"{_API_CLIENT}.async_get_relays", return_value=[]),
        patch(
            f"{_API_CLIENT}.async_get_cameras",
            side_effect=CameDomoticApiClientCommunicationError("Not supported"),
        ),
        patch(
            f"{_API_CLIENT}.async_get_topology",
            return_value=_mock_topology(),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch(f"{_COORDINATOR}.start_long_poll"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "camera"
    ]
    assert len(entries) == 0
