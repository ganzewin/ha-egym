"""Fetches EGYM data, writes history as long-term statistics and keeps current values for sensors."""

import datetime
import logging

import requests

from homeassistant.components.recorder.models import StatisticMeanType
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_NAME, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util, slugify

from .const import CONF_BASE_URL, CONF_ECCENTRIC_FACTOR, CONF_ORDER, DEFAULT_ECCENTRIC_FACTOR, DOMAIN, HISTORY_START, RESYNC_MARGIN, STORAGE_VERSION, STORE_SCHEMA, SYNC_INTERVAL, TRAINING_BAND
from .convert import (
    body_metric_types,
    body_metrics_to_statistics,
    current_values,
    history_values,
    derived_statistics,
    latest_sensors,
    apply_order,
    merge_history,
    parse_order,
    progress_sensors,
    strength_to_statistics,
    workouts_to_statistics,
)
from .egym_api import Api, AuthenticationError, EgymError

_LOGGER = logging.getLogger(__name__)


def fetch_all(email, password, base_url, start, end):
    """All API calls in one login. Runs in the executor."""
    api = Api(email=email, password=password, base_url=base_url or None)
    try:
        types = body_metric_types(api.get_latest_body_metrics())
        return {
            "workouts": api.get_workouts(start, end),
            "strength": api.get_strength_measurements(start, end),
            "body_metrics": api.get_body_metrics(types, start, end) if types else [],
            "bio_age": api.get_bio_age(),
            "activity_level": api.get_activity_level(),
            "muscle_imbalances": api.get_muscle_imbalances(),
        }
    finally:
        try:
            api.logout()
        except (EgymError, requests.RequestException):
            pass


def person_name(entry: ConfigEntry) -> str:
    """Name used in statistic ids, statistic names and the device; defaults to the part of the email before @."""
    return entry.data.get(CONF_NAME) or entry.data[CONF_EMAIL].split("@")[0]


def store_key(entry: ConfigEntry) -> str:
    # v2: statistic ids carry the person's name; a new key forces a full first sync for those ids
    return f"{DOMAIN}.{entry.entry_id}.v2"


class EgymCoordinator(DataUpdateCoordinator):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, _LOGGER, name=DOMAIN, config_entry=entry, update_interval=SYNC_INTERVAL)
        self.store = Store(hass, STORAGE_VERSION, store_key(entry))
        self.last_sync = None
        self.history = {}
        self.eccentric_factor = float(entry.options.get(CONF_ECCENTRIC_FACTOR, DEFAULT_ECCENTRIC_FACTOR))
        self.person = person_name(entry)
        self.prefix = slugify(self.person)

    async def async_load(self) -> None:
        data = await self.store.async_load() or {}
        # A store from an older version syncs everything once, so all sensors get filled
        # and every statistic gets the current names
        # A changed eccentric factor also needs a full sync, to recompute every eccentric session
        if (data.get("last_sync") and data.get("schema") == STORE_SCHEMA
                and data.get("excentrisch_factor") == self.eccentric_factor):
            self.last_sync = datetime.date.fromisoformat(data["last_sync"])
        self.history = data.get("history") or {}

    async def _async_update_data(self):
        today = dt_util.now().date()
        start = max(self.last_sync - RESYNC_MARGIN, HISTORY_START) if self.last_sync else HISTORY_START
        entry = self.config_entry
        try:
            data = await self.hass.async_add_executor_job(
                fetch_all, entry.data[CONF_EMAIL], entry.data[CONF_PASSWORD], entry.data.get(CONF_BASE_URL), start, today
            )
        except AuthenticationError as error:
            raise ConfigEntryError(f"EGYM login refused: {error}") from error
        except (EgymError, requests.RequestException) as error:
            raise UpdateFailed(f"EGYM not reachable: {error}") from error

        statistics = {
            **workouts_to_statistics(data["workouts"], self.eccentric_factor),
            **strength_to_statistics(data["strength"]),
            **body_metrics_to_statistics(data["body_metrics"], self.hass.config.time_zone),
        }
        # Later syncs only see recent days, so the values per measurement are kept in the store
        merge_history(self.history, history_values(statistics))
        # Index and intensity need every strength test since the first one, so they come from the stored history
        statistics.update(derived_statistics(self.history))
        positions = parse_order(entry.options.get(CONF_ORDER, ""))
        sensors = {
            **current_values(data["bio_age"], data["activity_level"], data["muscle_imbalances"]),
            **latest_sensors(self.history, TRAINING_BAND, self.eccentric_factor),
            **progress_sensors(self.history, dt_util.now(), TRAINING_BAND),
        }
        apply_order(sensors, statistics, positions)
        for statistic_id, stat in statistics.items():
            # egym:kracht_1002 -> egym:marcel_kracht_1002, so several people can share one Home Assistant
            statistic_id = statistic_id.replace(f"{DOMAIN}:", f"{DOMAIN}:{self.prefix}_", 1)
            async_add_external_statistics(
                self.hass,
                {
                    "has_sum": False,
                    "mean_type": StatisticMeanType.ARITHMETIC,
                    "name": f"{self.person} {stat['name']}",
                    "source": DOMAIN,
                    "statistic_id": statistic_id,
                    "unit_class": stat["unit_class"],
                    "unit_of_measurement": stat["unit"],
                },
                sorted(stat["rows"].values(), key=lambda row: row["start"]),
            )
        self.last_sync = today
        await self.store.async_save({
            "schema": STORE_SCHEMA, "excentrisch_factor": self.eccentric_factor,
            "last_sync": today.isoformat(), "history": self.history,
        })
        _LOGGER.debug("EGYM sync %s..%s: %d statistics", start, today, len(statistics))
        return sensors
