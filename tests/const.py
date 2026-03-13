"""Constants for CAME Domotic tests."""

from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from custom_components.came_domotic.const import CONF_SERVER_INFO

MOCK_CONFIG = {
    CONF_HOST: "192.168.1.100",
    CONF_USERNAME: "test_username",
    CONF_PASSWORD: "test_password",
}

MOCK_KEYCODE = "AA:BB:CC:DD:EE:FF"

MOCK_SERVER_INFO_DICT = {
    "board": "board_v1",
    "type": "ETI/Domo",
    "serial": "0011FFEE",
    "swver": "1.2.3",
}

MOCK_CONFIG_WITH_SERVER_INFO = {
    **MOCK_CONFIG,
    CONF_SERVER_INFO: MOCK_SERVER_INFO_DICT,
}
