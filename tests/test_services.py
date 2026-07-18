"""Tests for CAME Domotic service actions."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic.api import (
    CameDomoticApiClientAuthenticationError,
    CameDomoticApiClientCommunicationError,
)
from custom_components.came_domotic.const import DOMAIN
from custom_components.came_domotic.services import (
    ATTR_CURRENT_PASSWORD,
    ATTR_GROUP,
    ATTR_NAME,
    ATTR_NEW_NAME,
    ATTR_NEW_PASSWORD,
    ATTR_PASSWORD,
    ATTR_USERNAME,
    SERVICE_CHANGE_PASSWORD,
    SERVICE_CREATE_USER,
    SERVICE_DELETE_SCENARIO,
    SERVICE_DELETE_USER,
    SERVICE_FORCE_REFRESH,
    SERVICE_GET_SERVER_DATETIME,
    SERVICE_GET_TERMINAL_GROUPS,
    SERVICE_GET_USERS,
    SERVICE_RENAME_SCENARIO,
    SERVICE_RESET_ENERGY_COUNTERS,
    SERVICE_START_SCENARIO_RECORDING,
    SERVICE_STOP_SCENARIO_RECORDING,
)

from .const import MOCK_CONFIG

_API_CLIENT = "custom_components.came_domotic.api.CameDomoticApiClient"


def _mock_user(name: str) -> MagicMock:
    """Create a mock User object."""
    user = MagicMock()
    user.name = name
    user.async_delete = AsyncMock()
    user.async_change_password = AsyncMock()
    return user


def _mock_terminal_group(group_id: int, name: str) -> MagicMock:
    """Create a mock TerminalGroup object."""
    group = MagicMock()
    group.id = group_id
    group.name = name
    return group


def _mock_scenario(scenario_id: int, name: str, user_defined: int = 1) -> MagicMock:
    """Create a mock Scenario object."""
    scenario = MagicMock()
    scenario.id = scenario_id
    scenario.name = name
    scenario.user_defined = user_defined
    return scenario


async def _setup_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up a config entry for service tests."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    return config_entry


# --- create_user ---


async def test_create_user_success(hass, bypass_get_data):
    """Test successful user creation via service."""
    config_entry = await _setup_entry(hass)
    mock_user = _mock_user("newuser")
    mock_groups = [_mock_terminal_group(1, "ETI/Domo")]

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_terminal_groups",
            return_value=mock_groups,
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_add_user",
            return_value=mock_user,
        ) as mock_add,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_USER,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "newuser",
                ATTR_PASSWORD: "newpass",
                ATTR_GROUP: "ETI/Domo",
            },
            blocking=True,
        )

    mock_add.assert_awaited_once_with("newuser", "newpass", group="ETI/Domo")


async def test_create_user_default_group(hass, bypass_get_data):
    """Test user creation with default group."""
    config_entry = await _setup_entry(hass)
    mock_user = _mock_user("newuser")

    with patch.object(
        config_entry.runtime_data.client,
        "async_add_user",
        return_value=mock_user,
    ) as mock_add:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_USER,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "newuser",
                ATTR_PASSWORD: "newpass",
            },
            blocking=True,
        )

    mock_add.assert_awaited_once_with("newuser", "newpass", group="*")


async def test_create_user_entry_not_found(hass, bypass_get_data):
    """Test create_user raises ServiceValidationError for unknown entry."""
    await _setup_entry(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_USER,
            {
                "config_entry_id": "nonexistent",
                ATTR_USERNAME: "newuser",
                ATTR_PASSWORD: "newpass",
            },
            blocking=True,
        )


async def test_create_user_entry_not_loaded(hass, bypass_get_data):
    """Test create_user raises ServiceValidationError for unloaded entry."""
    # Set up two entries so unloading one doesn't remove services
    config_entry_1 = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test1", unique_id="server1"
    )
    config_entry_1.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry_1.entry_id)
    await hass.async_block_till_done()

    config_entry_2 = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test2", unique_id="server2"
    )
    config_entry_2.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_2.entry_id)
    await hass.async_block_till_done()

    # Unload entry 1 but keep entry 2 loaded (services remain)
    await hass.config_entries.async_unload(config_entry_1.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_USER,
            {
                "config_entry_id": "test1",
                ATTR_USERNAME: "newuser",
                ATTR_PASSWORD: "newpass",
            },
            blocking=True,
        )


async def test_create_user_auth_error(hass, bypass_get_data):
    """Test create_user raises HomeAssistantError on auth failure."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_add_user",
            side_effect=CameDomoticApiClientAuthenticationError("bad creds"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_USER,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "newuser",
                ATTR_PASSWORD: "newpass",
            },
            blocking=True,
        )


