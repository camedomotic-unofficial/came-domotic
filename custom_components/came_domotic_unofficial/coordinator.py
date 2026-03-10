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

from aiocamedomotic.models import DeviceType
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
    SESSION_RECYCLE_THRESHOLD,
    UPDATE_THROTTLE_DELAY,
)
from .models import CameDomoticServerData

_LOGGER: logging.Logger = logging.getLogger(__name__)


class CameDomoticUnofficialDataUpdateCoordinator(
    DataUpdateCoordinator[CameDomoticServerData]
):
    """Coordinator that manages push-based data updates via long polling.

    On first refresh, performs a full data fetch from the CAME server.
    After that, a background task long-polls for incremental updates
    and pushes them to entities via async_set_updated_data().
    """

    config_entry: ConfigEntry
    data: CameDomoticServerData

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
        # Tracks successful long-poll calls to trigger periodic session recycling.
        # See _async_recycle_session() for why this is needed (cseq reset).
        self._long_poll_count: int = 0
        _LOGGER.debug("Coordinator initialized (push-based, no polling interval)")

    async def _async_update_data(self) -> CameDomoticServerData:
        """Perform a full data fetch from the CAME server.

        Called during initial setup (async_config_entry_first_refresh) and
        when a plant configuration change is detected.
        """
        try:
            server_info = await self.api.async_get_server_info()
            thermo_zones = await self.api.async_get_thermo_zones()
            scenarios = await self.api.async_get_scenarios()
            openings = await self.api.async_get_openings()
            lights = await self.api.async_get_lights()
        except CameDomoticUnofficialApiClientAuthenticationError as exception:
            _LOGGER.warning("Authentication failed during data update")
            raise ConfigEntryAuthFailed(exception) from exception
        except CameDomoticUnofficialApiClientError as exception:
            _LOGGER.warning("Error updating data: %s", exception)
            raise UpdateFailed(exception) from exception

        _LOGGER.debug(
            "Full data fetch complete: %d thermo zone(s), %d scenario(s), "
            "%d opening(s), %d light(s)",
            len(thermo_zones),
            len(scenarios),
            len(openings),
            len(lights),
        )
        return CameDomoticServerData(
            server_info=server_info,
            thermo_zones={z.act_id: z for z in thermo_zones},
            scenarios={s.id: s for s in scenarios},
            openings={o.open_act_id: o for o in openings},
            lights={lt.act_id: lt for lt in lights},
        )

    def start_long_poll(self) -> None:
        """Start the background long-polling task.

        Creates an asyncio task that continuously long-polls the CAME server
        for device state changes. Must be called after the initial data fetch.
        """
        if self._long_poll_task is not None:
            _LOGGER.warning("Long-poll task already running, not starting another")
            return
        self._long_poll_task = self.config_entry.async_create_background_task(
            self.hass,
            self._async_long_poll_loop(),
            name=f"{DOMAIN}_long_poll_{self.config_entry.entry_id}",
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

    async def _async_recycle_session(self) -> None:
        """Dispose and recreate the API session, then do a full data fetch.

        The CAME Domotic server tracks a command sequence number (cseq) for
        each API call within a session. Since Home Assistant runs continuously
        for weeks or months, the cseq can grow very large. The server is
        likely not designed for such long-running sessions, so high cseq
        values may hit server-side limits. Recycling the session resets the
        cseq to zero, preventing potential issues.
        """
        _LOGGER.info(
            "Recycling API session after %d long-poll calls",
            self._long_poll_count,
        )
        await self.api.async_dispose()
        await self.api.async_connect()
        new_data = await self._async_update_data()
        self.async_set_updated_data(new_data)
        self._long_poll_count = 0
        _LOGGER.debug("Session recycled successfully")

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
            # Check if session recycling is needed (cseq reset)
            if self._long_poll_count >= SESSION_RECYCLE_THRESHOLD:
                try:
                    await self._async_recycle_session()
                except CameDomoticUnofficialApiClientAuthenticationError:
                    _LOGGER.warning(
                        "Authentication failed during session recycle, "
                        "triggering reauth"
                    )
                    self.config_entry.async_start_reauth(self.hass)
                    return
                except CameDomoticUnofficialApiClientError as err:
                    _LOGGER.warning(
                        "Error during session recycle: %s. Retrying in %ds",
                        err,
                        RECONNECT_DELAY,
                    )
                    await asyncio.sleep(RECONNECT_DELAY)
                    continue

            try:
                update_list = await self.api.async_get_updates(
                    timeout=DEFAULT_LONG_POLL_TIMEOUT
                )
            except CameDomoticUnofficialApiClientAuthenticationError:
                _LOGGER.warning(
                    "Authentication failed in long-poll loop, triggering reauth"
                )
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

            self._long_poll_count += 1

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
                self._merge_updates(update_list)
                self.async_set_updated_data(self.data)

            # Throttle before next long-poll call
            await asyncio.sleep(UPDATE_THROTTLE_DELAY)

    def _merge_updates(self, update_list) -> None:
        """Merge incremental device updates into the current coordinator data.

        For each device update, finds the matching device by its identifier
        and merges the update's raw_data into the device's raw_data. Only keys
        present in the update are overwritten; missing fields are preserved.

        Mutates self.data in-place.

        Args:
            update_list: The UpdateList from async_get_updates().
        """
        # Merge thermostat (thermo zone) updates
        thermo_updates = update_list.get_typed_by_device_type(DeviceType.THERMOSTAT)
        _LOGGER.debug(
            "Merging incremental updates: %d thermo zone update(s)",
            len(thermo_updates) if thermo_updates else 0,
        )
        for update in thermo_updates:
            zone = self.data.thermo_zones.get(update.act_id)
            if zone is not None:
                zone.raw_data.update(update.raw_data)
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

        # Merge scenario updates
        scenario_updates = update_list.get_typed_by_device_type(DeviceType.SCENARIO)
        _LOGGER.debug(
            "Merging incremental updates: %d scenario update(s)",
            len(scenario_updates) if scenario_updates else 0,
        )
        for update in scenario_updates:
            scenario = self.data.scenarios.get(update.id)
            if scenario is not None:
                scenario.raw_data.update(update.raw_data)
                _LOGGER.debug(
                    "Applied update to scenario '%s' (id=%d)",
                    update.name,
                    update.id,
                )
            else:
                _LOGGER.debug(
                    "Received update for unknown scenario id=%d, ignoring",
                    update.id,
                )

        # Merge opening updates
        opening_updates = update_list.get_typed_by_device_type(DeviceType.OPENING)
        _LOGGER.debug(
            "Merging incremental updates: %d opening update(s)",
            len(opening_updates) if opening_updates else 0,
        )
        for update in opening_updates:
            opening = self.data.openings.get(update.open_act_id)
            if opening is not None:
                opening.raw_data.update(update.raw_data)
                _LOGGER.debug(
                    "Applied update to opening '%s' (open_act_id=%d)",
                    update.name,
                    update.open_act_id,
                )
            else:
                _LOGGER.debug(
                    "Received update for unknown opening open_act_id=%d, ignoring",
                    update.open_act_id,
                )

        # Merge light updates
        light_updates = update_list.get_typed_by_device_type(DeviceType.LIGHT)
        _LOGGER.debug(
            "Merging incremental updates: %d light update(s)",
            len(light_updates) if light_updates else 0,
        )
        for update in light_updates:
            light = self.data.lights.get(update.act_id)
            if light is not None:
                light.raw_data.update(update.raw_data)
                _LOGGER.debug(
                    "Applied update to light '%s' (act_id=%d)",
                    update.name,
                    update.act_id,
                )
            else:
                _LOGGER.debug(
                    "Received update for unknown light act_id=%d, ignoring",
                    update.act_id,
                )
