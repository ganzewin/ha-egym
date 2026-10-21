"""Constants for the EGYM integration."""

import datetime

DOMAIN = "egym"

CONF_BASE_URL = "base_url"
# Order of the machines in the gym, one per line or comma separated; adds a number to their names
CONF_ORDER = "volgorde"
# Eccentric sets: lowering weight = lifting weight x this factor (as shown on the machine)
CONF_ECCENTRIC_FACTOR = "excentrisch_factor"
DEFAULT_ECCENTRIC_FACTOR = 1.55

# How often EGYM is checked for new data.
SYNC_INTERVAL = datetime.timedelta(hours=6)

# First sync: all history from this date on.
HISTORY_START = datetime.date(2019, 1, 1)

# Later syncs: from the last successful sync minus this margin,
# so late-arriving or edited data is picked up again.
RESYNC_MARGIN = datetime.timedelta(days=3)

STORAGE_VERSION = 1

# Bump when stored data or statistic names change; an older store triggers one full sync.
STORE_SCHEMA = 6

# Training weight as % of the strength test (1RM) for EGYM's strength endurance programme:
# 40-65% of 1RM, about 20-30 repetitions per set.
TRAINING_BAND = (40, 65)
