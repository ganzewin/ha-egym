import datetime
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.recorder import get_instance
from homeassistant.components.recorder.statistics import list_statistic_ids, statistics_during_period
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.recorder.common import async_wait_recording_done

from custom_components.egym.egym_api import AuthenticationError, DiscoveryError

from .sample_data import all_data

FETCH = "custom_components.egym.coordinator.fetch_all"


def _entry(name="Marcel", email="marcel@example.com"):
    return MockConfigEntry(
        domain="egym", unique_id=email,
        data={"email": email, "password": "x", "name": name, "base_url": "https://gym.netpulse.com"},
    )


async def _statistics(hass, ids):
    return await get_instance(hass).async_add_executor_job(
        statistics_during_period, hass, datetime.datetime(2026, 9, 1, tzinfo=datetime.UTC), None,
        set(ids), "hour", None, {"mean", "min", "max"},
    )


async def test_setup_imports_statistics_and_sensors(recorder_mock, enable_custom_integrations, hass):
    await hass.config.async_set_time_zone("Europe/Amsterdam")
    entry = _entry()
    entry.add_to_hass(hass)
    calls = []

    def fake(email, password, base_url, start, end):
        calls.append(start)
        return all_data()

    with patch(FETCH, side_effect=fake):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)

        ids = {i["statistic_id"]: i for i in await get_instance(hass).async_add_executor_job(list_statistic_ids, hass)}
        assert "egym:marcel_kracht_1002" in ids
        assert ids["egym:marcel_kracht_1002"]["name"] == "Marcel EGYM Leg Press kracht"
        stats = await _statistics(hass, ["egym:marcel_oefening_581_gewicht", "egym:marcel_lichaam_weight_kg"])
        assert [r["max"] for r in stats["egym:marcel_oefening_581_gewicht"]] == [50.0, 53.0]
        assert [r["max"] for r in stats["egym:marcel_lichaam_weight_kg"]] == [81.0, 80.0]

        assert hass.states.get("sensor.egym_marcel_bio_leeftijd").state == "40"
        assert hass.states.get("sensor.egym_marcel_bio_leeftijd_cardio").state == "unknown"
        assert hass.states.get("sensor.egym_marcel_activiteitsniveau").state == "silver"
        assert hass.states.get("sensor.egym_marcel_spierbalans_quadriceps_hamstring").attributes["optimaal_tot"] == 60.0

        # Last measured values as sensors, with their date
        leg_press = hass.states.get("sensor.egym_marcel_leg_press_gewicht")
        assert leg_press.state == "53.0" and leg_press.attributes["icon"] == "mdi:weight-kilogram"
        assert "state_class" not in leg_press.attributes
        assert hass.states.get("sensor.egym_marcel_leg_press_kracht").attributes["gemeten_op"].startswith("2026-10-08")
        assert hass.states.get("sensor.egym_marcel_lichaamsgewicht").state == "80.0"

        # Later syncs only go back a few days, and re-importing does not duplicate rows
        assert calls[0] == datetime.date(2019, 1, 1)
        await entry.runtime_data.async_refresh()
        await async_wait_recording_done(hass)
        assert calls[1] > datetime.date(2026, 1, 1)
        stats = await _statistics(hass, ["egym:marcel_kracht_1002"])
        assert len(stats["egym:marcel_kracht_1002"]) == 2

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_two_people_do_not_collide(recorder_mock, enable_custom_integrations, hass):
    for name in ("Marcel", "Daan"):
        _entry(name, f"{name.lower()}@example.com").add_to_hass(hass)
    with patch(FETCH, return_value=all_data()):
        # Setting up the integration sets up every entry of it
        assert await hass.config_entries.async_setup(hass.config_entries.async_entries("egym")[0].entry_id)
        await hass.async_block_till_done()
        assert all(e.state is config_entries.ConfigEntryState.LOADED for e in hass.config_entries.async_entries("egym"))
        await async_wait_recording_done(hass)
    ids = {i["statistic_id"] for i in await get_instance(hass).async_add_executor_job(list_statistic_ids, hass)}
    assert {"egym:marcel_kracht_1002", "egym:daan_kracht_1002"} <= ids
    assert hass.states.get("sensor.egym_daan_bio_leeftijd").state == "40"


