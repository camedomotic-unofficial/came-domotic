"""Test CAME Domotic config flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic.api import (
    CameDomoticApiClientAuthenticationError,
    CameDomoticApiClientCommunicationError,
    CameDomoticApiClientError,
)
from custom_components.came_domotic.const import DOMAIN

from .const import MOCK_CONFIG, MOCK_KEYCODE

_API_CLIENT = "custom_components.came_domotic.api.CameDomoticApiClient"


@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch(
        "custom_components.came_domotic.async_setup_entry",
        return_value=True,
    ):
        yield


# --- User flow ---


async def test_successful_config_flow(hass, bypass_test_credentials):
    """Test a successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"CAME Domotic ({MOCK_CONFIG[CONF_HOST]})"
    assert result["data"] == MOCK_CONFIG
    assert result["result"]


async def test_config_flow_cannot_connect(hass):
    """Test config flow with connection error shows cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        f"{_API_CLIENT}.async_connect",
        side_effect=CameDomoticApiClientCommunicationError("Timeout"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_config_flow_invalid_auth(hass):
    """Test config flow with authentication error shows invalid_auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            side_effect=CameDomoticApiClientAuthenticationError("Bad creds"),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_config_flow_unknown_error(hass):
    """Test config flow with unexpected exception shows unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        f"{_API_CLIENT}.async_connect",
        side_effect=Exception("Unexpected"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_config_flow_duplicate_server_abort(hass, bypass_test_credentials):
    """Test that configuring the same server (same unique_id) is aborted."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_config_flow_generic_api_error(hass):
    """Test that base ApiClientError (non-comm, non-auth) maps to cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            f"{_API_CLIENT}.async_connect",
            side_effect=CameDomoticApiClientError("Parse error"),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


# --- Reauth flow ---


async def _init_reauth_flow(hass, entry):
    """Start a reauth flow and return the form result."""
    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    return result


async def test_reauth_flow_success(hass, bypass_test_credentials):
    """Test successful reauth flow updates credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id=MOCK_KEYCODE,
    )
    entry.add_to_hass(hass)

    result = await _init_reauth_flow(hass, entry)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_USERNAME: "new_user", CONF_PASSWORD: "new_pass"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_USERNAME] == "new_user"
    assert entry.data[CONF_PASSWORD] == "new_pass"


