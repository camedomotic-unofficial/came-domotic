"""Test CAME Domotic Unofficial config flow."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
)
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic_unofficial.api import (
    CameDomoticUnofficialApiClientAuthenticationError,
    CameDomoticUnofficialApiClientCommunicationError,
    CameDomoticUnofficialApiClientError,
)
from custom_components.came_domotic_unofficial.const import (
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

from .const import MOCK_CONFIG, MOCK_KEYCODE

_API_CLIENT = (
    "custom_components.came_domotic_unofficial.api.CameDomoticUnofficialApiClient"
)

MOCK_USER_INPUT = {**MOCK_CONFIG, CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL}


@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch(
        "custom_components.came_domotic_unofficial.async_setup_entry",
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
        result["flow_id"], user_input=MOCK_USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"CAME Domotic ({MOCK_CONFIG[CONF_HOST]})"
    assert result["data"] == MOCK_CONFIG
    assert result["options"] == {CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL}
    assert result["result"]


async def test_config_flow_cannot_connect(hass):
    """Test config flow with connection error shows cannot_connect."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        f"{_API_CLIENT}.async_connect",
        side_effect=CameDomoticUnofficialApiClientCommunicationError("Timeout"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_INPUT
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
            side_effect=CameDomoticUnofficialApiClientAuthenticationError("Bad creds"),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_INPUT
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
            result["flow_id"], user_input=MOCK_USER_INPUT
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
        result["flow_id"], user_input=MOCK_USER_INPUT
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
            side_effect=CameDomoticUnofficialApiClientError("Parse error"),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_INPUT
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
            side_effect=CameDomoticUnofficialApiClientAuthenticationError("Bad creds"),
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
        side_effect=CameDomoticUnofficialApiClientCommunicationError("Timeout"),
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
    """Test successful reconfigure flow updates credentials and options."""
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
        CONF_SCAN_INTERVAL: 60,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=new_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_HOST] == "192.168.1.200"
    assert entry.data[CONF_USERNAME] == "new_user"
    assert entry.data[CONF_PASSWORD] == "new_pass"
    assert entry.options[CONF_SCAN_INTERVAL] == 60


async def test_reconfigure_flow_cannot_connect(hass):
    """Test reconfigure flow with connection error shows cannot_connect."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, unique_id=MOCK_KEYCODE)
    entry.add_to_hass(hass)
    result = await _init_reconfigure_flow(hass, entry)

    with patch(
        f"{_API_CLIENT}.async_connect",
        side_effect=CameDomoticUnofficialApiClientCommunicationError("Timeout"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_INPUT
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
            side_effect=CameDomoticUnofficialApiClientAuthenticationError("Bad creds"),
        ),
        patch(f"{_API_CLIENT}.async_dispose"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=MOCK_USER_INPUT
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
            result["flow_id"], user_input=MOCK_USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


# --- Options flow ---


async def test_options_flow(hass, bypass_get_data):
    """Test options flow updates scan interval."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SCAN_INTERVAL: 60},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_SCAN_INTERVAL: 60}
