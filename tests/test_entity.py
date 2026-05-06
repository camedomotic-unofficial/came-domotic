"""Tests for CAME Domotic base entity classes."""

from __future__ import annotations

import json
from pathlib import Path

from homeassistant.helpers import device_registry as dr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic.const import DOMAIN, MANUFACTURER

from .const import MOCK_CONFIG

_TRANSLATION_KEY = "came_server_device_friendly_name"
_INTEGRATION_DIR = Path(__file__).parent.parent / "custom_components" / "came_domotic"


async def test_gateway_device_uses_translation_key(hass, bypass_get_data):
    """Gateway device is registered via translation_key and resolves to localized name.

    Home Assistant resolves DeviceInfo's translation_key against the active
    language at registration time and stores the result in DeviceEntry.name.
    For the default test language (English) the resolved name is "CAME server".
    """
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    device_reg = dr.async_get(hass)
    device = device_reg.async_get_device(identifiers={(DOMAIN, config_entry.entry_id)})
    assert device is not None
    assert device.name == "CAME server"
    assert device.manufacturer == MANUFACTURER


def test_translation_key_consistency_across_translations() -> None:
    """strings.json and every translations/*.json define the device name key."""
    expected = {
        _INTEGRATION_DIR / "strings.json": "CAME server",
        _INTEGRATION_DIR / "translations" / "en.json": "CAME server",
        _INTEGRATION_DIR / "translations" / "it.json": "Server CAME",
    }
    for path, expected_name in expected.items():
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["device"][_TRANSLATION_KEY]["name"] == expected_name, (
            f"{path.name} is missing or has the wrong value for "
            f"device.{_TRANSLATION_KEY}.name"
        )