async def test_create_user_comm_error(hass, bypass_get_data):
    """Test create_user raises HomeAssistantError on communication failure."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_add_user",
            side_effect=CameDomoticApiClientCommunicationError("timeout"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_USER,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "newuser",
                ATTR_PASSWORD: "newpass",
            },
            blocking=True,
        )


async def test_create_user_group_not_found(hass, bypass_get_data):
    """Test create_user raises ServiceValidationError when group not found."""
    config_entry = await _setup_entry(hass)
    mock_groups = [_mock_terminal_group(1, "ETI/Domo")]

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_terminal_groups",
            return_value=mock_groups,
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_USER,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "newuser",
                ATTR_PASSWORD: "newpass",
                ATTR_GROUP: "NonExistentGroup",
            },
            blocking=True,
        )


async def test_create_user_auth_error_on_get_groups(hass, bypass_get_data):
    """Test create_user raises HomeAssistantError on auth error during group lookup."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_terminal_groups",
            side_effect=CameDomoticApiClientAuthenticationError("bad creds"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_USER,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "newuser",
                ATTR_PASSWORD: "newpass",
                ATTR_GROUP: "ETI/Domo",
            },
            blocking=True,
        )


async def test_create_user_comm_error_on_get_groups(hass, bypass_get_data):
    """Test create_user raises HomeAssistantError on comm error during group lookup."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_terminal_groups",
            side_effect=CameDomoticApiClientCommunicationError("timeout"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_USER,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "newuser",
                ATTR_PASSWORD: "newpass",
                ATTR_GROUP: "ETI/Domo",
            },
            blocking=True,
        )


# --- delete_user ---


async def test_delete_user_success(hass, bypass_get_data):
    """Test successful user deletion via service."""
    config_entry = await _setup_entry(hass)
    mock_users = [_mock_user("admin"), _mock_user("olduser")]

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            return_value=mock_users,
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_delete_user",
        ) as mock_delete,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_USER,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "olduser",
            },
            blocking=True,
        )

    mock_delete.assert_awaited_once_with(mock_users[1])


async def test_delete_user_not_found(hass, bypass_get_data):
    """Test delete_user raises ServiceValidationError when user not found."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            return_value=[_mock_user("admin")],
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_USER,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "nonexistent",
            },
            blocking=True,
        )


async def test_delete_user_cannot_delete_current(hass, bypass_get_data):
    """Test delete_user raises ServiceValidationError for current user."""
    config_entry = await _setup_entry(hass)
    mock_users = [_mock_user("test_username")]

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            return_value=mock_users,
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_delete_user",
            side_effect=ValueError("Cannot delete current user"),
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_USER,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "test_username",
            },
            blocking=True,
        )


async def test_delete_user_entry_not_found(hass, bypass_get_data):
    """Test delete_user raises ServiceValidationError for unknown entry."""
    await _setup_entry(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_USER,
            {
                "config_entry_id": "nonexistent",
                ATTR_USERNAME: "olduser",
            },
            blocking=True,
        )


async def test_delete_user_auth_error_on_get_users(hass, bypass_get_data):
    """Test delete_user raises HomeAssistantError on auth error during user lookup."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            side_effect=CameDomoticApiClientAuthenticationError("bad creds"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_USER,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "olduser",
            },
            blocking=True,
        )


async def test_delete_user_comm_error_on_get_users(hass, bypass_get_data):
    """Test delete_user raises HomeAssistantError on comm error during user lookup."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            side_effect=CameDomoticApiClientCommunicationError("timeout"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_USER,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "olduser",
            },
            blocking=True,
        )


async def test_delete_user_auth_error_on_delete(hass, bypass_get_data):
    """Test delete_user raises HomeAssistantError on auth error during deletion."""
    config_entry = await _setup_entry(hass)
    mock_users = [_mock_user("olduser")]

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            return_value=mock_users,
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_delete_user",
            side_effect=CameDomoticApiClientAuthenticationError("bad creds"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_USER,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "olduser",
            },
            blocking=True,
        )


async def test_delete_user_comm_error_on_delete(hass, bypass_get_data):
    """Test delete_user raises HomeAssistantError on comm error during deletion."""
    config_entry = await _setup_entry(hass)
    mock_users = [_mock_user("olduser")]

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            return_value=mock_users,
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_delete_user",
            side_effect=CameDomoticApiClientCommunicationError("timeout"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_USER,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "olduser",
            },
            blocking=True,
        )


# --- change_password ---


async def test_change_password_success(hass, bypass_get_data):
    """Test successful password change for a non-authenticated user."""
    config_entry = await _setup_entry(hass)
    mock_users = [_mock_user("otheruser")]

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            return_value=mock_users,
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_change_user_password",
        ) as mock_change,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CHANGE_PASSWORD,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "otheruser",
                ATTR_CURRENT_PASSWORD: "oldpass",
                ATTR_NEW_PASSWORD: "newpass",
            },
            blocking=True,
        )

    mock_change.assert_awaited_once_with(mock_users[0], "oldpass", "newpass")
    # Config entry password should NOT be updated for non-authenticated user
    assert config_entry.data[CONF_PASSWORD] == "test_password"


