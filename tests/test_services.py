"""Tests for CAME Domotic Unofficial service actions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.came_domotic_unofficial.api import (
    CameDomoticUnofficialApiClientAuthenticationError,
    CameDomoticUnofficialApiClientCommunicationError,
)
from custom_components.came_domotic_unofficial.const import DOMAIN
from custom_components.came_domotic_unofficial.services import (
    ATTR_CURRENT_PASSWORD,
    ATTR_GROUP,
    ATTR_NEW_PASSWORD,
    ATTR_PASSWORD,
    ATTR_USERNAME,
    SERVICE_CHANGE_PASSWORD,
    SERVICE_CREATE_USER,
    SERVICE_DELETE_USER,
    SERVICE_GET_TERMINAL_GROUPS,
)

from .const import MOCK_CONFIG

_API_CLIENT = (
    "custom_components.came_domotic_unofficial.api.CameDomoticUnofficialApiClient"
)


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
            side_effect=CameDomoticUnofficialApiClientAuthenticationError("bad creds"),
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
            side_effect=CameDomoticUnofficialApiClientCommunicationError("timeout"),
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
            side_effect=CameDomoticUnofficialApiClientAuthenticationError("bad creds"),
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
            side_effect=CameDomoticUnofficialApiClientCommunicationError("timeout"),
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
            side_effect=CameDomoticUnofficialApiClientAuthenticationError("bad creds"),
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
            side_effect=CameDomoticUnofficialApiClientCommunicationError("timeout"),
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
            side_effect=CameDomoticUnofficialApiClientAuthenticationError("bad creds"),
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
            side_effect=CameDomoticUnofficialApiClientCommunicationError("timeout"),
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
            side_effect=CameDomoticUnofficialApiClientAuthenticationError("bad creds"),
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
            side_effect=CameDomoticUnofficialApiClientCommunicationError("timeout"),
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
            side_effect=CameDomoticUnofficialApiClientAuthenticationError("bad creds"),
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
            side_effect=CameDomoticUnofficialApiClientCommunicationError("timeout"),
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
            side_effect=CameDomoticUnofficialApiClientAuthenticationError("bad creds"),
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
            side_effect=CameDomoticUnofficialApiClientCommunicationError("timeout"),
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


# --- Service registration lifecycle ---


async def test_services_registered_after_setup(hass, bypass_get_data):
    """Test that services are registered after integration setup."""
    await _setup_entry(hass)

    assert hass.services.has_service(DOMAIN, SERVICE_CREATE_USER)
    assert hass.services.has_service(DOMAIN, SERVICE_DELETE_USER)
    assert hass.services.has_service(DOMAIN, SERVICE_CHANGE_PASSWORD)
    assert hass.services.has_service(DOMAIN, SERVICE_GET_TERMINAL_GROUPS)


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
