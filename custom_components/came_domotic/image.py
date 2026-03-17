"""Image platform for CAME Domotic.

Exposes CAME Domotic map pages (floor plans) as Home Assistant image
entities. Each map page has a background image hosted on the CAME
server. Maps are read-only structural metadata that refresh only on
full plant updates.
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import quote

import aiohttp
from homeassistant.components.image import ImageEntity
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import CameDomoticConfigEntry
from .coordinator import CameDomoticDataUpdateCoordinator
from .entity import CameDomoticEntity

_LOGGER = logging.getLogger(__name__)

_IMAGE_FETCH_TIMEOUT = 10  # seconds

# Map file extensions to MIME types for background images.
_CONTENT_TYPE_MAP: dict[str, str] = {
    ".png": "image/png",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    ".webp": "image/webp",
}
_DEFAULT_CONTENT_TYPE = "image/jpeg"


def _detect_content_type(background: str) -> str:
    """Detect the image MIME type from the background URL file extension.

    Falls back to ``image/jpeg`` for unrecognized or missing extensions.
    """
    if not background:
        return _DEFAULT_CONTENT_TYPE
    suffix = PurePosixPath(background).suffix.lower()
    return _CONTENT_TYPE_MAP.get(suffix, _DEFAULT_CONTENT_TYPE)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up image platform for map pages."""
    coordinator = entry.runtime_data.coordinator
    maps = coordinator.data.maps
    _LOGGER.debug("Setting up %d map image(s)", len(maps))
    async_add_entities(
        CameDomoticMapImage(coordinator, page_id, page.page_label)
        for page_id, page in maps.items()
    )


class CameDomoticMapImage(CameDomoticEntity, ImageEntity):
    """Image entity for a CAME Domotic map page (floor plan).

    Displays the floor plan background image from the CAME server.
    Map metadata (page scale, element count) is exposed as extra
    state attributes.
    """

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        page_id: int,
        page_label: str,
    ) -> None:
        """Initialize the map image entity.

        Args:
            coordinator: The data update coordinator.
            page_id: The unique map page identifier.
            page_label: The display name of the map page.
        """
        CameDomoticEntity.__init__(self, coordinator, entity_key=f"map_{page_id}")
        ImageEntity.__init__(self, coordinator.hass)
        self._attr_has_entity_name = False
        self._page_id = page_id
        self._attr_name = page_label

        # Detect content type from background file extension.
        page = coordinator.data.maps.get(page_id)
        bg = page.background if page else ""
        self._attr_content_type = _detect_content_type(bg)
        self._attr_image_last_updated = dt_util.utcnow()

    async def async_image(self) -> bytes | None:
        """Fetch the floor plan background image from the CAME server.

        Constructs the full URL from the server host and the relative
        background path (percent-encoding spaces and special characters).

        Returns None if the map has no background, the server is
        unreachable, or the response is not a valid image.
        """
        page = self.coordinator.data.maps.get(self._page_id)
        if page is None or not page.background:
            return None

        host = self.coordinator.config_entry.data[CONF_HOST]
        encoded_bg = quote(page.background.lstrip("/"), safe="/")
        url = f"http://{host}/{encoded_bg}"

        try:
            session = async_get_clientsession(self.hass, verify_ssl=False)
            async with (
                asyncio.timeout(_IMAGE_FETCH_TIMEOUT),
                session.get(url) as resp,
            ):
                if resp.status != 200:
                    _LOGGER.warning(
                        "Map image fetch returned status %d for page %d",
                        resp.status,
                        self._page_id,
                    )
                    return None

                content_type = resp.content_type or ""
                if not content_type.startswith("image/"):
                    _LOGGER.warning(
                        "Unexpected content type '%s' for map page %d",
                        content_type,
                        self._page_id,
                    )
                    return None

                return await resp.read()
        except TimeoutError:
            _LOGGER.warning("Timeout fetching map image for page %d", self._page_id)
            return None
        except aiohttp.ClientError:
            _LOGGER.warning("Failed to fetch map image for page %d", self._page_id)
            return None

    @callback
    def _handle_coordinator_update(self) -> None:
        """Invalidate image cache when coordinator data is refreshed."""
        self._attr_image_last_updated = dt_util.utcnow()
        super()._handle_coordinator_update()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return map metadata as extra state attributes."""
        page = self.coordinator.data.maps.get(self._page_id)
        if page is None:
            return None
        return {
            "page_id": page.page_id,
            "page_scale": page.page_scale,
            "elements_count": len(page.elements),
        }