async def test_change_password_authenticated_user_updates_entry(hass, bypass_get_data):
    """Test changing authenticated user's password updates config entry."""
    config_entry = await _setup_entry(hass)
    # The authenticated user is "test_username" (from MOCK_CONFIG)
    mock_users = [_mock_user("test_username")]

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            return_value=mock_users,
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_change_user_password",
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CHANGE_PASSWORD,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "test_username",
                ATTR_CURRENT_PASSWORD: "test_password",
                ATTR_NEW_PASSWORD: "brand_new_pass",
            },
            blocking=True,
        )

    # Config entry password should be updated
    assert config_entry.data[CONF_PASSWORD] == "brand_new_pass"
    assert config_entry.data[CONF_USERNAME] == "test_username"


async def test_change_password_user_not_found(hass, bypass_get_data):
    """Test change_password raises ServiceValidationError when user not found."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            return_value=[_mock_user("admin")],
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CHANGE_PASSWORD,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "nonexistent",
                ATTR_CURRENT_PASSWORD: "oldpass",
                ATTR_NEW_PASSWORD: "newpass",
            },
            blocking=True,
        )


async def test_change_password_entry_not_found(hass, bypass_get_data):
    """Test change_password raises ServiceValidationError for unknown entry."""
    await _setup_entry(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CHANGE_PASSWORD,
            {
                "config_entry_id": "nonexistent",
                ATTR_USERNAME: "user",
                ATTR_CURRENT_PASSWORD: "oldpass",
                ATTR_NEW_PASSWORD: "newpass",
            },
            blocking=True,
        )


async def test_change_password_auth_error_on_get_users(hass, bypass_get_data):
    """Test change_password raises HomeAssistantError on auth error during lookup."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            side_effect=CameDomoticApiClientAuthenticationError("bad creds"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CHANGE_PASSWORD,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "user",
                ATTR_CURRENT_PASSWORD: "oldpass",
                ATTR_NEW_PASSWORD: "newpass",
            },
            blocking=True,
        )


async def test_change_password_comm_error_on_get_users(hass, bypass_get_data):
    """Test change_password raises HomeAssistantError on comm error during lookup."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            side_effect=CameDomoticApiClientCommunicationError("timeout"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CHANGE_PASSWORD,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "user",
                ATTR_CURRENT_PASSWORD: "oldpass",
                ATTR_NEW_PASSWORD: "newpass",
            },
            blocking=True,
        )


async def test_change_password_auth_error_on_change(hass, bypass_get_data):
    """Test change_password raises HomeAssistantError on auth error during change."""
    config_entry = await _setup_entry(hass)
    mock_users = [_mock_user("testuser")]

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            return_value=mock_users,
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_change_user_password",
            side_effect=CameDomoticApiClientAuthenticationError("bad creds"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CHANGE_PASSWORD,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "testuser",
                ATTR_CURRENT_PASSWORD: "oldpass",
                ATTR_NEW_PASSWORD: "newpass",
            },
            blocking=True,
        )


async def test_change_password_comm_error_on_change(hass, bypass_get_data):
    """Test change_password raises HomeAssistantError on comm error during change."""
    config_entry = await _setup_entry(hass)
    mock_users = [_mock_user("testuser")]

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            return_value=mock_users,
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_change_user_password",
            side_effect=CameDomoticApiClientCommunicationError("timeout"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CHANGE_PASSWORD,
            {
                "config_entry_id": "test",
                ATTR_USERNAME: "testuser",
                ATTR_CURRENT_PASSWORD: "oldpass",
                ATTR_NEW_PASSWORD: "newpass",
            },
            blocking=True,
        )


# --- get_terminal_groups ---


async def test_get_terminal_groups_success(hass, bypass_get_data):
    """Test successful terminal groups retrieval."""
    config_entry = await _setup_entry(hass)
    mock_groups = [
        _mock_terminal_group(1, "ETI/Domo"),
        _mock_terminal_group(2, "Admin"),
    ]

    with patch.object(
        config_entry.runtime_data.client,
        "async_get_terminal_groups",
        return_value=mock_groups,
    ):
        result = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_TERMINAL_GROUPS,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )

    assert result == {
        "terminal_groups": [
            {"id": 1, "name": "ETI/Domo"},
            {"id": 2, "name": "Admin"},
        ]
    }


async def test_get_terminal_groups_empty(hass, bypass_get_data):
    """Test terminal groups retrieval returns empty list."""
    config_entry = await _setup_entry(hass)

    with patch.object(
        config_entry.runtime_data.client,
        "async_get_terminal_groups",
        return_value=[],
    ):
        result = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_TERMINAL_GROUPS,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )

    assert result == {"terminal_groups": []}


async def test_get_terminal_groups_entry_not_found(hass, bypass_get_data):
    """Test get_terminal_groups raises ServiceValidationError for unknown entry."""
    await _setup_entry(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_TERMINAL_GROUPS,
            {"config_entry_id": "nonexistent"},
            blocking=True,
            return_response=True,
        )


async def test_get_terminal_groups_auth_error(hass, bypass_get_data):
    """Test get_terminal_groups raises HomeAssistantError on auth failure."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_terminal_groups",
            side_effect=CameDomoticApiClientAuthenticationError("bad creds"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_TERMINAL_GROUPS,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )


