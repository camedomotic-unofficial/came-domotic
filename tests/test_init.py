"""Test CAME Domotic setup process."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.helpers import area_registry as ar, floor_registry as fr
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic import (
    _setup_topology,
    async_remove_config_entry_device,
)
from custom_components.came_domotic.api import (
    CameDomoticApiClient,
    CameDomoticApiClientCommunicationError,
)
from custom_components.came_domotic.const import (
    CONF_TOPOLOGY_IMPORTED,
    DOMAIN,
    PING_UPDATE_INTERVAL_DISCONNECTED,
)
from custom_components.came_domotic.coordinator import (
    CameDomoticDataUpdateCoordinator,
    CameDomoticPingCoordinator,
)
from custom_components.came_domotic.models import CameDomoticServerData

from .conftest import _mock_topology, _mock_topology_floor, _mock_topology_room
from .const import MOCK_CONFIG

_API_CLIENT = "custom_components.came_domotic.api.CameDomoticApiClient"
_COORDINATOR = (
    "custom_components.came_domotic.coordinator.CameDomoticDataUpdateCoordinator"
)


async def test_setup_and_unload_entry(hass, bypass_get_data):
    """Test entry setup and unload."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    assert config_entry.runtime_data is not None
    assert isinstance(
        config_entry.runtime_data.coordinator,
        CameDomoticDataUpdateCoordinator,
    )
    assert isinstance(
        config_entry.runtime_data.client,
        CameDomoticApiClient,
    )
    assert isinstance(
        config_entry.runtime_data.ping_coordinator,
        CameDomoticPingCoordinator,
    )

    # Unload the entry
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_setup_entry_communication_error(hass, error_on_get_data):
    """Test offline mode when API raises a communication error during first refresh."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Entry loaded in offline mode despite data fetch failure
    assert config_entry.state is ConfigEntryState.LOADED

    coordinator = config_entry.runtime_data.coordinator
    ping_coordinator = config_entry.runtime_data.ping_coordinator

    # Coordinator should be in offline state
    assert coordinator._started_offline is True  # noqa: SLF001
    assert coordinator.server_available is False

    # Ping should show disconnected with fast retry cadence
    assert ping_coordinator.data.connected is False
    assert ping_coordinator.update_interval == PING_UPDATE_INTERVAL_DISCONNECTED

    # Clean up
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_entry_auth_error(hass, auth_error_on_get_data):
    """Test ConfigEntryAuthFailed when API raises auth error during setup."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


async def test_remove_config_entry_device(hass, bypass_get_data):
    """Test removing a device entry always returns True."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await async_remove_config_entry_device(hass, config_entry, None)  # type: ignore[arg-type]
    assert result is True


async def test_unload_entry_failure(hass, bypass_get_data):
    """Test unload when platform unload fails skips API disposal."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        return_value=False,
    ):
        result = await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert result is False


