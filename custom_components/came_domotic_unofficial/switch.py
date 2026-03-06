"""Switch platform for CAME Domotic Unofficial."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import CameDomoticUnofficialConfigEntry
from .const import ICON
from .entity import CameDomoticUnofficialEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticUnofficialConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up switch platform."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([CameDomoticUnofficialSwitch(coordinator, "switch")])


class CameDomoticUnofficialSwitch(CameDomoticUnofficialEntity, SwitchEntity):
    """CAME Domotic Unofficial switch class."""

    _attr_translation_key = "switch"
    _attr_icon = ICON

    async def async_turn_on(self, **kwargs) -> None:
        """Turn on the switch."""
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn off the switch."""
        await self.coordinator.async_request_refresh()

    @property
    def is_on(self) -> bool:
        """Return true if the switch is on."""
        return self.coordinator.data.get("keycode") is not None
