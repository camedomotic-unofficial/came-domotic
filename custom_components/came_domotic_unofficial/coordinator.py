"""Push-based DataUpdateCoordinator for CAME Domotic Unofficial.

Uses a background long-polling task to receive incremental device state
updates from the CAME server. The coordinator performs a full data fetch
on initial setup (one API call per device type), then switches to
long-polling for real-time updates via async_get_updates().
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

from aiocamedomotic.models import DeviceType, ThermoZone
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import (
    CameDomoticUnofficialApiClient,
    CameDomoticUnofficialApiClientAuthenticationError,
    CameDomoticUnofficialApiClientError,
)
from .const import (
    DEFAULT_LONG_POLL_TIMEOUT,
    DOMAIN,
    RECONNECT_DELAY,
    UPDATE_THROTTLE_DELAY,
)

_LOGGER: logging.Logger = logging.getLogger(__name__)


class CameDomoticUnofficialDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator that manages push-based data updates via long polling.

    On first refresh, performs a full data fetch from the CAME server.
    After that, a background task long-polls for incremental updates
    and pushes them to entities via async_set_updated_data().
    """

    data: dict[str, Any]

    def __init__(
        self,
        hass: HomeAssistant,
        client: CameDomoticUnofficialApiClient,
        config_entry: ConfigEntry,
    ) -> None:
        """Initialize the push-based coordinator.

        Args:
            hass: The Home Assistant instance.
            client: The API client for communicating with the CAME server.
            config_entry: The config entry associated with this coordinator.
        """
        self.api = client
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN} ({config_entry.unique_id})",
            config_entry=config_entry,
            # No update_interval: this is a push-based coordinator.
        )
        self._long_poll_task: asyncio.Task[None] | None = None
        _LOGGER.debug("Coordinator initialized (push-based, no polling interval)")

    async def _async_update_data(self) -> dict[str, Any]:
        """Perform a full data fetch from the CAME server.

        Called during initial setup (async_config_entry_first_refresh) and
        when a plant configuration change is detected.
        """
        try:
            raw_data = await self.api.async_get_data()
        except CameDomoticUnofficialApiClientAuthenticationError as exception:
            _LOGGER.warning("Authentication failed during data update")
            raise ConfigEntryAuthFailed(exception) from exception
        except CameDomoticUnofficialApiClientError as exception:
            _LOGGER.warning("Error updating data: %s", exception)
            raise UpdateFailed(exception) from exception

        _LOGGER.debug(
            "Full data fetch complete: %d thermo zone(s)",
            len(raw_data.get("thermo_zones", [])),
        )
        return raw_data

    def start_long_poll(self) -> None:
        """Start the background long-polling task.

        Creates an asyncio task that continuously long-polls the CAME server
        for device state changes. Must be called after the initial data fetch.
        """
        if self._long_poll_task is not None:
            _LOGGER.warning("Long-poll task already running, not starting another")
            return
        self._long_poll_task = self.hass.async_create_background_task(
            self._async_long_poll_loop(),
            name=f"{DOMAIN}_long_poll_{self.config_entry.entry_id if self.config_entry else 'unknown'}",
        )
        _LOGGER.info("Long-poll background task started")

    async def stop_long_poll(self) -> None:
        """Stop the background long-polling task.

        Cancels the task and waits for it to finish. Safe to call even
        if the task is not running.
        """
        if self._long_poll_task is not None:
            self._long_poll_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._long_poll_task
            self._long_poll_task = None
            _LOGGER.debug("Long-poll background task stopped")

    async def _async_long_poll_loop(self) -> None:
        """Run the long-polling loop in a background task.

        Continuously calls async_get_updates() to receive device state
        changes from the CAME server. On each successful response, merges
        the updates into the coordinator's data and notifies entities.

        The loop handles errors as follows:
        - Auth errors: triggers reauth flow and exits the loop.
        - Communication/server errors (including timeout): logs and retries
          after RECONNECT_DELAY.
        - Cancellation: re-raises for clean shutdown.

        After processing each batch of updates, waits UPDATE_THROTTLE_DELAY
        seconds before the next long-poll call.
        """
        _LOGGER.debug("Long-poll loop started")
        while True:
            try:
                update_list = await self.api.async_get_updates(
                    timeout=DEFAULT_LONG_POLL_TIMEOUT
                )
            except CameDomoticUnofficialApiClientAuthenticationError:
                _LOGGER.warning(
                    "Authentication failed in long-poll loop, triggering reauth"
                )
                if self.config_entry:
                    self.config_entry.async_start_reauth(self.hass)
                return
            except CameDomoticUnofficialApiClientError as err:
                _LOGGER.debug(
                    "Error in long-poll loop: %s. Retrying in %ds",
                    err,
                    RECONNECT_DELAY,
                )
                await asyncio.sleep(RECONNECT_DELAY)
                continue
            except asyncio.CancelledError:
                _LOGGER.debug("Long-poll loop cancelled")
                raise

            # Handle plant configuration changes (requires full refresh)
            if update_list.has_plant_update:
                _LOGGER.info(
                    "Plant configuration changed, performing full data refresh"
                )
                try:
                    new_data = await self._async_update_data()
                    self.async_set_updated_data(new_data)
                except ConfigEntryAuthFailed:
                    # Reauth already triggered inside _async_update_data
                    return
                except UpdateFailed as err:
                    _LOGGER.warning(
                        "Full refresh after plant update failed: %s. "
                        "Keeping stale data",
                        err,
                    )
            else:
                # Incremental update: merge partial changes into current state
                new_data = self._merge_updates(update_list)
                self.async_set_updated_data(new_data)

            # Throttle before next long-poll call
            await asyncio.sleep(UPDATE_THROTTLE_DELAY)

    def _merge_updates(self, update_list) -> dict[str, Any]:
        """Merge incremental device updates into the current coordinator data.

        For each ThermoZoneUpdate, finds the matching ThermoZone by act_id
        and merges the update's raw_data into the zone's raw_data. Only keys
        present in the update are overwritten; missing fields are preserved.

        Args:
            update_list: The UpdateList from async_get_updates().

        Returns:
            A new data dict with the merged state.
        """
        data = dict(self.data)

        # Merge thermostat (thermo zone) updates
        thermo_updates = update_list.get_typed_by_device_type(DeviceType.THERMOSTAT)
        _LOGGER.debug(
            "Merging incremental updates: %d thermo zone update(s)",
            len(thermo_updates) if thermo_updates else 0,
        )
        if thermo_updates:
            zone_map: dict[int, ThermoZone] = {
                z.act_id: z for z in data.get("thermo_zones", [])
            }
            for update in thermo_updates:
                if update.act_id in zone_map:
                    zone_map[update.act_id].raw_data.update(update.raw_data)
                    _LOGGER.debug(
                        "Applied update to thermo zone '%s' (act_id=%d)",
                        update.name,
                        update.act_id,
                    )
                else:
                    _LOGGER.debug(
                        "Received update for unknown thermo zone act_id=%d, ignoring",
                        update.act_id,
                    )
            data["thermo_zones"] = list(zone_map.values())

        return data
