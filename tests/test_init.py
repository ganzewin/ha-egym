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
        assert ids["egym:marcel_kracht_1002"]["name"] == "Marcel Krachttest Leg Press"
        stats = await _statistics(hass, ["egym:marcel_oefening_581_gewicht", "egym:marcel_lichaam_weight_kg"])
        assert [r["max"] for r in stats["egym:marcel_oefening_581_gewicht"]] == [50.0, 53.0]
        assert [r["max"] for r in stats["egym:marcel_lichaam_weight_kg"]] == [81.0, 80.0]

        assert hass.states.get("sensor.egym_marcel_bio_leeftijd").state == "40"
        assert hass.states.get("sensor.egym_marcel_bio_leeftijd_cardio").state == "unknown"
        assert hass.states.get("sensor.egym_marcel_activiteit_niveau").state == "silver"
        progress = hass.states.get("sensor.egym_marcel_activiteit_voortgang")
        assert progress.state == "35.7" and progress.attributes["state_class"] == "measurement"
        assert hass.states.get("sensor.egym_marcel_spierbalans_quadriceps_hamstring").attributes["optimaal_tot"] == 60.0

        # Last measured values as sensors, with their date
        leg_press = hass.states.get("sensor.egym_marcel_training_leg_press_gewicht")
        assert leg_press.state == "53.0" and leg_press.attributes["icon"] == "mdi:weight-kilogram"
        assert "state_class" not in leg_press.attributes
        assert hass.states.get("sensor.egym_marcel_krachttest_leg_press").attributes["gemeten_op"].startswith("2026-10-08")
        assert hass.states.get("sensor.egym_marcel_lichaam_gewicht").state == "80.0"
        assert len(leg_press.attributes["sessies"]) == 2 and len(leg_press.attributes["krachttest"]) == 2
        assert leg_press.attributes["pct_van_krachttest"] == 50.5
        intensity = hass.states.get("sensor.egym_marcel_training_intensiteit")
        assert intensity.state == "50.5" and intensity.attributes["positie_in_band_pct"] == 42
        index = hass.states.get("sensor.egym_marcel_krachttest_index")
        assert index.state == "105.0" and index.attributes["unit_of_measurement"] == "%"
        assert "state_class" not in index.attributes
        assert hass.states.get("sensor.egym_marcel_krachttest_leg_press").attributes["verandering_pct"] == 5.0
        assert hass.states.get("sensor.egym_marcel_training_volume_totaal").state == "2100.0"
        assert hass.states.get("sensor.egym_marcel_training_sessies_per_week") is not None
        stats = await _statistics(hass, ["egym:marcel_krachttest_index", "egym:marcel_training_volume_totaal",
                                         "egym:marcel_oefening_581_intensiteit"])
        assert [r["max"] for r in stats["egym:marcel_oefening_581_intensiteit"]] == [50.0, 50.5]
        assert [r["max"] for r in stats["egym:marcel_krachttest_index"]] == [100.0, 105.0]
        assert len(stats["egym:marcel_training_volume_totaal"]) == 2

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
            result["flow_id"], {"email": "marcel@example.com", "password": "x", "base_url": "https://gym.netpulse.com",
                                "volgorde": "Leg Press\nSeated Row\n"}
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["options"] == {"volgorde": "Leg Press\nSeated Row"}
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
    assert hass.states.get("sensor.egym_marcel_training_seated_row_gewicht").state == "30.0"
    leg_press = hass.states.get("sensor.egym_marcel_training_leg_press_gewicht")
    assert leg_press.state == "53.0" and len(leg_press.attributes["sessies"]) == 2
    assert hass.states.get("sensor.egym_marcel_krachttest_leg_press").state == "105.0"


async def test_ships_its_own_icon(enable_custom_integrations, hass):
    from homeassistant.loader import async_get_integration
    integration = await async_get_integration(hass, "egym")
    assert integration.has_branding