async def test_get_terminal_groups_comm_error(hass, bypass_get_data):
    """Test get_terminal_groups raises HomeAssistantError on communication failure."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_terminal_groups",
            side_effect=CameDomoticApiClientCommunicationError("timeout"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_TERMINAL_GROUPS,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )


# --- get_users ---


async def test_get_users_success(hass, bypass_get_data):
    """Test successful users retrieval."""
    config_entry = await _setup_entry(hass)
    mock_users = [_mock_user("admin"), _mock_user("guest")]

    with patch.object(
        config_entry.runtime_data.client,
        "async_get_users",
        return_value=mock_users,
    ):
        result = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_USERS,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )

    assert result == {
        "users": [
            {"name": "admin"},
            {"name": "guest"},
        ]
    }


async def test_get_users_empty(hass, bypass_get_data):
    """Test users retrieval returns empty list."""
    config_entry = await _setup_entry(hass)

    with patch.object(
        config_entry.runtime_data.client,
        "async_get_users",
        return_value=[],
    ):
        result = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_USERS,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )

    assert result == {"users": []}


async def test_get_users_entry_not_found(hass, bypass_get_data):
    """Test get_users raises ServiceValidationError for unknown entry."""
    await _setup_entry(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_USERS,
            {"config_entry_id": "nonexistent"},
            blocking=True,
            return_response=True,
        )


async def test_get_users_auth_error(hass, bypass_get_data):
    """Test get_users raises HomeAssistantError on auth failure."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            side_effect=CameDomoticApiClientAuthenticationError("bad creds"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_USERS,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )


async def test_get_users_comm_error(hass, bypass_get_data):
    """Test get_users raises HomeAssistantError on communication failure."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_users",
            side_effect=CameDomoticApiClientCommunicationError("timeout"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_USERS,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )


# --- force_refresh ---


async def test_force_refresh_success(hass, bypass_get_data):
    """Test successful force refresh via service."""
    config_entry = await _setup_entry(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_FORCE_REFRESH,
        {"config_entry_id": "test"},
        blocking=True,
    )

    # No error means refresh succeeded; bypass_get_data mocks all API calls
    assert config_entry.state is ConfigEntryState.LOADED


async def test_force_refresh_entry_not_found(hass, bypass_get_data):
    """Test force_refresh raises ServiceValidationError for unknown entry."""
    await _setup_entry(hass)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_FORCE_REFRESH,
            {"config_entry_id": "nonexistent"},
            blocking=True,
        )


async def test_force_refresh_entry_not_loaded(hass, bypass_get_data):
    """Test force_refresh raises ServiceValidationError for unloaded entry."""
    # Set up two entries so unloading one doesn't remove services
    config_entry_1 = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test1", unique_id="server1"
    )
    config_entry_1.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry_1.entry_id)
    await hass.async_block_till_done()

    config_entry_2 = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test2", unique_id="server2"
    )
    config_entry_2.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry_2.entry_id)
    await hass.async_block_till_done()

    # Unload entry 1 but keep entry 2 loaded (services remain)
    await hass.config_entries.async_unload(config_entry_1.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_FORCE_REFRESH,
            {"config_entry_id": "test1"},
            blocking=True,
        )


async def test_force_refresh_auth_error(hass, bypass_get_data):
    """Test force_refresh raises HomeAssistantError on auth failure."""
    config_entry = await _setup_entry(hass)
    coordinator = config_entry.runtime_data.coordinator

    async def _fake_refresh():
        coordinator.last_update_success = False
        coordinator.last_exception = CameDomoticApiClientAuthenticationError(
            "bad creds"
        )

    with (
        patch.object(coordinator, "async_refresh", side_effect=_fake_refresh),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_FORCE_REFRESH,
            {"config_entry_id": "test"},
            blocking=True,
        )


async def test_force_refresh_comm_error(hass, bypass_get_data):
    """Test force_refresh raises HomeAssistantError on communication failure."""
    config_entry = await _setup_entry(hass)
    coordinator = config_entry.runtime_data.coordinator

    async def _fake_refresh():
        coordinator.last_update_success = False
        coordinator.last_exception = CameDomoticApiClientCommunicationError("timeout")

    with (
        patch.object(coordinator, "async_refresh", side_effect=_fake_refresh),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_FORCE_REFRESH,
            {"config_entry_id": "test"},
            blocking=True,
        )


# --- start_scenario_recording ---


async def test_start_scenario_recording_success(hass, bypass_get_data):
    """Test successful start of scenario recording via service."""
    config_entry = await _setup_entry(hass)

    with patch.object(
        config_entry.runtime_data.client,
        "async_start_scenario_recording",
    ) as mock_start:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_SCENARIO_RECORDING,
            {"config_entry_id": "test", ATTR_NAME: "Movie night"},
            blocking=True,
        )

    mock_start.assert_awaited_once_with("Movie night")


async def test_start_scenario_recording_invalid_name(hass, bypass_get_data):
    """Test start_scenario_recording raises ServiceValidationError on bad name."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_start_scenario_recording",
            side_effect=ValueError("name must be a non-empty string"),
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_SCENARIO_RECORDING,
            {"config_entry_id": "test", ATTR_NAME: "   "},
            blocking=True,
        )


