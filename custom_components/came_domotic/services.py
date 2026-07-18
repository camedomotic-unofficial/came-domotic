"""Service actions for the CAME Domotic integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_CONFIG_ENTRY_ID, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
)
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
)
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .api import (
    CameDomoticApiClient,
    CameDomoticApiClientAuthenticationError,
    CameDomoticApiClientCommunicationError,
)
from .const import DOMAIN

if TYPE_CHECKING:
    from aiocamedomotic.models import Scenario

    from . import CameDomoticConfigEntry

_LOGGER = logging.getLogger(__name__)

# Service names
SERVICE_CREATE_USER = "create_user"
SERVICE_DELETE_USER = "delete_user"
SERVICE_CHANGE_PASSWORD = "change_password"  # noqa: S105  # nosec B105
SERVICE_GET_TERMINAL_GROUPS = "get_terminal_groups"
SERVICE_GET_USERS = "get_users"
SERVICE_FORCE_REFRESH = "force_refresh"
SERVICE_START_SCENARIO_RECORDING = "start_scenario_recording"
SERVICE_STOP_SCENARIO_RECORDING = "stop_scenario_recording"
SERVICE_RENAME_SCENARIO = "rename_scenario"
SERVICE_DELETE_SCENARIO = "delete_scenario"
SERVICE_RESET_ENERGY_COUNTERS = "reset_energy_counters"
SERVICE_GET_SERVER_DATETIME = "get_server_datetime"

# Field attribute names
ATTR_USERNAME = "username"
ATTR_PASSWORD = "password"  # noqa: S105  # nosec B105
ATTR_CURRENT_PASSWORD = "current_password"  # noqa: S105  # nosec B105
ATTR_NEW_PASSWORD = "new_password"  # noqa: S105  # nosec B105
ATTR_GROUP = "group"
ATTR_NAME = "name"
ATTR_NEW_NAME = "new_name"

# Voluptuous schemas
SERVICE_CREATE_USER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_USERNAME): cv.string,
        vol.Required(ATTR_PASSWORD): cv.string,
        vol.Optional(ATTR_GROUP, default="*"): cv.string,
    }
)

SERVICE_DELETE_USER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_USERNAME): cv.string,
    }
)

SERVICE_CHANGE_PASSWORD_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_USERNAME): cv.string,
        vol.Required(ATTR_CURRENT_PASSWORD): cv.string,
        vol.Required(ATTR_NEW_PASSWORD): cv.string,
    }
)

SERVICE_GET_TERMINAL_GROUPS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)

SERVICE_GET_USERS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)

SERVICE_FORCE_REFRESH_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)

SERVICE_START_SCENARIO_RECORDING_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_NAME): vol.All(cv.string, vol.Length(min=1)),
    }
)

SERVICE_STOP_SCENARIO_RECORDING_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)

SERVICE_RENAME_SCENARIO_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_NAME): vol.All(cv.string, vol.Length(min=1)),
        vol.Required(ATTR_NEW_NAME): vol.All(cv.string, vol.Length(min=1)),
    }
)

SERVICE_DELETE_SCENARIO_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
        vol.Required(ATTR_NAME): vol.All(cv.string, vol.Length(min=1)),
    }
)

SERVICE_RESET_ENERGY_COUNTERS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)

SERVICE_GET_SERVER_DATETIME_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONFIG_ENTRY_ID): cv.string,
    }
)


def _get_entry_and_client(
    hass: HomeAssistant, call: ServiceCall
) -> tuple[CameDomoticConfigEntry, CameDomoticApiClient]:
    """Validate config entry and return the entry and API client.

    Raises:
        ServiceValidationError: If the config entry is not found or not loaded.
    """
    entry_id: str = call.data[ATTR_CONFIG_ENTRY_ID]

    entry: CameDomoticConfigEntry | None = hass.config_entries.async_get_entry(entry_id)
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_found",
            translation_placeholders={"config_entry_id": entry_id},
        )
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="config_entry_not_loaded",
            translation_placeholders={"config_entry_id": entry_id},
        )

    return entry, entry.runtime_data.client


async def _get_user_defined_scenario(
    client: CameDomoticApiClient, name: str
) -> Scenario:
    """Look up a user-defined scenario by name.

    If multiple scenarios share the same name, the one with the highest id
    (the most recently created) is returned, consistently with the library's
    stop-recording behavior.

    Raises:
        ServiceValidationError: If no scenario matches the name, or the
            matched scenario is system-defined.
        HomeAssistantError: If fetching the scenario list fails.
    """
    try:
        scenarios = await client.async_get_scenarios()
    except CameDomoticApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticApiClientCommunicationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(err)},
        ) from err

    matches = [s for s in scenarios if s.name == name]
    if not matches:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="scenario_not_found",
            translation_placeholders={"name": name},
        )

    scenario = max(matches, key=lambda s: s.id)
    if not scenario.user_defined:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="scenario_not_user_defined",
            translation_placeholders={"name": name},
        )

    return scenario


async def async_handle_create_user(call: ServiceCall) -> None:
    """Handle the create_user service call."""
    hass = call.hass
    _, client = _get_entry_and_client(hass, call)

    username: str = call.data[ATTR_USERNAME]
    password: str = call.data[ATTR_PASSWORD]
    group: str = call.data[ATTR_GROUP]

    _LOGGER.debug("Service call: creating user '%s' with group '%s'", username, group)

    # Validate that the specified group exists (skip for wildcard "*")
    if group != "*":
        try:
            groups = await client.async_get_terminal_groups()
        except CameDomoticApiClientAuthenticationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_auth_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except CameDomoticApiClientCommunicationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_comm_error",
                translation_placeholders={"error": str(err)},
            ) from err

        if not any(g.name == group for g in groups):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="group_not_found",
                translation_placeholders={"group": group},
            )

    try:
        await client.async_add_user(username, password, group=group)
    except CameDomoticApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticApiClientCommunicationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(err)},
        ) from err

    _LOGGER.debug("User '%s' created successfully", username)


async def async_handle_delete_user(call: ServiceCall) -> None:
    """Handle the delete_user service call."""
    hass = call.hass
    _, client = _get_entry_and_client(hass, call)

    username: str = call.data[ATTR_USERNAME]

    _LOGGER.debug("Service call: deleting user '%s'", username)

    # Look up the User object by name
    try:
        users = await client.async_get_users()
    except CameDomoticApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticApiClientCommunicationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(err)},
        ) from err

    user = next((u for u in users if u.name == username), None)
    if user is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="user_not_found",
            translation_placeholders={"username": username},
        )

    try:
        await client.async_delete_user(user)
    except ValueError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="cannot_delete_current_user",
            translation_placeholders={"username": username},
        ) from err
    except CameDomoticApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticApiClientCommunicationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(err)},
        ) from err

    _LOGGER.debug("User '%s' deleted successfully", username)


async def async_handle_change_password(call: ServiceCall) -> None:
    """Handle the change_password service call."""
    hass = call.hass
    entry, client = _get_entry_and_client(hass, call)

    username: str = call.data[ATTR_USERNAME]
    current_password: str = call.data[ATTR_CURRENT_PASSWORD]
    new_password: str = call.data[ATTR_NEW_PASSWORD]

    _LOGGER.debug("Service call: changing password for user '%s'", username)

    # Look up the User object by name
    try:
        users = await client.async_get_users()
    except CameDomoticApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticApiClientCommunicationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(err)},
        ) from err

    user = next((u for u in users if u.name == username), None)
    if user is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="user_not_found",
            translation_placeholders={"username": username},
        )

    try:
        await client.async_change_user_password(user, current_password, new_password)
    except CameDomoticApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticApiClientCommunicationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(err)},
        ) from err

    # If we changed the authenticated user's password, update the config entry
    if username == entry.data.get(CONF_USERNAME):
        _LOGGER.debug(
            "Updating config entry credentials for authenticated user '%s'", username
        )
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_PASSWORD: new_password}
        )

    _LOGGER.debug("Password changed for user '%s'", username)


async def async_handle_get_terminal_groups(call: ServiceCall) -> ServiceResponse:
    """Handle the get_terminal_groups service call."""
    hass = call.hass
    _, client = _get_entry_and_client(hass, call)

    _LOGGER.debug("Service call: fetching terminal groups")

    try:
        groups = await client.async_get_terminal_groups()
    except CameDomoticApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticApiClientCommunicationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(err)},
        ) from err

    _LOGGER.debug("Fetched %d terminal group(s)", len(groups))

    return {
        "terminal_groups": [{"id": group.id, "name": group.name} for group in groups]
    }


async def async_handle_get_users(call: ServiceCall) -> ServiceResponse:
    """Handle the get_users service call."""
    hass = call.hass
    _, client = _get_entry_and_client(hass, call)

    _LOGGER.debug("Service call: fetching users")

    try:
        users = await client.async_get_users()
    except CameDomoticApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticApiClientCommunicationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(err)},
        ) from err

    _LOGGER.debug("Fetched %d user(s)", len(users))

    return {"users": [{"name": user.name} for user in users]}


async def async_handle_force_refresh(call: ServiceCall) -> None:
    """Handle the force_refresh service call."""
    hass = call.hass
    entry, _ = _get_entry_and_client(hass, call)
    coordinator = entry.runtime_data.coordinator

    _LOGGER.debug("Service call: forcing full data refresh")

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(coordinator.last_exception)},
        )

    _LOGGER.debug("Full data refresh completed successfully")


async def async_handle_start_scenario_recording(call: ServiceCall) -> None:
    """Handle the start_scenario_recording service call."""
    hass = call.hass
    _, client = _get_entry_and_client(hass, call)

    name: str = call.data[ATTR_NAME]

    _LOGGER.debug("Service call: starting recording of scenario '%s'", name)

    try:
        await client.async_start_scenario_recording(name)
    except ValueError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_scenario_name",
            translation_placeholders={"name": name},
        ) from err
    except CameDomoticApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticApiClientCommunicationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(err)},
        ) from err

    _LOGGER.debug("Scenario recording started for '%s'", name)


async def async_handle_stop_scenario_recording(call: ServiceCall) -> ServiceResponse:
    """Handle the stop_scenario_recording service call."""
    hass = call.hass
    entry, client = _get_entry_and_client(hass, call)

    _LOGGER.debug("Service call: stopping scenario recording")

    try:
        scenario = await client.async_stop_scenario_recording()
    except CameDomoticApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticApiClientCommunicationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(err)},
        ) from err

    # Reload the entry so the new scenario shows up as a scene entity
    hass.config_entries.async_schedule_reload(entry.entry_id)

    if not call.return_response:
        return None
    return {
        "scenario": (
            {"id": scenario.id, "name": scenario.name} if scenario is not None else None
        )
    }


async def async_handle_rename_scenario(call: ServiceCall) -> None:
    """Handle the rename_scenario service call."""
    hass = call.hass
    entry, client = _get_entry_and_client(hass, call)

    name: str = call.data[ATTR_NAME]
    new_name: str = call.data[ATTR_NEW_NAME]

    _LOGGER.debug("Service call: renaming scenario '%s' to '%s'", name, new_name)

    scenario = await _get_user_defined_scenario(client, name)

    try:
        await client.async_rename_scenario(scenario, new_name)
    except ValueError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_scenario_name",
            translation_placeholders={"name": new_name},
        ) from err
    except CameDomoticApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticApiClientCommunicationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(err)},
        ) from err

    # Reload the entry so the scene entity reflects the new name
    hass.config_entries.async_schedule_reload(entry.entry_id)

    _LOGGER.debug("Scenario '%s' renamed to '%s'", name, new_name)


async def async_handle_delete_scenario(call: ServiceCall) -> None:
    """Handle the delete_scenario service call."""
    hass = call.hass
    entry, client = _get_entry_and_client(hass, call)

    name: str = call.data[ATTR_NAME]

    _LOGGER.debug("Service call: deleting scenario '%s'", name)

    scenario = await _get_user_defined_scenario(client, name)

    try:
        await client.async_delete_scenario(scenario)
    except CameDomoticApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticApiClientCommunicationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(err)},
        ) from err

    # Reload the entry so the deleted scenario's scene entity is removed
    hass.config_entries.async_schedule_reload(entry.entry_id)

    _LOGGER.debug("Scenario '%s' deleted successfully", name)


async def async_handle_reset_energy_counters(call: ServiceCall) -> None:
    """Handle the reset_energy_counters service call."""
    hass = call.hass
    _, client = _get_entry_and_client(hass, call)

    _LOGGER.debug("Service call: resetting energy counters")

    try:
        await client.async_reset_energy_counters()
    except CameDomoticApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticApiClientCommunicationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(err)},
        ) from err

    _LOGGER.debug("Energy counters reset successfully")


async def async_handle_get_server_datetime(call: ServiceCall) -> ServiceResponse:
    """Handle the get_server_datetime service call."""
    hass = call.hass
    _, client = _get_entry_and_client(hass, call)

    _LOGGER.debug("Service call: fetching server datetime")

    try:
        server_datetime = await client.async_get_server_datetime()
    except CameDomoticApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticApiClientCommunicationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(err)},
        ) from err

    utc_datetime = server_datetime.utc_datetime
    return {
        "datetime": server_datetime.datetime_string,
        "epoch": server_datetime.epoch,
        "utc_datetime": utc_datetime.isoformat() if utc_datetime else None,
        "timezone": server_datetime.timezone_name,
        "daylight_saving_time": server_datetime.daylight_saving_time,
    }


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration services (idempotent)."""
    if hass.services.has_service(DOMAIN, SERVICE_CREATE_USER):
        return

    hass.services.async_register(
        DOMAIN,
        SERVICE_CREATE_USER,
        async_handle_create_user,
        schema=SERVICE_CREATE_USER_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_USER,
        async_handle_delete_user,
        schema=SERVICE_DELETE_USER_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CHANGE_PASSWORD,
        async_handle_change_password,
        schema=SERVICE_CHANGE_PASSWORD_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_TERMINAL_GROUPS,
        async_handle_get_terminal_groups,
        schema=SERVICE_GET_TERMINAL_GROUPS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_USERS,
        async_handle_get_users,
        schema=SERVICE_GET_USERS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_FORCE_REFRESH,
        async_handle_force_refresh,
        schema=SERVICE_FORCE_REFRESH_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_START_SCENARIO_RECORDING,
        async_handle_start_scenario_recording,
        schema=SERVICE_START_SCENARIO_RECORDING_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_STOP_SCENARIO_RECORDING,
        async_handle_stop_scenario_recording,
        schema=SERVICE_STOP_SCENARIO_RECORDING_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RENAME_SCENARIO,
        async_handle_rename_scenario,
        schema=SERVICE_RENAME_SCENARIO_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_DELETE_SCENARIO,
        async_handle_delete_scenario,
        schema=SERVICE_DELETE_SCENARIO_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET_ENERGY_COUNTERS,
        async_handle_reset_energy_counters,
        schema=SERVICE_RESET_ENERGY_COUNTERS_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_SERVER_DATETIME,
        async_handle_get_server_datetime,
        schema=SERVICE_GET_SERVER_DATETIME_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )

    _LOGGER.debug("Registered %s services", DOMAIN)


async def async_unload_services(hass: HomeAssistant) -> None:
    """Unload services if no more config entries are loaded."""
    # Only remove services when the last config entry is unloaded
    loaded_entries = [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.state is ConfigEntryState.LOADED
    ]
    if loaded_entries:
        return

    for service in (
        SERVICE_CREATE_USER,
        SERVICE_DELETE_USER,
        SERVICE_CHANGE_PASSWORD,
        SERVICE_GET_TERMINAL_GROUPS,
        SERVICE_GET_USERS,
        SERVICE_FORCE_REFRESH,
        SERVICE_START_SCENARIO_RECORDING,
        SERVICE_STOP_SCENARIO_RECORDING,
        SERVICE_RENAME_SCENARIO,
        SERVICE_DELETE_SCENARIO,
        SERVICE_RESET_ENERGY_COUNTERS,
        SERVICE_GET_SERVER_DATETIME,
    ):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)

    _LOGGER.debug("Removed %s services", DOMAIN)
