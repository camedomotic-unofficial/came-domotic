"""Adds config flow for CAME Domotic."""

from __future__ import annotations

import logging
from typing import Any

from aiocamedomotic import async_is_came_endpoint
from homeassistant.config_entries import (
    ConfigFlow,
    ConfigFlowResult,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
import voluptuous as vol

from .api import (
    CameDomoticApiClient,
    CameDomoticApiClientAuthenticationError,
    CameDomoticApiClientCommunicationError,
    CameDomoticApiClientError,
)
from .const import CONF_SERVER_INFO, CONF_TOPOLOGY_IMPORTED, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
    }
)


async def _async_test_credentials(
    hass,
    host: str,
    username: str,
    password: str,
) -> tuple[str, dict[str, str | None]]:
    """Validate credentials and return the server keycode and info.

    Returns a tuple of (keycode, server_info_dict).
    Raises CannotConnect or InvalidAuth on failure.
    """
    _LOGGER.debug("Testing credentials for host %s", host)
    session = async_get_clientsession(hass)
    client = CameDomoticApiClient(host, username, password, session)
    try:
        await client.async_connect()
        server_info = await client.async_get_server_info()
        _LOGGER.debug("Credentials validated, server keycode: %s", server_info.keycode)
        return server_info.keycode, {
            "board": server_info.board,
            "type": server_info.type,
            "serial": server_info.serial,
            "swver": server_info.swver,
        }
    except CameDomoticApiClientAuthenticationError as err:
        raise InvalidAuth from err
    except CameDomoticApiClientCommunicationError as err:
        raise CannotConnect from err
    except CameDomoticApiClientError as err:
        raise CannotConnect from err
    finally:
        await client.async_dispose()


class CameDomoticFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for came_domotic."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Populate flow_title placeholder (used by strings.json)
            self.context["title_placeholders"] = {
                "host": user_input[CONF_HOST],
            }
            try:
                keycode, server_info_dict = await _async_test_credentials(
                    self.hass,
                    user_input[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except CannotConnect:
                _LOGGER.warning("Cannot connect to %s", user_input[CONF_HOST])
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                _LOGGER.warning("Invalid authentication for %s", user_input[CONF_HOST])
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(keycode)
                self._abort_if_unique_id_configured()
                _LOGGER.info(
                    "Configuration entry created for %s", user_input[CONF_HOST]
                )
                return self.async_create_entry(
                    title=f"CAME Domotic ({user_input[CONF_HOST]})",
                    data={**user_input, CONF_SERVER_INFO: server_info_dict},
                )

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                STEP_USER_DATA_SCHEMA,
                user_input or {},
            ),
            description_placeholders={
                "documentation_url": "https://github.com/camedomotic-unofficial/came-domotic"
            },
            errors=errors,
        )

    async def async_step_dhcp(
        self, discovery_info: DhcpServiceInfo
    ) -> ConfigFlowResult:
        """Handle DHCP discovery of a CAME Domotic server."""
        host = discovery_info.ip
        _LOGGER.debug(
            "DHCP discovery: potential CAME device at %s (MAC: %s)",
            host,
            discovery_info.macaddress,
        )

        # Verify this is actually a CAME endpoint (filters out other BPT devices)
        session = async_get_clientsession(self.hass)
        if not await async_is_came_endpoint(host, websession=session):
            _LOGGER.debug("DHCP: host %s is not a CAME endpoint, ignoring", host)
            return self.async_abort(reason="not_came_device")
        _LOGGER.debug("DHCP: host %s confirmed as CAME endpoint", host)

        # Check if any existing entry already uses this host
        self._async_abort_entries_match({CONF_HOST: host})
        _LOGGER.debug("DHCP: host %s is not yet configured, proceeding", host)

        self._discovered_host = host
        self.context["title_placeholders"] = {"host": host}
        return await self.async_step_dhcp_confirm()

    async def async_step_dhcp_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Confirm DHCP discovery and collect credentials."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                keycode, server_info_dict = await _async_test_credentials(
                    self.hass,
                    self._discovered_host,
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during DHCP setup")
                errors["base"] = "unknown"
            else:
                await self.async_set_unique_id(keycode)
                self._abort_if_unique_id_configured()
                _LOGGER.info(
                    "DHCP: configuration entry created for %s", self._discovered_host
                )
                return self.async_create_entry(
                    title=f"CAME Domotic ({self._discovered_host})",
                    data={
                        CONF_HOST: self._discovered_host,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_SERVER_INFO: server_info_dict,
                    },
                )

        dhcp_confirm_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="dhcp_confirm",
            data_schema=self.add_suggested_values_to_schema(
                dhcp_confirm_schema,
                user_input or {},
            ),
            description_placeholders={"host": self._discovered_host},
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Handle reauth when credentials become invalid."""
        # Populate flow_title placeholder (used by strings.json)
        reauth_entry = self._get_reauth_entry()
        self.context["title_placeholders"] = {
            "host": reauth_entry.data[CONF_HOST],
        }
        return self.async_show_form(step_id="reauth_confirm")

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reauth confirmation with new credentials."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            try:
                _keycode, server_info_dict = await _async_test_credentials(
                    self.hass,
                    reauth_entry.data[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except CannotConnect:
                _LOGGER.warning(
                    "Reauth: cannot connect to %s", reauth_entry.data[CONF_HOST]
                )
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                _LOGGER.warning(
                    "Reauth: invalid authentication for %s",
                    reauth_entry.data[CONF_HOST],
                )
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception during reauth")
                errors["base"] = "unknown"
            else:
                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        **reauth_entry.data,
                        CONF_USERNAME: user_input[CONF_USERNAME],
                        CONF_PASSWORD: user_input[CONF_PASSWORD],
                        CONF_SERVER_INFO: server_info_dict,
                    },
                )

        suggested_values = user_input or {
            CONF_USERNAME: reauth_entry.data[CONF_USERNAME],
        }
        reauth_schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self.add_suggested_values_to_schema(
                reauth_schema,
                suggested_values,
            ),
            errors=errors,
        )

    async def async_step_reconfigure(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle reconfiguration of the integration."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        # Populate flow_title placeholder (used by strings.json)
        self.context["title_placeholders"] = {
            "host": (user_input or reconfigure_entry.data)[CONF_HOST],
        }

        if user_input is not None:
            try:
                _keycode, server_info_dict = await _async_test_credentials(
                    self.hass,
                    user_input[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except CannotConnect:
                _LOGGER.warning(
                    "Reconfigure: cannot connect to %s", user_input[CONF_HOST]
                )
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                _LOGGER.warning(
                    "Reconfigure: invalid authentication for %s",
                    user_input[CONF_HOST],
                )
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                _LOGGER.info(
                    "Configuration entry updated for %s", user_input[CONF_HOST]
                )
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    unique_id=reconfigure_entry.unique_id,
                    data={
                        **{
                            k: v
                            for k, v in reconfigure_entry.data.items()
                            if k != CONF_TOPOLOGY_IMPORTED
                        },
                        **user_input,
                        CONF_SERVER_INFO: server_info_dict,
                    },
                    reason="reconfigure_successful",
                )

        suggested_values = user_input or {
            CONF_HOST: reconfigure_entry.data[CONF_HOST],
            CONF_USERNAME: reconfigure_entry.data[CONF_USERNAME],
        }
        reconfigure_schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                reconfigure_schema,
                suggested_values,
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