async def test_start_scenario_recording_auth_error(hass, bypass_get_data):
    """Test start_scenario_recording raises HomeAssistantError on auth failure."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_start_scenario_recording",
            side_effect=CameDomoticApiClientAuthenticationError("bad creds"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_SCENARIO_RECORDING,
            {"config_entry_id": "test", ATTR_NAME: "Movie night"},
            blocking=True,
        )


async def test_start_scenario_recording_comm_error(hass, bypass_get_data):
    """Test start_scenario_recording raises HomeAssistantError on comm failure."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_start_scenario_recording",
            side_effect=CameDomoticApiClientCommunicationError("timeout"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_SCENARIO_RECORDING,
            {"config_entry_id": "test", ATTR_NAME: "Movie night"},
            blocking=True,
        )


# --- stop_scenario_recording ---


async def test_stop_scenario_recording_success_with_response(hass, bypass_get_data):
    """Test stop_scenario_recording returns the new scenario and reloads the entry."""
    config_entry = await _setup_entry(hass)
    new_scenario = _mock_scenario(42, "Movie night")

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_stop_scenario_recording",
            return_value=new_scenario,
        ) as mock_stop,
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_SCENARIO_RECORDING,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )

    mock_stop.assert_awaited_once()
    mock_reload.assert_called_once_with("test")
    assert response == {"scenario": {"id": 42, "name": "Movie night"}}


async def test_stop_scenario_recording_unidentified_scenario(hass, bypass_get_data):
    """Test stop_scenario_recording response when the scenario is unidentifiable."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_stop_scenario_recording",
            return_value=None,
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_SCENARIO_RECORDING,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )

    mock_reload.assert_called_once_with("test")
    assert response == {"scenario": None}


async def test_stop_scenario_recording_no_response(hass, bypass_get_data):
    """Test stop_scenario_recording without requesting a response."""
    config_entry = await _setup_entry(hass)
    new_scenario = _mock_scenario(42, "Movie night")

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_stop_scenario_recording",
            return_value=new_scenario,
        ) as mock_stop,
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_SCENARIO_RECORDING,
            {"config_entry_id": "test"},
            blocking=True,
        )

    mock_stop.assert_awaited_once()
    mock_reload.assert_called_once_with("test")


async def test_stop_scenario_recording_auth_error(hass, bypass_get_data):
    """Test stop_scenario_recording raises HomeAssistantError on auth failure."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_stop_scenario_recording",
            side_effect=CameDomoticApiClientAuthenticationError("bad creds"),
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_SCENARIO_RECORDING,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )

    mock_reload.assert_not_called()


async def test_stop_scenario_recording_comm_error(hass, bypass_get_data):
    """Test stop_scenario_recording raises HomeAssistantError on comm failure."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_stop_scenario_recording",
            side_effect=CameDomoticApiClientCommunicationError("timeout"),
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_STOP_SCENARIO_RECORDING,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )

    mock_reload.assert_not_called()


# --- rename_scenario ---


async def test_rename_scenario_success(hass, bypass_get_data):
    """Test successful scenario rename via service."""
    config_entry = await _setup_entry(hass)
    scenario = _mock_scenario(42, "Movie night")

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_scenarios",
            return_value=[scenario],
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_rename_scenario",
        ) as mock_rename,
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RENAME_SCENARIO,
            {
                "config_entry_id": "test",
                ATTR_NAME: "Movie night",
                ATTR_NEW_NAME: "Cinema mode",
            },
            blocking=True,
        )

    mock_rename.assert_awaited_once_with(scenario, "Cinema mode")
    mock_reload.assert_called_once_with("test")


async def test_rename_scenario_picks_highest_id_on_duplicates(hass, bypass_get_data):
    """Test rename_scenario picks the highest id when names are duplicated."""
    config_entry = await _setup_entry(hass)
    older = _mock_scenario(10, "Movie night")
    newer = _mock_scenario(42, "Movie night")

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_scenarios",
            return_value=[newer, older],
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_rename_scenario",
        ) as mock_rename,
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RENAME_SCENARIO,
            {
                "config_entry_id": "test",
                ATTR_NAME: "Movie night",
                ATTR_NEW_NAME: "Cinema mode",
            },
            blocking=True,
        )

    mock_rename.assert_awaited_once_with(newer, "Cinema mode")


async def test_rename_scenario_not_found(hass, bypass_get_data):
    """Test rename_scenario raises ServiceValidationError for unknown scenario."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_scenarios",
            return_value=[],
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RENAME_SCENARIO,
            {
                "config_entry_id": "test",
                ATTR_NAME: "Ghost",
                ATTR_NEW_NAME: "Cinema mode",
            },
            blocking=True,
        )


