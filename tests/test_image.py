"""Test CAME Domotic image platform (map pages / floor plans)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic.const import DOMAIN
from custom_components.came_domotic.image import _detect_content_type
from custom_components.came_domotic.models import CameDomoticServerData

from .conftest import _mock_map_page, _mock_server_info, _mock_topology
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


def _get_image_entity(hass, entity_id):
    """Return the image entity object for the given entity_id."""
    for state in hass.states.async_all("image"):
        if state.entity_id == entity_id:
            return hass.data["image"].get_entity(state.entity_id)
    return None


async def _setup_entry(hass, mock_maps):
    """Set up a config entry with the given mock map pages list."""
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
        patch(f"{_API_CLIENT}.async_get_cameras", return_value=[]),
        patch(
            f"{_API_CLIENT}.async_get_map_pages",
            return_value=mock_maps,
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


async def test_image_entities_created(hass, bypass_get_data):
    """Test that one image entity is created per map page."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "image"
    ]
    assert len(entries) == 2


async def test_image_unique_id(hass, bypass_get_data):
    """Test image unique IDs follow the expected pattern."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    unique_ids = {
        e.unique_id
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "image"
    }
    assert unique_ids == {
        "test_map_0",
        "test_map_1",
    }


async def test_no_maps(hass):
    """Test no image entities created when there are no maps."""
    config_entry = await _setup_entry(hass, [])

    registry = er.async_get(hass)
    entries = [
        e
        for e in registry.entities.values()
        if e.config_entry_id == config_entry.entry_id and e.domain == "image"
    ]
    assert len(entries) == 0


async def test_image_entity_name(hass):
    """Test image entity name comes from page_label."""
    maps = [_mock_map_page(0, "Ground Floor")]
    await _setup_entry(hass, maps)

    state = hass.states.get("image.came_eti_domo_server_192_168_1_100_ground_floor")
    assert state is not None


# --- Image fetching ---


async def test_async_image_success(hass):
    """Test async_image returns bytes on success."""
    maps = [
        _mock_map_page(0, "Ground Floor", background="images/ground floor.jpg"),
    ]
    await _setup_entry(hass, maps)

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.content_type = "image/jpeg"
    mock_resp.read = AsyncMock(return_value=b"\xff\xd8\xff\xe0fake-jpeg")

    mock_session = MagicMock()
    mock_session.get = _mock_aiohttp_get(resp=mock_resp)

    entity = _get_image_entity(
        hass, "image.came_eti_domo_server_192_168_1_100_ground_floor"
    )
    assert entity is not None

    with patch(
        "custom_components.came_domotic.image.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await entity.async_image()

    assert result == b"\xff\xd8\xff\xe0fake-jpeg"


async def test_async_image_url_construction(hass):
    """Test that the image URL is properly constructed with percent-encoded spaces."""
    maps = [
        _mock_map_page(0, "Ground Floor", background="images/ground floor.jpg"),
    ]
    await _setup_entry(hass, maps)

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.content_type = "image/jpeg"
    mock_resp.read = AsyncMock(return_value=b"image-data")

    mock_session = MagicMock()
    mock_session.get = _mock_aiohttp_get(resp=mock_resp)

    entity = _get_image_entity(
        hass, "image.came_eti_domo_server_192_168_1_100_ground_floor"
    )
    assert entity is not None

    with patch(
        "custom_components.came_domotic.image.async_get_clientsession",
        return_value=mock_session,
    ):
        await entity.async_image()

    # Verify the URL was constructed with percent-encoded spaces
    call_args = mock_session.get.call_args
    url = call_args[0][0]
    assert url == "http://192.168.1.100/images/ground%20floor.jpg"


async def test_async_image_no_background(hass):
    """Test async_image returns None when background is empty."""
    maps = [_mock_map_page(0, "Empty Map", background="")]
    await _setup_entry(hass, maps)

    entity = _get_image_entity(
        hass, "image.came_eti_domo_server_192_168_1_100_empty_map"
    )
    assert entity is not None
    result = await entity.async_image()
    assert result is None


async def test_async_image_timeout(hass):
    """Test async_image returns None on timeout."""
    maps = [_mock_map_page(0, "Ground Floor")]
    await _setup_entry(hass, maps)

    mock_session = MagicMock()
    mock_session.get = _mock_aiohttp_get(side_effect=TimeoutError)

    entity = _get_image_entity(
        hass, "image.came_eti_domo_server_192_168_1_100_ground_floor"
    )
    assert entity is not None

    with patch(
        "custom_components.came_domotic.image.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await entity.async_image()

    assert result is None


async def test_async_image_client_error(hass):
    """Test async_image returns None on aiohttp.ClientError."""
    maps = [_mock_map_page(0, "Ground Floor")]
    await _setup_entry(hass, maps)

    mock_session = MagicMock()
    mock_session.get = _mock_aiohttp_get(side_effect=aiohttp.ClientError)

    entity = _get_image_entity(
        hass, "image.came_eti_domo_server_192_168_1_100_ground_floor"
    )
    assert entity is not None

    with patch(
        "custom_components.came_domotic.image.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await entity.async_image()

    assert result is None


async def test_async_image_non_200(hass):
    """Test async_image returns None on non-200 status."""
    maps = [_mock_map_page(0, "Ground Floor")]
    await _setup_entry(hass, maps)

    mock_resp = AsyncMock()
    mock_resp.status = 404
    mock_resp.content_type = "text/html"

    mock_session = MagicMock()
    mock_session.get = _mock_aiohttp_get(resp=mock_resp)

    entity = _get_image_entity(
        hass, "image.came_eti_domo_server_192_168_1_100_ground_floor"
    )
    assert entity is not None

    with patch(
        "custom_components.came_domotic.image.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await entity.async_image()

    assert result is None


async def test_async_image_bad_content_type(hass):
    """Test async_image returns None for non-image content type."""
    maps = [_mock_map_page(0, "Ground Floor")]
    await _setup_entry(hass, maps)

    mock_resp = AsyncMock()
    mock_resp.status = 200
    mock_resp.content_type = "text/html"

    mock_session = MagicMock()
    mock_session.get = _mock_aiohttp_get(resp=mock_resp)

    entity = _get_image_entity(
        hass, "image.came_eti_domo_server_192_168_1_100_ground_floor"
    )
    assert entity is not None

    with patch(
        "custom_components.came_domotic.image.async_get_clientsession",
        return_value=mock_session,
    ):
        result = await entity.async_image()

    assert result is None


# --- Content type detection ---


def test_detect_content_type_jpeg_default():
    """Test default content type is image/jpeg."""
    assert _detect_content_type("images/floor.jpg") == "image/jpeg"
    assert _detect_content_type("images/floor.jpeg") == "image/jpeg"


def test_detect_content_type_png():
    """Test PNG extension detected correctly."""
    assert _detect_content_type("images/floor.png") == "image/png"


def test_detect_content_type_gif():
    """Test GIF extension detected correctly."""
    assert _detect_content_type("images/floor.gif") == "image/gif"


def test_detect_content_type_bmp():
    """Test BMP extension detected correctly."""
    assert _detect_content_type("images/floor.bmp") == "image/bmp"


def test_detect_content_type_svg():
    """Test SVG extension detected correctly."""
    assert _detect_content_type("images/floor.svg") == "image/svg+xml"


def test_detect_content_type_webp():
    """Test WebP extension detected correctly."""
    assert _detect_content_type("images/floor.webp") == "image/webp"


def test_detect_content_type_no_background():
    """Test default when background is empty."""
    assert _detect_content_type("") == "image/jpeg"


def test_detect_content_type_unknown_extension():
    """Test default for unrecognized extensions."""
    assert _detect_content_type("images/floor.tiff") == "image/jpeg"


# --- Extra state attributes ---


async def test_extra_state_attributes(hass):
    """Test extra_state_attributes exposes map metadata."""
    elements = [{"type": "light", "act_id": 300, "x": 100, "y": 200}]
    maps = [_mock_map_page(0, "Ground Floor", page_scale=1024, elements=elements)]
    await _setup_entry(hass, maps)

    state = hass.states.get("image.came_eti_domo_server_192_168_1_100_ground_floor")
    assert state is not None
    assert state.attributes["page_id"] == 0
    assert state.attributes["page_scale"] == 1024
    assert state.attributes["elements_count"] == 1


async def test_extra_state_attributes_map_missing(hass):
    """Test extra_state_attributes returns None when map disappears."""
    maps = [_mock_map_page(0, "Ground Floor")]
    config_entry = await _setup_entry(hass, maps)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.maps.clear()

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

    state = hass.states.get("image.came_eti_domo_server_192_168_1_100_ground_floor")
    assert state is not None
    assert "page_id" not in state.attributes
    assert "page_scale" not in state.attributes
    assert "elements_count" not in state.attributes


# --- Edge cases ---


async def test_map_disappeared_from_coordinator(hass):
    """Test map image returns None when map disappears from coordinator."""
    maps = [_mock_map_page(0, "Ground Floor")]
    config_entry = await _setup_entry(hass, maps)

    coordinator = config_entry.runtime_data.coordinator
    coordinator.data.maps.clear()

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

    entity = _get_image_entity(
        hass, "image.came_eti_domo_server_192_168_1_100_ground_floor"
    )
    assert entity is not None
    result = await entity.async_image()
    assert result is None