async def test_unload_stops_long_poll(hass, bypass_get_data):
    """Test that unloading the entry stops the long-poll task."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = config_entry.runtime_data.coordinator

    with patch.object(coordinator, "stop_long_poll") as mock_stop:
        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    mock_stop.assert_awaited_once()


async def test_setup_entry_server_offline(hass):
    """Test entry sets up in offline mode when server is unreachable at startup."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    with (
        patch(
            f"{_API_CLIENT}.async_connect",
            side_effect=CameDomoticApiClientCommunicationError("Timeout"),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch(f"{_API_CLIENT}.async_ping", return_value=10.0),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # Entry loaded successfully despite server being offline
    assert config_entry.state is ConfigEntryState.LOADED

    coordinator = config_entry.runtime_data.coordinator
    ping_coordinator = config_entry.runtime_data.ping_coordinator

    # Coordinator should be in offline state
    assert coordinator._started_offline is True  # noqa: SLF001
    assert coordinator.server_available is False

    # Ping should show disconnected with fast retry cadence
    assert ping_coordinator.data.connected is False
    assert ping_coordinator.data.latency_ms is None
    assert ping_coordinator.update_interval == PING_UPDATE_INTERVAL_DISCONNECTED

    # Data should be empty defaults
    assert coordinator.data.server_info is None
    assert coordinator.data.thermo_zones == {}

    # Clean up
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


# --- _setup_topology tests ---


async def test_setup_topology_creates_floors_and_areas(hass):
    """Test that _setup_topology creates HA floors and assigns areas."""
    data = CameDomoticServerData(topology=_mock_topology())

    _setup_topology(hass, data)

    floor_registry = fr.async_get(hass)
    area_registry = ar.async_get(hass)

    # Floors created
    ground = floor_registry.async_get_floor_by_name("Ground Floor")
    first = floor_registry.async_get_floor_by_name("First Floor")
    assert ground is not None
    assert first is not None
    assert ground.level == 0
    assert first.level == 1

    # Areas created and assigned to correct floors
    living = area_registry.async_get_area_by_name("Living Room")
    bedroom = area_registry.async_get_area_by_name("Bedroom")
    assert living is not None
    assert bedroom is not None
    assert living.floor_id == ground.floor_id
    assert bedroom.floor_id == first.floor_id


async def test_setup_topology_idempotent(hass):
    """Test that running _setup_topology twice doesn't create duplicates."""
    data = CameDomoticServerData(topology=_mock_topology())

    _setup_topology(hass, data)
    _setup_topology(hass, data)

    floor_registry = fr.async_get(hass)
    area_registry = ar.async_get(hass)

    # Only one of each floor/area
    all_floors = floor_registry.floors
    floor_names = [f.name for f in all_floors.values()]
    assert floor_names.count("Ground Floor") == 1
    assert floor_names.count("First Floor") == 1

    all_areas = area_registry.areas
    area_names = [a.name for a in all_areas.values()]
    assert area_names.count("Living Room") == 1
    assert area_names.count("Bedroom") == 1


async def test_setup_topology_respects_user_floor_assignment(hass):
    """Test that user-assigned floors are not overwritten."""
    floor_registry = fr.async_get(hass)
    area_registry = ar.async_get(hass)

    # Pre-create a floor and area with a user-chosen assignment
    user_floor = floor_registry.async_create("User Custom Floor", level=99)
    living = area_registry.async_get_or_create("Living Room")
    area_registry.async_update(living.id, floor_id=user_floor.floor_id)

    data = CameDomoticServerData(topology=_mock_topology())
    _setup_topology(hass, data)

    # Living Room should still be on the user's custom floor
    living_after = area_registry.async_get_area_by_name("Living Room")
    assert living_after is not None
    assert living_after.floor_id == user_floor.floor_id


async def test_setup_topology_reuses_existing_floor(hass):
    """Test that pre-existing HA floors with matching names are reused."""
    floor_registry = fr.async_get(hass)

    # Pre-create a floor with the same name
    existing = floor_registry.async_create("Ground Floor", level=10)

    data = CameDomoticServerData(topology=_mock_topology())
    _setup_topology(hass, data)

    # Should reuse the existing floor, not create a duplicate
    all_floors = floor_registry.floors
    ground_floors = [f for f in all_floors.values() if f.name == "Ground Floor"]
    assert len(ground_floors) == 1
    assert ground_floors[0].floor_id == existing.floor_id

    # Area should be assigned to the existing floor
    area_registry = ar.async_get(hass)
    living = area_registry.async_get_area_by_name("Living Room")
    assert living is not None
    assert living.floor_id == existing.floor_id


async def test_setup_topology_none_is_noop(hass):
    """Test that _setup_topology does nothing when topology is None."""
    data = CameDomoticServerData(topology=None)

    _setup_topology(hass, data)

    floor_registry = fr.async_get(hass)
    area_registry = ar.async_get(hass)

    assert len(floor_registry.floors) == 0
    assert len(area_registry.areas) == 0


async def test_setup_topology_empty_floors(hass):
    """Test that _setup_topology handles empty floor list."""
    topology = MagicMock()
    topology.floors = []
    data = CameDomoticServerData(topology=topology)

    _setup_topology(hass, data)

    floor_registry = fr.async_get(hass)
    area_registry = ar.async_get(hass)

    assert len(floor_registry.floors) == 0
    assert len(area_registry.areas) == 0


async def test_setup_topology_called_during_entry_setup(hass, bypass_get_data):
    """Test that _setup_topology is called during normal entry setup."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify floors and areas were created from mock topology
    floor_registry = fr.async_get(hass)
    area_registry = ar.async_get(hass)

    assert floor_registry.async_get_floor_by_name("Ground Floor") is not None
    assert floor_registry.async_get_floor_by_name("First Floor") is not None
    assert area_registry.async_get_area_by_name("Living Room") is not None
    assert area_registry.async_get_area_by_name("Bedroom") is not None

    # Flag should be set after first setup
    assert config_entry.data.get(CONF_TOPOLOGY_IMPORTED) is True

    # Clean up
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_topology_skipped_on_restart(hass, bypass_get_data):
    """Test that _setup_topology is not called when topology was already imported."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_TOPOLOGY_IMPORTED: True},
        entry_id="test",
    )
    config_entry.add_to_hass(hass)

    with patch("custom_components.came_domotic._setup_topology") as mock_setup_topology:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    mock_setup_topology.assert_not_called()

    # No floors should be created (topology was skipped).
    # Areas may still be created by suggested_area in DeviceInfo.
    floor_registry = fr.async_get(hass)
    assert len(floor_registry.floors) == 0

    # Clean up
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()


async def test_setup_topology_case_insensitive_floor_match(hass):
    """Test that CAME floors match existing HA floors case-insensitively."""
    floor_registry = fr.async_get(hass)
    area_registry = ar.async_get(hass)

    # Pre-create with title casing
    existing_floor = floor_registry.async_create("Ground Floor", level=10)
    area_registry.async_get_or_create("Living Room")

    # Topology returns UPPERCASE names (as CAME servers often do)
    topology = MagicMock()
    topology.floors = [
        _mock_topology_floor(
            0,
            "GROUND FLOOR",
            rooms=[_mock_topology_room(0, "LIVING ROOM")],
        ),
    ]
    data = CameDomoticServerData(topology=topology)
    _setup_topology(hass, data)

    # Should reuse existing floor, not create a duplicate
    all_floors = floor_registry.floors
    assert len(all_floors) == 1
    assert list(all_floors.values())[0].floor_id == existing_floor.floor_id

    # Should reuse existing area, not create a duplicate
    all_areas = area_registry.areas
    assert len(all_areas) == 1


async def test_setup_topology_not_called_when_offline(hass):
    """Test that _setup_topology is not called when server is offline."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    with (
        patch(
            f"{_API_CLIENT}.async_connect",
            side_effect=CameDomoticApiClientCommunicationError("Timeout"),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
        patch(f"{_API_CLIENT}.async_ping", return_value=10.0),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    # No floors or areas should be created in offline mode
    floor_registry = fr.async_get(hass)
    area_registry = ar.async_get(hass)

    assert len(floor_registry.floors) == 0
    assert len(area_registry.areas) == 0

    # Flag should NOT be set so topology imports on recovery
    assert config_entry.data.get(CONF_TOPOLOGY_IMPORTED) is not True

    # Clean up
    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
