"""Binary sensor platform for CAME Domotic.

Exposes CAME Domotic digital inputs as Home Assistant binary sensor entities.
Digital inputs are read-only devices that report ACTIVE/IDLE state.
Load shedding is reported via per-load "shed" problem sensors.
"""

from __future__ import annotations

import logging
from typing import Any

from aiocamedomotic.models import DigitalInputStatus, LoadsCtrlRelay
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from . import CameDomoticConfigEntry
from .const import ATTRIBUTION, DOMAIN
from .coordinator import CameDomoticDataUpdateCoordinator
from .entity import CameDomoticDeviceEntity
from .ping_coordinator import CameDomoticPingCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: CameDomoticConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up binary sensor platform."""
    coordinator = entry.runtime_data.coordinator
    ping_coordinator = entry.runtime_data.ping_coordinator
    digital_inputs = coordinator.data.digital_inputs
    loadsctrl_relays = coordinator.data.loadsctrl_relays
    _LOGGER.debug(
        "Setting up %d digital input binary sensor(s) and %d load shed sensor(s)",
        len(digital_inputs),
        len(loadsctrl_relays),
    )
    async_add_entities(
        [
            CameDomoticServerConnectivitySensor(ping_coordinator, entry.entry_id),
            *(
                CameDomoticDigitalInput(coordinator, act_id, di.name)
                for act_id, di in digital_inputs.items()
            ),
            *(
                CameDomoticLoadShedSensor(coordinator, relay)
                for relay in loadsctrl_relays.values()
            ),
        ]
    )


class CameDomoticDigitalInput(CameDomoticDeviceEntity, BinarySensorEntity):
    """Binary sensor entity for a CAME Domotic digital input.

    Read-only device that reports ACTIVE (on) or IDLE (off) state.
    """

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        act_id: int,
        input_name: str,
    ) -> None:
        """Initialize the digital input binary sensor.

        Args:
            coordinator: The data update coordinator.
            act_id: The actuator ID that identifies this digital input.
            input_name: The display name of the digital input.
        """
        super().__init__(
            coordinator,
            entity_key=f"digital_input_{act_id}",
            device_name=input_name,
            device_id=f"digital_input_{act_id}",
        )
        self._act_id = act_id
        self._attr_has_entity_name = False
        self._attr_name = input_name

    @property
    def is_on(self) -> bool | None:
        """Return True if the digital input is active.

        Maps DigitalInputStatus.ACTIVE to True, IDLE to False,
        and UNKNOWN to None.
        """
        digital_input = self.coordinator.data.digital_inputs.get(self._act_id)
        if digital_input is None:
            return None
        if digital_input.status == DigitalInputStatus.UNKNOWN:
            return None
        return digital_input.status == DigitalInputStatus.ACTIVE

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return additional digital input attributes."""
        digital_input = self.coordinator.data.digital_inputs.get(self._act_id)
        if digital_input is None:
            return None
        last_triggered = None
        if digital_input.utc_time:
            last_triggered = (
                dt_util.utc_from_timestamp(digital_input.utc_time)
                .astimezone(dt_util.DEFAULT_TIME_ZONE)
                .isoformat()
            )
        return {
            "addr": digital_input.addr,
            "last_triggered": last_triggered,
        }


class CameDomoticLoadShedSensor(CameDomoticDeviceEntity, BinarySensorEntity):
    """Problem sensor reporting whether a load is currently shed.

    ON means the load shedding controller has detached (shed) this load
    because consumption exceeded the overload threshold. The sensor lives
    on a per-load HA device named after the load (loads have no floor/room
    placement of their own), so the friendly name reads
    "<load name> <translated suffix>".
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_translation_key = "load_detached"

    def __init__(
        self,
        coordinator: CameDomoticDataUpdateCoordinator,
        relay: LoadsCtrlRelay,
    ) -> None:
        """Initialize the load shed sensor."""
        super().__init__(
            coordinator,
            entity_key=f"loadsctrl_relay_{relay.id}_detached",
            device_name=relay.name,
            device_id=f"loadsctrl_relay_{relay.id}",
        )
        self._relay_id = relay.id

    @property
    def is_on(self) -> bool | None:
        """Return True if the load is currently shed by the controller."""
        relay = self.coordinator.data.loadsctrl_relays.get(self._relay_id)
        if relay is None:
            return None
        return relay.detached

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return read-only load configuration attributes."""
        relay = self.coordinator.data.loadsctrl_relays.get(self._relay_id)
        if relay is None:
            return None
        return {
            "priority": relay.priority,
            "status": relay.status.name.lower(),
        }


class CameDomoticServerConnectivitySensor(
    CoordinatorEntity[CameDomoticPingCoordinator], BinarySensorEntity
):
    """Diagnostic binary sensor reporting whether the CAME server is reachable.

    Shows ON when the server responds to ping, OFF when unreachable.
    Uses EntityCategory.DIAGNOSTIC so it is grouped separately in the UI.
    """

    _attr_has_entity_name = True
    _attr_attribution = ATTRIBUTION
    _attr_translation_key = "server_connectivity"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(
        self,
        coordinator: CameDomoticPingCoordinator,
        entry_id: str,
    ) -> None:
        """Initialize the server connectivity binary sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry_id}_server_connectivity"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry_id)})

    @property
    def is_on(self) -> bool:
        """Return True if the server responded to the last ping."""
        return self.coordinator.data.connected
