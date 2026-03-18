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

from .const import (
    MOCK_CONFIG,
    MOCK_CONFIG_WITH_SERVER_INFO,
    MOCK_KEYCODE_HASH,
)

_API_CLIENT = "custom_components.came_domotic.api.CameDomoticApiClient"


@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch(
        "custom_components.came_domotic.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.fixture(autouse=True)
def bypass_user_flow_probe():
    """Prevent auto-probe from finding servers during unrelated tests."""
    with (
        patch(
            "custom_components.came_domotic.config_flow.async_is_came_endpoint",
            return_value=False,
        ),
        patch(
            "homeassistant.components.network.async_get_source_ip",
            side_effect=Exception("no network"),
        ),
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
    assert result["title"] == f"CAME ETI/Domo server ({MOCK_CONFIG[CONF_HOST]})"
    assert result["data"] == MOCK_CONFIG_WITH_SERVER_INFO
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
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE_HASH
    )
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
        unique_id=MOCK_KEYCODE_HASH,
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
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE_HASH
    )
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
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE_HASH
    )
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
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE_HASH
    )
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
        unique_id=MOCK_KEYCODE_HASH,
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
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE_HASH
    )
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
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE_HASH
    )
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
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE_HASH
    )
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
    assert result["title"] == f"CAME ETI/Domo server ({MOCK_CONFIG[CONF_HOST]})"
    assert result["data"] == MOCK_CONFIG_WITH_SERVER_INFO
    assert result["result"].unique_id == MOCK_KEYCODE_HASH


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
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE_HASH
    )
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
        unique_id=MOCK_KEYCODE_HASH,
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


# --- User flow auto-probe ---


async def test_user_flow_auto_probe_found(hass, bypass_test_credentials):
    """Test that user flow auto-probes and redirects to dhcp_confirm when found."""
    with (
        patch(_IS_CAME_ENDPOINT, return_value=True),
        patch(_ASYNC_GET_SOURCE_IP, side_effect=Exception("no network")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    # Should skip the user form and show dhcp_confirm directly
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dhcp_confirm"

    # Complete the flow with credentials
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: MOCK_CONFIG[CONF_USERNAME],
            CONF_PASSWORD: MOCK_CONFIG[CONF_PASSWORD],
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] in {
        "CAME ETI/Domo server (192.168.1.3)",
        "CAME ETI/Domo server (192.168.0.3)",
    }


async def test_user_flow_auto_probe_not_found(hass):
    """Test that user flow shows normal form when auto-probe finds nothing."""
    # autouse fixture already mocks probes to return False
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


# --- _async_probe_candidate_hosts unit tests ---

_IS_CAME_ENDPOINT = "custom_components.came_domotic.config_flow.async_is_came_endpoint"
_ASYNC_GET_SOURCE_IP = "homeassistant.components.network.async_get_source_ip"


async def _run_probe(
    hass, endpoint_rv=False, endpoint_side_effect=None, source_ip_rv=None
):
    """Helper to call _async_probe_candidate_hosts with controlled mocks.

    Overrides the autouse bypass fixture patches with test-specific values.
    """
    from custom_components.came_domotic.config_flow import CameDomoticFlowHandler

    flow = CameDomoticFlowHandler()
    flow.hass = hass

    endpoint_kwargs = (
        {"side_effect": endpoint_side_effect}
        if endpoint_side_effect
        else {"return_value": endpoint_rv}
    )
    source_ip_kwargs = (
        {"return_value": source_ip_rv}
        if source_ip_rv
        else {"side_effect": Exception("no network")}
    )

    with (
        patch(_IS_CAME_ENDPOINT, **endpoint_kwargs) as mock_probe,
        patch(_ASYNC_GET_SOURCE_IP, **source_ip_kwargs),
    ):
        result = await flow._async_probe_candidate_hosts()  # noqa: SLF001

    return result, mock_probe


async def test_probe_finds_server(hass):
    """Test _async_probe_candidate_hosts returns host when endpoint is found."""
    result, _ = await _run_probe(hass, endpoint_rv=True)

    assert result in {"192.168.1.3", "192.168.0.3"}


async def test_probe_no_server(hass):
    """Test _async_probe_candidate_hosts returns None when no endpoint found."""
    result, _ = await _run_probe(hass, endpoint_rv=False)
    assert result is None


async def test_probe_adds_subnet_candidate(hass):
    """Test _async_probe_candidate_hosts derives .3 from local IP."""
    _, mock_probe = await _run_probe(hass, endpoint_rv=False, source_ip_rv="10.0.5.100")

    probed_hosts = {call.args[0] for call in mock_probe.call_args_list}
    assert "10.0.5.3" in probed_hosts


async def test_probe_skips_configured_hosts(hass):
    """Test _async_probe_candidate_hosts skips already-configured hosts."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**MOCK_CONFIG, CONF_HOST: "192.168.1.3"},
        entry_id="existing",
    )
    entry.add_to_hass(hass)

    _, mock_probe = await _run_probe(hass, endpoint_rv=False)

    probed_hosts = {call.args[0] for call in mock_probe.call_args_list}
    assert "192.168.1.3" not in probed_hosts


async def test_probe_all_configured_returns_none(hass):
    """Test _async_probe_candidate_hosts returns None when all candidates configured."""
    for host in ("192.168.1.3", "192.168.0.3"):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={**MOCK_CONFIG, CONF_HOST: host},
            entry_id=f"entry_{host}",
        )
        entry.add_to_hass(hass)

    result, mock_probe = await _run_probe(hass)

    assert result is None
    mock_probe.assert_not_called()


async def test_probe_exception_handled(hass):
    """Test _async_probe_candidate_hosts handles probe exceptions gracefully."""
    result, _ = await _run_probe(hass, endpoint_side_effect=ConnectionError("timeout"))
    assert result is None
