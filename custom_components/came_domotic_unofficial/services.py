"""Service actions for the CAME Domotic Unofficial integration."""

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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import homeassistant.helpers.config_validation as cv
import voluptuous as vol

from .api import (
    CameDomoticUnofficialApiClient,
    CameDomoticUnofficialApiClientAuthenticationError,
    CameDomoticUnofficialApiClientCommunicationError,
)
from .const import DOMAIN

if TYPE_CHECKING:
    from . import CameDomoticUnofficialConfigEntry

_LOGGER = logging.getLogger(__name__)

# Service names
SERVICE_CREATE_USER = "create_user"
SERVICE_DELETE_USER = "delete_user"
SERVICE_CHANGE_PASSWORD = "change_password"  # noqa: S105  # nosec B105
SERVICE_GET_TERMINAL_GROUPS = "get_terminal_groups"

# Field attribute names
ATTR_USERNAME = "username"
ATTR_PASSWORD = "password"  # noqa: S105  # nosec B105
ATTR_CURRENT_PASSWORD = "current_password"  # noqa: S105  # nosec B105
ATTR_NEW_PASSWORD = "new_password"  # noqa: S105  # nosec B105
ATTR_GROUP = "group"

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


def _get_entry_and_client(
    hass: HomeAssistant, call: ServiceCall
) -> tuple[CameDomoticUnofficialConfigEntry, CameDomoticUnofficialApiClient]:
    """Validate config entry and return the entry and API client.

    Raises:
        ServiceValidationError: If the config entry is not found or not loaded.
    """
    entry_id: str = call.data[ATTR_CONFIG_ENTRY_ID]

    entry: CameDomoticUnofficialConfigEntry | None = (
        hass.config_entries.async_get_entry(entry_id)
    )
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
        except CameDomoticUnofficialApiClientAuthenticationError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="service_auth_error",
                translation_placeholders={"error": str(err)},
            ) from err
        except CameDomoticUnofficialApiClientCommunicationError as err:
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
    except CameDomoticUnofficialApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticUnofficialApiClientCommunicationError as err:
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
    except CameDomoticUnofficialApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticUnofficialApiClientCommunicationError as err:
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
    except CameDomoticUnofficialApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticUnofficialApiClientCommunicationError as err:
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
    except CameDomoticUnofficialApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticUnofficialApiClientCommunicationError as err:
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
    except CameDomoticUnofficialApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticUnofficialApiClientCommunicationError as err:
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
    except CameDomoticUnofficialApiClientAuthenticationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_auth_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except CameDomoticUnofficialApiClientCommunicationError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="service_comm_error",
            translation_placeholders={"error": str(err)},
        ) from err

    _LOGGER.debug("Fetched %d terminal group(s)", len(groups))

    return {
        "terminal_groups": [{"id": group.id, "name": group.name} for group in groups]
    }


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration services."""
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

    hass.services.async_remove(DOMAIN, SERVICE_CREATE_USER)
    hass.services.async_remove(DOMAIN, SERVICE_DELETE_USER)
    hass.services.async_remove(DOMAIN, SERVICE_CHANGE_PASSWORD)
    hass.services.async_remove(DOMAIN, SERVICE_GET_TERMINAL_GROUPS)

    _LOGGER.debug("Removed %s services", DOMAIN)
