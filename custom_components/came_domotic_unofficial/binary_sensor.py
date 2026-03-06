"""Binary sensor platform for CAME Domotic Unofficial."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CameDomoticUnofficialConfigEntry
from .entity import CameDomoticUnofficialEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticUnofficialConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary_sensor platform."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [CameDomoticUnofficialBinarySensor(coordinator, "binary_sensor")]
    )


class CameDomoticUnofficialBinarySensor(
    CameDomoticUnofficialEntity, BinarySensorEntity
):
    """CAME Domotic Unofficial binary_sensor class."""

    _attr_translation_key = "binary_sensor"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    @property
    def is_on(self) -> bool:
        """Return true if the binary_sensor is on."""
        return self.coordinator.data.get("keycode") is not None