async def test_reauth_flow_invalid_auth(hass):
    """Test reauth flow with auth error shows invalid_auth."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE)
    entry.add_to_hass(hass)
    result = await _init_reauth_flow(hass, entry)

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            side_effect=CameDomoticApiClientAuthenticationError("Bad creds"),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "user", CONF_PASSWORD: "wrong"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_cannot_connect(hass):
    """Test reauth flow with connection error shows cannot_connect."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE)
    entry.add_to_hass(hass)
    result = await _init_reauth_flow(hass, entry)

    with patch(
        f"{_API_CLIENT}.async_connect",
        side_effect=CameDomoticApiClientCommunicationError("Timeout"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reauth_flow_unknown_error(hass):
    """Test reauth flow with unexpected error shows unknown."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE)
    entry.add_to_hass(hass)
    result = await _init_reauth_flow(hass, entry)

    with patch(
        f"{_API_CLIENT}.async_connect",
        side_effect=Exception("Unexpected"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


# --- Reconfigure flow ---


async def _init_reconfigure_flow(hass, entry):
    """Start a reconfigure flow and return the form result."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )
    assert result["type"] is FlowResultType.FORM
    return result


async def test_reconfigure_flow_success(hass, bypass_test_credentials):
    """Test successful reconfigure flow updates credentials."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        unique_id=MOCK_KEYCODE,
    )
    entry.add_to_hass(hass)

    result = await _init_reconfigure_flow(hass, entry)
    assert result["step_id"] == "reconfigure"

    new_input = {
        CONF_HOST: "192.168.1.200",
        CONF_USERNAME: "new_user",
        CONF_PASSWORD: "new_pass",
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=new_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.168.1.200"
    assert entry.data[CONF_USERNAME] == "new_user"
    assert entry.data[CONF_PASSWORD] == "new_pass"


async def test_reconfigure_flow_cannot_connect(hass):
    """Test reconfigure flow with connection error shows cannot_connect."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE)
    entry.add_to_hass(hass)
    result = await _init_reconfigure_flow(hass, entry)

    with patch(
        f"{_API_CLIENT}.async_connect",
        side_effect=CameDomoticApiClientCommunicationError("Timeout"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_invalid_auth(hass):
    """Test reconfigure flow with auth error shows invalid_auth."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE)
    entry.add_to_hass(hass)
    result = await _init_reconfigure_flow(hass, entry)

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            side_effect=CameDomoticApiClientAuthenticationError("Bad creds"),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_flow_unknown_error(hass):
    """Test reconfigure flow with unexpected error shows unknown."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE)
    entry.add_to_hass(hass)
    result = await _init_reconfigure_flow(hass, entry)

    with patch(
        f"{_API_CLIENT}.async_connect",
        side_effect=Exception("Unexpected"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_CONFIG
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


# --- DHCP discovery flow ---

MOCK_DHCP_SERVICE_INFO = DhcpServiceInfo(
    ip=MOCK_CONFIG[CONF_HOST],
    hostname="came-server",
    macaddress="001cb2ddeeff",
)

_IS_CAME_ENDPOINT = "custom_components.came_domotic.config_flow.async_is_came_endpoint"


async def test_dhcp_discovery_new_device(hass, bypass_test_credentials):
    """Test successful DHCP discovery of a new CAME device."""
    with patch(_IS_CAME_ENDPOINT, return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=MOCK_DHCP_SERVICE_INFO,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: MOCK_CONFIG[CONF_USERNAME],
            CONF_PASSWORD: MOCK_CONFIG[CONF_PASSWORD],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"CAME Domotic ({MOCK_CONFIG[CONF_HOST]})"
    assert result["data"] == MOCK_CONFIG
    assert result["result"].unique_id == MOCK_KEYCODE


async def test_dhcp_discovery_not_came_endpoint(hass):
    """Test DHCP discovery aborts when host is not a CAME endpoint."""
    with patch(_IS_CAME_ENDPOINT, return_value=False):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=MOCK_DHCP_SERVICE_INFO,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_came_device"


async def test_dhcp_discovery_already_configured_by_host(hass):
    """Test DHCP discovery aborts when host is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE)
    entry.add_to_hass(hass)

    with patch(_IS_CAME_ENDPOINT, return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=MOCK_DHCP_SERVICE_INFO,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery_already_configured_by_keycode(
    hass, bypass_test_credentials
):
    """Test DHCP discovery aborts when keycode matches existing entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: "192.168.1.200"},
        unique_id=MOCK_KEYCODE,
    )
    entry.add_to_hass(hass)

    with patch(_IS_CAME_ENDPOINT, return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=MOCK_DHCP_SERVICE_INFO,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: MOCK_CONFIG[CONF_USERNAME],
            CONF_PASSWORD: MOCK_CONFIG[CONF_PASSWORD],
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_dhcp_discovery_cannot_connect(hass):
    """Test DHCP discovery with connection error shows cannot_connect."""
    with patch(_IS_CAME_ENDPOINT, return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=MOCK_DHCP_SERVICE_INFO,
        )

    assert result["type"] is FlowResultType.FORM

    with patch(
        f"{_API_CLIENT}.async_connect",
        side_effect=CameDomoticApiClientCommunicationError("Timeout"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_dhcp_discovery_invalid_auth(hass):
    """Test DHCP discovery with auth error shows invalid_auth."""
    with patch(_IS_CAME_ENDPOINT, return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=MOCK_DHCP_SERVICE_INFO,
        )

    assert result["type"] is FlowResultType.FORM

    with (
        patch(f"{_API_CLIENT}.async_connect"),
        patch(
            f"{_API_CLIENT}.async_get_server_info",
            side_effect=CameDomoticApiClientAuthenticationError("Bad creds"),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "user", CONF_PASSWORD: "wrong"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_dhcp_discovery_unknown_error(hass):
    """Test DHCP discovery with unexpected error shows unknown."""
    with patch(_IS_CAME_ENDPOINT, return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_DHCP},
            data=MOCK_DHCP_SERVICE_INFO,
        )

    assert result["type"] is FlowResultType.FORM

    with patch(
        f"{_API_CLIENT}.async_connect",
        side_effect=Exception("Unexpected"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
