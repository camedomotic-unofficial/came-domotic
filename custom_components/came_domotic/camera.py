"""Camera platform for CAME Domotic.

Exposes CAME Domotic TVCC cameras as Home Assistant camera entities.
Cameras are read-only — they provide streaming video and/or JPEG
snapshots but cannot be remotely controlled.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp
from homeassistant.components.camera import Camera as CameraEntity, CameraEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CameDomoticConfigEntry
from .const import MANUFACTURER
from .coordinator import CameDomoticDataUpdateCoordinator
from .entity import CameDomoticDeviceEntity

_LOGGER = logging.getLogger(__name__)

_SNAPSHOT_TIMEOUT = 10  # seconds


def _is_rtsp_uri(uri: str) -> bool:
    """Return True if the URI uses the RTSP protocol."""
    return uri.lower().startswith("rtsp://")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up camera platform."""
    coordinator = entry.runtime_data.coordinator
    cameras = coordinator.data.cameras
    _LOGGER.debug("Setting up %d CCTV camera(s)", len(cameras))
    async_add_entities(
        CameDomoticCamera(coordinator, camera_id, camera.name)
        for camera_id, camera in cameras.items()
    )


class CameDomoticCamera(CameDomoticDeviceEntity, CameraEntity):
    """Camera entity for a CAME Domotic TVCC camera.

    Read-only entity providing streaming video (RTSP) and/or JPEG
    snapshots from IP cameras connected to the CAME Domotic system.
    """

    _attr_brand = MANUFACTURER

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        camera_id: int,
        camera_name: str,
    ) -> None:
        """Initialize the camera entity.

        Args:
            coordinator: The data update coordinator.
            camera_id: The unique camera identifier.
            camera_name: The display name of the camera.
        """
        CameDomoticDeviceEntity.__init__(
            self,
            coordinator,
            entity_key=f"camera_{camera_id}",
            device_name=camera_name,
            device_id=f"camera_{camera_id}",
        )
        CameraEntity.__init__(self)
        self._camera_id = camera_id
        self._attr_has_entity_name = False
        self._attr_name = camera_name

    def _get_stream_source(self) -> str | None:
        """Return the RTSP stream URL if available.

        Only RTSP URIs are recognized as streamable. HTTP-based streams
        and Flash (SWF) cameras are not supported for live streaming.

        Note: the returned URI may contain embedded credentials. HA's
        stream component handles this internally and does not expose the
        raw URL to the frontend.
        """
        camera = self.coordinator.data.cameras.get(self._camera_id)
        if camera is None or camera.is_flash or not camera.uri:
            return None
        if _is_rtsp_uri(camera.uri):
            return camera.uri
        return None

    @property
    def is_streaming(self) -> bool:
        """Return True if the camera has a valid stream source."""
        return self._get_stream_source() is not None

    @property
    def supported_features(self) -> CameraEntityFeature:
        """Return supported features based on stream availability."""
        if self._get_stream_source() is not None:
            return CameraEntityFeature.STREAM
        return CameraEntityFeature(0)

    async def stream_source(self) -> str | None:
        """Return the RTSP stream URL for HA's stream component."""
        return self._get_stream_source()

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Fetch a JPEG snapshot from the camera's still-image URI.

        Appends a timestamp query parameter for cache busting as
        recommended by the aiocamedomotic library.
        """
        camera = self.coordinator.data.cameras.get(self._camera_id)
        if camera is None or not camera.uri_still:
            return None

        separator = "&" if "?" in camera.uri_still else "?"
        url = f"{camera.uri_still}{separator}t={int(time.time())}"
        try:
            session = async_get_clientsession(self.hass)
            async with (
                asyncio.timeout(_SNAPSHOT_TIMEOUT),
                session.get(url) as resp,
            ):
                if resp.status != 200:
                    _LOGGER.warning(
                        "Snapshot fetch returned status %d for camera %d",
                        resp.status,
                        self._camera_id,
                    )
                    return None

                content_type = resp.content_type or ""
                if not content_type.startswith("image/"):
                    _LOGGER.warning(
                        "Unexpected content type '%s' for camera %d snapshot",
                        content_type,
                        self._camera_id,
                    )
                    return None

                return await resp.read()
        except TimeoutError:
            _LOGGER.warning("Timeout fetching snapshot for camera %d", self._camera_id)
            return None
        except aiohttp.ClientError:
            _LOGGER.warning("Failed to fetch snapshot for camera %d", self._camera_id)
            return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return safe metadata attributes (never exposes URIs)."""
        camera = self.coordinator.data.cameras.get(self._camera_id)
        if camera is None:
            return None
        return {
            "stream_type": camera.stream_type,
            "is_flash": camera.is_flash,
        }
