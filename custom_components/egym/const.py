"""Constants for the EGYM integration."""

import datetime

DOMAIN = "egym"

CONF_BASE_URL = "base_url"

# How often EGYM is checked for new data.
SYNC_INTERVAL = datetime.timedelta(hours=6)

# First sync: all history from this date on.
HISTORY_START = datetime.date(2019, 1, 1)

# Later syncs: from the last successful sync minus this margin,
# so late-arriving or edited data is picked up again.
RESYNC_MARGIN = datetime.timedelta(days=3)

STORAGE_VERSION = 1
