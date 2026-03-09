"""Constants for CAME Domotic Unofficial."""

from __future__ import annotations

# Base component constants
NAME = "CAME Domotic Unofficial"
DOMAIN = "came_domotic_unofficial"

ATTRIBUTION = "Data provided by CAME Domotic"
MANUFACTURER = "CAME"

# Icons
ICON = "mdi:home-automation"

# Long-polling defaults
DEFAULT_LONG_POLL_TIMEOUT = 120  # seconds to wait for server-side changes
RECONNECT_DELAY = 5  # seconds to wait before retrying after a connection error
UPDATE_THROTTLE_DELAY = 1  # seconds to wait between long-poll iterations
