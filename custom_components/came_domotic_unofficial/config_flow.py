"""Adds config flow for CAME Domotic Unofficial."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import voluptuous as vol

from .api import (
    CameDomoticUnofficialApiClient,
    CameDomoticUnofficialApiClientAuthenticationError,
    CameDomoticUnofficialApiClientCommunicationError,
    CameDomoticUnofficialApiClientError,
)
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN, MIN_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_USERNAME): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(
            CONF_SCAN_INTERVAL,
            default=DEFAULT_SCAN_INTERVAL,
        ): vol.All(vol.Coerce(int), vol.Clamp(min=MIN_SCAN_INTERVAL)),
    }
)


async def _async_test_credentials(
    hass,
    host: str,
    username: str,
    password: str,
) -> str:
    """Validate credentials and return the server keycode.

    Raises CannotConnect or InvalidAuth on failure.
    """
    _LOGGER.debug("Testing credentials for host %s", host)
    session = async_get_clientsession(hass)
    client = CameDomoticUnofficialApiClient(host, username, password, session)
    try:
        await client.async_connect()
        server_info = await client.async_get_server_info()
        _LOGGER.debug("Credentials validated, server keycode: %s", server_info.keycode)
        return server_info.keycode
    except CameDomoticUnofficialApiClientAuthenticationError as err:
        raise InvalidAuth from err
    except CameDomoticUnofficialApiClientCommunicationError as err:
        raise CannotConnect from err
    except CameDomoticUnofficialApiClientError as err:
        raise CannotConnect from err
    finally:
        await client.async_dispose()


class CameDomoticUnofficialFlowHandler(ConfigFlow, domain=DOMAIN):
    """Config flow for came_domotic_unofficial."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return CameDomoticUnofficialOptionsFlowHandler()

    async def async_step_user(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                keycode = await _async_test_credentials(
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
                data = {k: v for k, v in user_input.items() if k != CONF_SCAN_INTERVAL}
                options = {
                    CONF_SCAN_INTERVAL: user_input.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                }
                _LOGGER.info(
                    "Configuration entry created for %s", user_input[CONF_HOST]
                )
                return self.async_create_entry(
                    title=f"CAME Domotic ({user_input[CONF_HOST]})",
                    data=data,
                    options=options,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            description_placeholders={
                "documentation_url": "https://github.com/camedomotic-unofficial/came-domotic-unofficial"
            },
            errors=errors,
        )

    async def async_step_reauth(
        self,
        entry_data: dict[str, Any],  # noqa: ARG002
    ) -> ConfigFlowResult:
        """Handle reauth when credentials become invalid."""
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
                await _async_test_credentials(
                    self.hass,
                    reauth_entry.data[CONF_HOST],
                    user_input[CONF_USERNAME],
                    user_input[CONF_PASSWORD],
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
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
                    },
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_USERNAME,
                        default=reauth_entry.data[CONF_USERNAME],
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                }
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

        if user_input is not None:
            try:
                await _async_test_credentials(
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
                data = {k: v for k, v in user_input.items() if k != CONF_SCAN_INTERVAL}
                options = {
                    CONF_SCAN_INTERVAL: user_input.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                }
                _LOGGER.info(
                    "Configuration entry updated for %s", user_input[CONF_HOST]
                )
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    unique_id=reconfigure_entry.unique_id,
                    data={**reconfigure_entry.data, **data},
                    options=options,
                    reason="reconfigure_successful",
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_HOST,
                        default=reconfigure_entry.data[CONF_HOST],
                    ): str,
                    vol.Required(
                        CONF_USERNAME,
                        default=reconfigure_entry.data[CONF_USERNAME],
                    ): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=reconfigure_entry.options.get(
                            CONF_SCAN_INTERVAL,
                            DEFAULT_SCAN_INTERVAL,
                        ),
                    ): vol.All(vol.Coerce(int), vol.Clamp(min=MIN_SCAN_INTERVAL)),
                }
            ),
            errors=errors,
        )


class CameDomoticUnofficialOptionsFlowHandler(OptionsFlow):
    """Config flow options handler for came_domotic_unofficial."""

    async def async_step_init(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            _LOGGER.debug(
                "Options updated: scan_interval=%ds",
                user_input[CONF_SCAN_INTERVAL],
            )
            return self.async_create_entry(
                title="",
                data={CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL]},
            )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL,
                            DEFAULT_SCAN_INTERVAL,
                        ),
                    ): vol.All(vol.Coerce(int), vol.Clamp(min=MIN_SCAN_INTERVAL)),
                }
            ),
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""