async def test_rename_scenario_system_defined(hass, bypass_get_data):
    """Test rename_scenario raises ServiceValidationError for system scenarios."""
    config_entry = await _setup_entry(hass)
    scenario = _mock_scenario(1, "Alarm", user_defined=0)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_scenarios",
            return_value=[scenario],
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RENAME_SCENARIO,
            {
                "config_entry_id": "test",
                ATTR_NAME: "Alarm",
                ATTR_NEW_NAME: "New alarm",
            },
            blocking=True,
        )


async def test_rename_scenario_auth_error_on_get_scenarios(hass, bypass_get_data):
    """Test rename_scenario raises HomeAssistantError on auth failure during lookup."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_scenarios",
            side_effect=CameDomoticApiClientAuthenticationError("bad creds"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RENAME_SCENARIO,
            {
                "config_entry_id": "test",
                ATTR_NAME: "Movie night",
                ATTR_NEW_NAME: "Cinema mode",
            },
            blocking=True,
        )


async def test_rename_scenario_comm_error_on_get_scenarios(hass, bypass_get_data):
    """Test rename_scenario raises HomeAssistantError on comm failure during lookup."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_scenarios",
            side_effect=CameDomoticApiClientCommunicationError("timeout"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RENAME_SCENARIO,
            {
                "config_entry_id": "test",
                ATTR_NAME: "Movie night",
                ATTR_NEW_NAME: "Cinema mode",
            },
            blocking=True,
        )


async def test_rename_scenario_invalid_new_name(hass, bypass_get_data):
    """Test rename_scenario raises ServiceValidationError on bad new name."""
    config_entry = await _setup_entry(hass)
    scenario = _mock_scenario(42, "Movie night")

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_scenarios",
            return_value=[scenario],
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_rename_scenario",
            side_effect=ValueError("name must be a non-empty string"),
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RENAME_SCENARIO,
            {
                "config_entry_id": "test",
                ATTR_NAME: "Movie night",
                ATTR_NEW_NAME: "   ",
            },
            blocking=True,
        )

    mock_reload.assert_not_called()


async def test_rename_scenario_auth_error_on_rename(hass, bypass_get_data):
    """Test rename_scenario raises HomeAssistantError on auth failure during rename."""
    config_entry = await _setup_entry(hass)
    scenario = _mock_scenario(42, "Movie night")

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_scenarios",
            return_value=[scenario],
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_rename_scenario",
            side_effect=CameDomoticApiClientAuthenticationError("bad creds"),
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RENAME_SCENARIO,
            {
                "config_entry_id": "test",
                ATTR_NAME: "Movie night",
                ATTR_NEW_NAME: "Cinema mode",
            },
            blocking=True,
        )

    mock_reload.assert_not_called()


async def test_rename_scenario_comm_error_on_rename(hass, bypass_get_data):
    """Test rename_scenario raises HomeAssistantError on comm failure during rename."""
    config_entry = await _setup_entry(hass)
    scenario = _mock_scenario(42, "Movie night")

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_scenarios",
            return_value=[scenario],
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_rename_scenario",
            side_effect=CameDomoticApiClientCommunicationError("timeout"),
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RENAME_SCENARIO,
            {
                "config_entry_id": "test",
                ATTR_NAME: "Movie night",
                ATTR_NEW_NAME: "Cinema mode",
            },
            blocking=True,
        )

    mock_reload.assert_not_called()


# --- delete_scenario ---


async def test_delete_scenario_success(hass, bypass_get_data):
    """Test successful scenario deletion via service."""
    config_entry = await _setup_entry(hass)
    scenario = _mock_scenario(42, "Movie night")

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_scenarios",
            return_value=[scenario],
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_delete_scenario",
        ) as mock_delete,
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_SCENARIO,
            {"config_entry_id": "test", ATTR_NAME: "Movie night"},
            blocking=True,
        )

    mock_delete.assert_awaited_once_with(scenario)
    mock_reload.assert_called_once_with("test")