async def test_login_refused(recorder_mock, enable_custom_integrations, hass):
    entry = _entry()
    entry.add_to_hass(hass)
    with patch(FETCH, side_effect=AuthenticationError("refused")):
        await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is config_entries.ConfigEntryState.SETUP_ERROR


async def test_config_flow(recorder_mock, enable_custom_integrations, hass):
    result = await hass.config_entries.flow.async_init("egym", context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    with patch("custom_components.egym.config_flow._check_login", side_effect=DiscoveryError("none")):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"email": "marcel@example.com", "password": "x"}
        )
    assert result["errors"] == {"base_url": "discovery_failed"}

    with patch("custom_components.egym.config_flow._check_login", return_value="https://gym.netpulse.com"), \
         patch("custom_components.egym.async_setup_entry", return_value=True):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"email": "marcel@example.com", "password": "x", "base_url": "https://gym.netpulse.com"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "marcel"
    assert result["data"]["name"] == "marcel"


async def test_name_from_email_when_empty(recorder_mock, enable_custom_integrations, hass):
    entry = MockConfigEntry(
        domain="egym", unique_id="daan.jansen@example.com",
        data={"email": "daan.jansen@example.com", "password": "x", "name": "", "base_url": "https://gym.netpulse.com"},
    )
    entry.add_to_hass(hass)
    with patch(FETCH, return_value=all_data()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)
    ids = {i["statistic_id"] for i in await get_instance(hass).async_add_executor_job(list_statistic_ids, hass)}
    assert "egym:daan_jansen_kracht_1002" in ids
    assert hass.states.get("sensor.egym_daan_jansen_bio_leeftijd").state == "40"


async def test_name_with_space(recorder_mock, enable_custom_integrations, hass):
    _entry("Daan Jansen", "daan@example.com").add_to_hass(hass)
    with patch(FETCH, return_value=all_data()):
        assert await hass.config_entries.async_setup(hass.config_entries.async_entries("egym")[0].entry_id)
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)
    ids = {i["statistic_id"] for i in await get_instance(hass).async_add_executor_job(list_statistic_ids, hass)}
    assert "egym:daan_jansen_kracht_1002" in ids
    assert hass.states.get("sensor.egym_daan_jansen_bio_leeftijd").state == "40"



async def test_latest_survives_short_sync_and_new_exercise_appears(recorder_mock, enable_custom_integrations, hass):
    entry = _entry()
    entry.add_to_hass(hass)
    first = all_data()
    with patch(FETCH, return_value=first):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    # A later sync that only sees one new exercise keeps the older sensors and adds the new one
    later = {**all_data(), "workouts": [{
        "completedAt": "2026-10-20T18:00:00", "timezone": "Europe/Amsterdam",
        "exercises": [{"label": "EGYM Seated Row", "completedAt": "2026-10-20T18:00:00", "timezone": "Europe/Amsterdam",
                       "activity": {"activityId": 334, "name": {"nl": "EGYM Seated Row"}},
                       "sets": [{"setType": "REP_BASED", "numberOfReps": 20, "weight": 30.0}]}],
    }], "strength": {}, "body_metrics": []}
    with patch(FETCH, return_value=later):
        await entry.runtime_data.async_refresh()
        await hass.async_block_till_done()
    assert hass.states.get("sensor.egym_marcel_seated_row_gewicht").state == "30.0"
    assert hass.states.get("sensor.egym_marcel_leg_press_gewicht").state == "53.0"
    assert hass.states.get("sensor.egym_marcel_leg_press_kracht").state == "105.0"


async def test_ships_its_own_icon(enable_custom_integrations, hass):
    from homeassistant.loader import async_get_integration
    integration = await async_get_integration(hass, "egym")
    assert integration.has_branding


async def test_store_from_older_version_triggers_full_sync(recorder_mock, enable_custom_integrations, hass, hass_storage):
    entry = _entry()
    entry.add_to_hass(hass)
    hass_storage[f"egym.{entry.entry_id}.v2"] = {"version": 1, "key": f"egym.{entry.entry_id}.v2", "data": {"last_sync": "2026-10-19"}}
    starts = []
    with patch(FETCH, side_effect=lambda e, p, b, start, end: starts.append(start) or all_data()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert starts == [datetime.date(2019, 1, 1)]
    assert hass.states.get("sensor.egym_marcel_lichaamsgewicht").state == "80.0"