async def test_store_from_older_version_triggers_full_sync(recorder_mock, enable_custom_integrations, hass, hass_storage):
    entry = _entry()
    entry.add_to_hass(hass)
    hass_storage[f"egym.{entry.entry_id}.v2"] = {"version": 1, "key": f"egym.{entry.entry_id}.v2", "data": {"schema": 3, "last_sync": "2026-10-19", "history": {}}}
    starts = []
    with patch(FETCH, side_effect=lambda e, p, b, start, end: starts.append(start) or all_data()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert starts == [datetime.date(2019, 1, 1)]
    assert hass.states.get("sensor.egym_marcel_lichaam_gewicht").state == "80.0"


async def test_sensors_sort_per_group(recorder_mock, enable_custom_integrations, hass):
    from homeassistant.helpers import entity_registry as er
    entry = _entry()
    entry.add_to_hass(hass)
    with patch(FETCH, return_value=all_data()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    names = sorted(hass.states.get(e.entity_id).attributes["friendly_name"].removeprefix("EGYM Marcel ")
                   for e in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
                   if hass.states.get(e.entity_id))
    groups = [n.split()[0] for n in names]
    # every group word appears as one consecutive block
    blocks = [g for i, g in enumerate(groups) if i == 0 or groups[i - 1] != g]
    assert len(blocks) == len(set(blocks)), names
    assert set(blocks) == {"Activiteit", "Bio-leeftijd", "Gegevens", "Krachttest", "Lichaam", "Spierbalans", "Training"}, names


async def test_machine_order_numbers_names_and_entity_ids(recorder_mock, enable_custom_integrations, hass):
    entry = MockConfigEntry(
        domain="egym", unique_id="marcel@example.com",
        data={"email": "marcel@example.com", "password": "x", "name": "Marcel", "base_url": "https://gym.netpulse.com"},
        options={"volgorde": "1 Leg Press\n2 Seated Row\n8 Chest Press"},
    )
    entry.add_to_hass(hass)
    with patch(FETCH, return_value=all_data()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        await async_wait_recording_done(hass)
    leg_press = hass.states.get("sensor.egym_marcel_training_1_leg_press_gewicht")
    assert leg_press is not None and leg_press.attributes["volgnummer"] == 1
    assert hass.states.get("sensor.egym_marcel_krachttest_1_leg_press").state == "105.0"
    # Chest Press is third in this list
    assert hass.states.get("sensor.egym_marcel_training_3_chest_press_gewicht") is not None
    ids = {i["statistic_id"]: i for i in await get_instance(hass).async_add_executor_job(list_statistic_ids, hass)}
    # Statistic ids stay the same, so charts keep working when the order changes; the name gets the number
    assert ids["egym:marcel_kracht_1002"]["name"] == "Marcel Krachttest 1 Leg Press"
    assert list(hass.states.get("sensor.egym_marcel_krachttest_index").attributes["groei_per_toestel_pct"]) == ["1 Leg Press"]


async def test_options_flow_changes_order_and_reloads(recorder_mock, enable_custom_integrations, hass):
    entry = _entry()
    entry.add_to_hass(hass)
    with patch(FETCH, return_value=all_data()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get("sensor.egym_marcel_training_leg_press_gewicht").attributes["friendly_name"] == \
            "EGYM Marcel Training Leg Press gewicht"
        result = await hass.config_entries.options.async_init(entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        result = await hass.config_entries.options.async_configure(result["flow_id"], {"volgorde": "Leg Press"})
        assert result["type"] is FlowResultType.CREATE_ENTRY
        await hass.async_block_till_done()
    assert entry.options == {"volgorde": "Leg Press", "excentrisch_factor": 1.55}
    # Existing entity keeps its id, its name gets the number
    state = hass.states.get("sensor.egym_marcel_training_leg_press_gewicht")
    assert state.attributes["friendly_name"] == "EGYM Marcel Training 1 Leg Press gewicht"


async def test_eccentric_factor_option_and_full_resync(recorder_mock, enable_custom_integrations, hass):
    from .sample_data import _exercise, _workout
    workouts = [_workout("2026-10-21T15:47:10", [
        _exercise(333, "EGYM Chest Press", "2026-10-21T15:47:10", [(27.0, 20)], eccentric=[(22.0, 15)]),
    ])]
    data = {**all_data(), "workouts": workouts}
    entry = _entry()
    entry.add_to_hass(hass)
    starts = []
    with patch(FETCH, side_effect=lambda e, p, b, start, end: starts.append(start) or data):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        state = hass.states.get("sensor.egym_marcel_training_chest_press_gewicht")
        assert state.state == "27.0"
        assert (state.attributes["excentrisch"], state.attributes["excentrisch_terug"]) == (28.0, 34)
        # Changing the factor reloads and recalculates every session from the start
        result = await hass.config_entries.options.async_init(entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], {"volgorde": "", "excentrisch_factor": 1.5})
        await hass.async_block_till_done()
    assert entry.options["excentrisch_factor"] == 1.5
    assert starts[-1] == datetime.date(2019, 1, 1)
    state = hass.states.get("sensor.egym_marcel_training_chest_press_gewicht")
    assert (state.attributes["excentrisch"], state.attributes["excentrisch_terug"]) == (27.5, 33)


async def test_refresh_button_fetches_now(recorder_mock, enable_custom_integrations, hass):
    entry = _entry()
    entry.add_to_hass(hass)
    calls = []
    with patch(FETCH, side_effect=lambda *args: calls.append(args) or all_data()):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        first = hass.states.get("sensor.egym_marcel_gegevens_laatst_opgehaald").state
        assert first not in ("unknown", "unavailable")
        await hass.services.async_call(
            "button", "press", {"entity_id": "button.egym_marcel_gegevens_ophalen"}, blocking=True)
        await hass.async_block_till_done()
    assert len(calls) == 2
    assert hass.states.get("sensor.egym_marcel_gegevens_laatst_opgehaald").state >= first