async def test_delete_scenario_not_found(hass, bypass_get_data):
    """Test delete_scenario raises ServiceValidationError for unknown scenario."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_scenarios",
            return_value=[],
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_SCENARIO,
            {"config_entry_id": "test", ATTR_NAME: "Ghost"},
            blocking=True,
        )


async def test_delete_scenario_system_defined(hass, bypass_get_data):
    """Test delete_scenario raises ServiceValidationError for system scenarios."""
    config_entry = await _setup_entry(hass)
    scenario = _mock_scenario(1, "Alarm", user_defined=0)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_scenarios",
            return_value=[scenario],
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_SCENARIO,
            {"config_entry_id": "test", ATTR_NAME: "Alarm"},
            blocking=True,
        )


async def test_delete_scenario_auth_error_on_delete(hass, bypass_get_data):
    """Test delete_scenario raises HomeAssistantError on auth failure."""
    config_entry = await _setup_entry(hass)
    scenario = _mock_scenario(42, "Movie night")

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_scenarios",
            return_value=[scenario],
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_delete_scenario",
            side_effect=CameDomoticApiClientAuthenticationError("bad creds"),
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_SCENARIO,
            {"config_entry_id": "test", ATTR_NAME: "Movie night"},
            blocking=True,
        )

    mock_reload.assert_not_called()


async def test_delete_scenario_comm_error_on_delete(hass, bypass_get_data):
    """Test delete_scenario raises HomeAssistantError on comm failure."""
    config_entry = await _setup_entry(hass)
    scenario = _mock_scenario(42, "Movie night")

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_scenarios",
            return_value=[scenario],
        ),
        patch.object(
            config_entry.runtime_data.client,
            "async_delete_scenario",
            side_effect=CameDomoticApiClientCommunicationError("timeout"),
        ),
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DELETE_SCENARIO,
            {"config_entry_id": "test", ATTR_NAME: "Movie night"},
            blocking=True,
        )

    mock_reload.assert_not_called()


# --- reset_energy_counters ---


async def test_reset_energy_counters_success(hass, bypass_get_data):
    """Test successful energy counters reset via service."""
    config_entry = await _setup_entry(hass)

    with patch.object(
        config_entry.runtime_data.client,
        "async_reset_energy_counters",
    ) as mock_reset:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_ENERGY_COUNTERS,
            {"config_entry_id": "test"},
            blocking=True,
        )

    mock_reset.assert_awaited_once()


async def test_reset_energy_counters_auth_error(hass, bypass_get_data):
    """Test reset_energy_counters raises HomeAssistantError on auth failure."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_reset_energy_counters",
            side_effect=CameDomoticApiClientAuthenticationError("bad creds"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_ENERGY_COUNTERS,
            {"config_entry_id": "test"},
            blocking=True,
        )


async def test_reset_energy_counters_comm_error(hass, bypass_get_data):
    """Test reset_energy_counters raises HomeAssistantError on comm failure."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_reset_energy_counters",
            side_effect=CameDomoticApiClientCommunicationError("timeout"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET_ENERGY_COUNTERS,
            {"config_entry_id": "test"},
            blocking=True,
        )


# --- get_server_datetime ---


async def test_get_server_datetime_success(hass, bypass_get_data):
    """Test successful server datetime retrieval via service."""
    config_entry = await _setup_entry(hass)
    server_datetime = MagicMock()
    server_datetime.datetime_string = "2026-07-18 12:34:56"
    server_datetime.epoch = 1784378096
    server_datetime.utc_datetime = datetime(2026, 7, 18, 10, 34, 56, tzinfo=UTC)
    server_datetime.timezone_name = "Europe/Rome"
    server_datetime.daylight_saving_time = True

    with patch.object(
        config_entry.runtime_data.client,
        "async_get_server_datetime",
        return_value=server_datetime,
    ):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SERVER_DATETIME,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )

    assert response == {
        "datetime": "2026-07-18 12:34:56",
        "epoch": 1784378096,
        "utc_datetime": "2026-07-18T10:34:56+00:00",
        "timezone": "Europe/Rome",
        "daylight_saving_time": True,
    }


async def test_get_server_datetime_missing_epoch(hass, bypass_get_data):
    """Test server datetime response when the server reports no epoch."""
    config_entry = await _setup_entry(hass)
    server_datetime = MagicMock()
    server_datetime.datetime_string = "2026-07-18 12:34:56"
    server_datetime.epoch = None
    server_datetime.utc_datetime = None
    server_datetime.timezone_name = "Europe/Rome"
    server_datetime.daylight_saving_time = False

    with patch.object(
        config_entry.runtime_data.client,
        "async_get_server_datetime",
        return_value=server_datetime,
    ):
        response = await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SERVER_DATETIME,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )

    assert response == {
        "datetime": "2026-07-18 12:34:56",
        "epoch": None,
        "utc_datetime": None,
        "timezone": "Europe/Rome",
        "daylight_saving_time": False,
    }


async def test_get_server_datetime_auth_error(hass, bypass_get_data):
    """Test get_server_datetime raises HomeAssistantError on auth failure."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_server_datetime",
            side_effect=CameDomoticApiClientAuthenticationError("bad creds"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SERVER_DATETIME,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )


async def test_get_server_datetime_comm_error(hass, bypass_get_data):
    """Test get_server_datetime raises HomeAssistantError on comm failure."""
    config_entry = await _setup_entry(hass)

    with (
        patch.object(
            config_entry.runtime_data.client,
            "async_get_server_datetime",
            side_effect=CameDomoticApiClientCommunicationError("timeout"),
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_GET_SERVER_DATETIME,
            {"config_entry_id": "test"},
            blocking=True,
            return_response=True,
        )


# --- Service registration lifecycle ---


async def test_services_registered_after_setup(hass, bypass_get_data):
    """Test that services are registered after integration setup."""
    await _setup_entry(hass)

    assert hass.services.has_service(DOMAIN, SERVICE_CREATE_USER)
    assert hass.services.has_service(DOMAIN, SERVICE_DELETE_USER)
    assert hass.services.has_service(DOMAIN, SERVICE_CHANGE_PASSWORD)
    assert hass.services.has_service(DOMAIN, SERVICE_GET_TERMINAL_GROUPS)
    assert hass.services.has_service(DOMAIN, SERVICE_GET_USERS)
    assert hass.services.has_service(DOMAIN, SERVICE_FORCE_REFRESH)
    assert hass.services.has_service(DOMAIN, SERVICE_START_SCENARIO_RECORDING)
    assert hass.services.has_service(DOMAIN, SERVICE_STOP_SCENARIO_RECORDING)
    assert hass.services.has_service(DOMAIN, SERVICE_RENAME_SCENARIO)
    assert hass.services.has_service(DOMAIN, SERVICE_DELETE_SCENARIO)
    assert hass.services.has_service(DOMAIN, SERVICE_RESET_ENERGY_COUNTERS)
    assert hass.services.has_service(DOMAIN, SERVICE_GET_SERVER_DATETIME)


async def test_services_removed_after_last_entry_unloaded(hass, bypass_get_data):
    """Test that services are removed when the last entry is unloaded."""
    config_entry = await _setup_entry(hass)

    # Services should exist
    assert hass.services.has_service(DOMAIN, SERVICE_CREATE_USER)

    await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    # Services should be removed
    assert not hass.services.has_service(DOMAIN, SERVICE_CREATE_USER)
    assert not hass.services.has_service(DOMAIN, SERVICE_DELETE_USER)
    assert not hass.services.has_service(DOMAIN, SERVICE_CHANGE_PASSWORD)
    assert not hass.services.has_service(DOMAIN, SERVICE_GET_TERMINAL_GROUPS)
    assert not hass.services.has_service(DOMAIN, SERVICE_GET_USERS)
    assert not hass.services.has_service(DOMAIN, SERVICE_FORCE_REFRESH)
    assert not hass.services.has_service(DOMAIN, SERVICE_START_SCENARIO_RECORDING)
    assert not hass.services.has_service(DOMAIN, SERVICE_STOP_SCENARIO_RECORDING)
    assert not hass.services.has_service(DOMAIN, SERVICE_RENAME_SCENARIO)
    assert not hass.services.has_service(DOMAIN, SERVICE_DELETE_SCENARIO)
    assert not hass.services.has_service(DOMAIN, SERVICE_RESET_ENERGY_COUNTERS)
    assert not hass.services.has_service(DOMAIN, SERVICE_GET_SERVER_DATETIME)


async def test_services_kept_when_other_entries_loaded(hass, bypass_get_data):
    """Test that services remain when other entries are still loaded."""
    config_entry_1 = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test1", unique_id="server1"
    )
    config_entry_1.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry_1.entry_id)
    await hass.async_block_till_done()

    config_entry_2 = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test2", unique_id="server2"
    )
    config_entry_2.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry_2.entry_id)
    await hass.async_block_till_done()

    # Unload first entry
    await hass.config_entries.async_unload(config_entry_1.entry_id)
    await hass.async_block_till_done()

    # Services should still exist (second entry still loaded)
    assert hass.services.has_service(DOMAIN, SERVICE_CREATE_USER)
    assert hass.services.has_service(DOMAIN, SERVICE_DELETE_USER)
    assert hass.services.has_service(DOMAIN, SERVICE_CHANGE_PASSWORD)
    assert hass.services.has_service(DOMAIN, SERVICE_GET_TERMINAL_GROUPS)
    assert hass.services.has_service(DOMAIN, SERVICE_GET_USERS)
    assert hass.services.has_service(DOMAIN, SERVICE_FORCE_REFRESH)
