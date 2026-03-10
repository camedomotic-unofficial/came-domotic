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

# Session recycling: the CAME server tracks a command sequence (cseq) per
# session. HA sessions can run for weeks/months, causing very high cseq values.
# The server is likely not built for such long-running sessions, so we recycle
# periodically to reset the cseq counter.
SESSION_RECYCLE_THRESHOLD = 900  # recycle API session after this many long-poll calls
