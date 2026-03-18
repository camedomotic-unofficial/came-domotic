"""Constants for CAME Domotic."""

from __future__ import annotations

from datetime import timedelta
import hashlib

# Base component constants
NAME = "CAME Domotic"
DOMAIN = "came_domotic"

ATTRIBUTION = "Data provided by CAME Domotic"
MANUFACTURER = "CAME"

# Stored server info keys (persisted in config entry data)
CONF_SERVER_INFO = "server_info"
CONF_TOPOLOGY_IMPORTED = "topology_imported"

# Icons
ICON = "mdi:home-automation"

# Long-polling defaults
DEFAULT_LONG_POLL_TIMEOUT = 120  # seconds to wait for server-side changes
RECONNECT_DELAY = 5  # seconds to wait before retrying after a connection error
UPDATE_THROTTLE_DELAY = 1  # seconds to wait between long-poll iterations

# Session recycling: the CAME server tracks a command sequence (cseq) per
# session. HA sessions can run for weeks/months, causing very high cseq values.
# The server is likely not built for such long-running sessions, so we recycle
# periodically to reset the cseq counter.
SESSION_RECYCLE_THRESHOLD = 900  # recycle API session after this many long-poll calls

# Ping coordinator: interval between server connectivity/latency checks.
# A shorter interval is used when the server is unreachable so we recover faster.
PING_UPDATE_INTERVAL: timedelta = timedelta(seconds=60)
PING_UPDATE_INTERVAL_DISCONNECTED: timedelta = timedelta(seconds=10)


def hash_keycode(keycode: str) -> str:
    """Return the SHA-256 hex digest of a server keycode."""
    return hashlib.sha256(keycode.encode()).hexdigest()
