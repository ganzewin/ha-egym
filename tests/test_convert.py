import datetime

from custom_components.egym.convert import (
    body_metric_types,
    body_metrics_to_statistics,
    current_values,
    history_values,
    band_position,
    derived_statistics,
    intensity,
    latest_sensors,
    latest_values,
    merge_history,
    ordered_name,
    parse_order,
    progress_sensors,
    sessions_per_week,
    strength_index,
    strength_to_statistics,
    workouts_to_statistics,
)

from .sample_data import ACTIVITY_LEVEL, BIO_AGE, BODY_METRICS, LATEST_BODY, MUSCLE_IMBALANCES, STRENGTH, WORKOUTS

UTC = datetime.UTC


def test_workouts():
    stats = workouts_to_statistics(WORKOUTS)
    assert set(stats) == {
        "egym:oefening_581_gewicht", "egym:oefening_581_herhalingen", "egym:oefening_581_volume",
        "egym:oefening_333_gewicht", "egym:oefening_333_herhalingen", "egym:oefening_333_volume",
        "egym:training_volume_totaal",
    }
    first = datetime.datetime(2026, 10, 1, 8, tzinfo=UTC)
    # Leg Press 2 x 20 x 50 kg = 2000, Chest Press 6 x 5 + 20 x 20 = 430
    assert stats["egym:oefening_581_volume"]["rows"][first]["mean"] == 2000.0
    assert stats["egym:training_volume_totaal"]["rows"][first]["mean"] == 2430.0
    rows = stats["egym:oefening_581_gewicht"]["rows"]
    second = rows[datetime.datetime(2026, 10, 8, 15, tzinfo=UTC)]  # 17:05 CEST
    assert (second["min"], second["mean"], second["max"]) == (52.0, 52.5, 53.0)
    reps = stats["egym:oefening_333_herhalingen"]["rows"][datetime.datetime(2026, 10, 1, 8, tzinfo=UTC)]
    assert reps["mean"] == 26


def test_strength_keeps_best_of_hour():
    rows = strength_to_statistics(STRENGTH)["egym:kracht_1002"]["rows"]
    assert rows[datetime.datetime(2026, 10, 8, 15, tzinfo=UTC)]["max"] == 105
    assert len(rows) == 2


def test_body_metrics():
    assert body_metric_types(LATEST_BODY) == ["BASAL_METABOLIC_RATE_KJ", "BODY_FAT_PERCENTS", "WEIGHT_KG"]
    stats = body_metrics_to_statistics(BODY_METRICS, "Europe/Amsterdam")
    weight = stats["egym:lichaam_weight_kg"]
    assert weight["unit"] == "kg" and len(weight["rows"]) == 2
    assert weight["rows"][datetime.datetime(2026, 10, 1, 10, tzinfo=UTC)]["max"] == 81.0  # 12:00 CEST
    bmr = stats["egym:lichaam_basal_metabolic_rate_kj"]
    assert bmr["unit"] == "kcal" and next(iter(bmr["rows"].values()))["max"] == 2000.0


def test_current_values():
    values = current_values(BIO_AGE, ACTIVITY_LEVEL, MUSCLE_IMBALANCES)
    assert values["bio_leeftijd"]["value"] == 40
    assert values["bio_leeftijd_cardio"]["value"] is None
    balance = values["spierbalans_quadriceps_hamstring"]
    assert balance["value"] == 45.0 and balance["attrs"]["optimaal_vanaf"] == 40.0
    assert balance["icon"] == "mdi:scale-balance" and balance["measurement"]
    assert not values["activiteit_niveau"]["measurement"]


def test_latest_values_and_sensors():
    stats = {
        **workouts_to_statistics(WORKOUTS),
        **strength_to_statistics(STRENGTH),
        **body_metrics_to_statistics(BODY_METRICS, "Europe/Amsterdam"),
    }
    history = history_values(stats)
    latest = latest_values(history)
    assert latest["oefening_581_gewicht"]["value"] == 53.0  # heaviest set of the last session
    assert latest["oefening_581_gewicht"]["name"] == "Training Leg Press gewicht"
    assert latest["kracht_1002"]["name"] == "Krachttest Leg Press"
    assert latest["lichaam_weight_kg"]["name"] == "Lichaam gewicht"
    assert latest["lichaam_basal_metabolic_rate_kj"]["name"] == "Lichaam basaal metabolisme"
    assert latest["oefening_581_herhalingen"]["value"] == 40
    assert latest["kracht_1002"]["value"] == 105
    assert latest["lichaam_weight_kg"]["value"] == 80.0
    sensors = latest_sensors(history)
    assert sensors["kracht_1002"]["attrs"]["gemeten_op"] == "2026-10-08T15:00:00+00:00"
    assert not sensors["kracht_1002"]["measurement"]
    assert sensors["kracht_1002"]["icon"] == "mdi:arm-flex"
    extra = latest_sensors({
        "lichaam_segmental_lean_trunk_kg": {**history["lichaam_weight_kg"], "name": "Lichaam spiermassa romp"},
        "lichaam_height_cm": {**history["lichaam_weight_kg"], "name": "Lichaam lengte"},
    })
    assert extra["lichaam_segmental_lean_trunk_kg"]["enabled"] is True
    assert extra["lichaam_height_cm"]["enabled"] is False


def test_chart_attributes_combine_sessions_and_strength_tests():
    stats = {**workouts_to_statistics(WORKOUTS), **strength_to_statistics(STRENGTH)}
    sensors = latest_sensors(history_values(stats))
    attrs = sensors["oefening_581_gewicht"]["attrs"]
    assert attrs["sessies"] == [["2026-10-01T08:00:00+00:00", 50.0], ["2026-10-08T15:00:00+00:00", 53.0]]
    assert attrs["krachttest"] == [["2026-10-01T08:00:00+00:00", 100.0], ["2026-10-08T15:00:00+00:00", 105.0]]
    assert sensors["oefening_581_herhalingen"]["attrs"]["sessies"][-1] == ["2026-10-08T15:00:00+00:00", 40]
    assert "krachttest" not in sensors["oefening_581_herhalingen"]["attrs"]
    assert sensors["oefening_333_gewicht"]["attrs"]["krachttest"] == []  # no test on this machine yet


def test_merge_history_keeps_old_points():
    full = history_values(workouts_to_statistics(WORKOUTS))
    stored = merge_history({}, full)
    recent = history_values(workouts_to_statistics(WORKOUTS[1:]))
    merge_history(stored, recent)
    assert len(stored["oefening_581_gewicht"]["points"]) == 2


def _history_with_tests(tests):
    """tests: {machine id: [(iso time, value)]}"""
    return {
        f"kracht_{machine}": {"name": f"Krachttest M{machine}", "unit": "kg", "points": dict(points)}
        for machine, points in tests.items()
    }


def test_strength_index_is_average_growth_per_machine():
    history = _history_with_tests({
        1: [("2026-10-01T08:00:00+00:00", 100.0), ("2026-10-19T13:00:00+00:00", 120.0)],
        2: [("2026-10-01T08:00:00+00:00", 50.0), ("2026-10-19T13:00:00+00:00", 65.0)],
        # Tested for the first time later: joins at 100% of its own baseline
        3: [("2026-11-05T09:00:00+00:00", 40.0)],
    })
    assert strength_index(history) == [
        ("2026-10-01T08:00:00+00:00", 100.0),
        ("2026-10-19T13:00:00+00:00", 125.0),  # (1.20 + 1.30) / 2; a sum would give 123.3
        ("2026-11-05T09:00:00+00:00", 116.7),  # (1.20 + 1.30 + 1.00) / 3
    ]
    rows = derived_statistics(history)["egym:krachttest_index"]["rows"]
    assert rows[datetime.datetime(2026, 10, 19, 13, tzinfo=UTC)]["mean"] == 125.0


def test_strength_index_with_real_tests():
    history = history_values(strength_to_statistics(STRENGTH))
    assert strength_index(history)[-1][1] == 105.0


def test_krachttest_attributes_and_pct_of_strength():
    stats = {**workouts_to_statistics(WORKOUTS), **strength_to_statistics(STRENGTH)}
    sensors = latest_sensors(history_values(stats))
    test = sensors["kracht_1002"]["attrs"]
    assert (test["nulmeting"], test["verandering_kg"], test["verandering_pct"], test["aantal_metingen"]) == (100.0, 5.0, 5.0, 2)
    assert sensors["oefening_581_gewicht"]["attrs"]["pct_van_krachttest"] == 50.5  # 53 / 105
    assert sensors["oefening_581_gewicht"]["attrs"]["positie_in_band_pct"] == 42  # (50.5 - 40) / 25
    assert "pct_van_krachttest" not in sensors["oefening_333_gewicht"]["attrs"]  # no test on this machine
    assert "oefening_581_volume" not in sensors
    assert sensors["training_volume_totaal"]["value"] == 2100.0  # 20 x 52 + 20 x 53, last session


def test_sessions_per_week():
    from zoneinfo import ZoneInfo
    history = history_values(workouts_to_statistics(WORKOUTS))
    now = datetime.datetime(2026, 10, 9, 12, tzinfo=ZoneInfo("Europe/Amsterdam"))  # Friday
    assert sessions_per_week(history, now) == (1, 0.5)  # 8 Oct this week; 1 and 8 Oct in 4 weeks
    sensors = progress_sensors(history, now)
    assert sensors["training_sessies_deze_week"]["value"] == 1
    assert "krachttest_index" not in sensors  # no strength tests in this history


def test_intensity_uses_the_test_in_effect_at_each_session():
    history = {
        "oefening_333_gewicht": {"name": "Training Chest Press gewicht", "unit": "kg", "points": {
            "2026-10-01T08:00:00+00:00": 18.0, "2026-10-12T14:00:00+00:00": 21.0,
            "2026-10-16T14:00:00+00:00": 23.0, "2026-10-19T13:00:00+00:00": 27.0,
        }},
        "kracht_998": {"name": "Krachttest Chest Press", "unit": "kg", "points": {
            "2026-10-01T08:00:00+00:00": 45.0, "2026-10-19T13:00:00+00:00": 64.0,
        }},
    }
    machine, points = intensity(history)["oefening_333"]
    # Rises within a cycle, drops back when a new test raises the baseline
    assert machine == "Chest Press"
    assert [p for _, p in points] == [40.0, 46.7, 51.1, 42.2]
    stats = derived_statistics(history)
    assert stats["egym:oefening_333_intensiteit"]["unit"] == "%"
    assert stats["egym:training_intensiteit"]["rows"][datetime.datetime(2026, 10, 16, 14, tzinfo=UTC)]["mean"] == 51.1
    from zoneinfo import ZoneInfo
    sensor = progress_sensors(history, datetime.datetime(2026, 10, 20, tzinfo=ZoneInfo("Europe/Amsterdam")))["training_intensiteit"]
    assert sensor["value"] == 42.2 and sensor["attrs"]["positie_in_band_pct"] == 9
    assert sensor["attrs"]["per_toestel"] == {"Chest Press": 42.2}


def test_band_position_is_clipped():
    assert (band_position(30, 40, 65), band_position(52.5, 40, 65), band_position(70, 40, 65)) == (0, 50, 100)


GYM_ORDER = "1\tLeg Press\n2\tSeated Row\n3\tLeg Curl\n4\tBack Extension\n5\tLat Pulldown\n6\tAbdominal Crunch\n7\tLeg Extension\n8\tChest Press"


def test_parse_order_accepts_numbers_tabs_commas_and_prefix():
    assert parse_order(GYM_ORDER)["chest press"] == 8
    assert parse_order("EGYM Leg Press, 2. Seated Row;Leg Curl") == {"leg press": 1, "seated row": 2, "leg curl": 3}
    assert parse_order("") == {}


def test_ordered_names():
    positions = parse_order(GYM_ORDER)
    assert ordered_name("Training Leg Press gewicht", positions) == "Training 1 Leg Press gewicht"
    assert ordered_name("Krachttest Chest Press", positions) == "Krachttest 8 Chest Press"
    assert ordered_name("Training Seated Row intensiteit", positions) == "Training 2 Seated Row intensiteit"
    for unchanged in ("Training volume totaal", "Krachttest index", "Training sessies per week", "Training Treadmill gewicht"):
        assert ordered_name(unchanged, positions) == unchanged
    ten = parse_order(",".join(f"M{i}" for i in range(1, 11)))
    assert ordered_name("Krachttest M3", ten) == "Krachttest 03 M3"  # same width, so 10 sorts after 9



def test_eccentric_sets_are_kept_apart():
    from .sample_data import _exercise, _workout
    workouts = [_workout("2026-10-21T15:47:10", [
        # Lat Pulldown: eccentric set first, as at the gym
        _exercise(335, "EGYM Lat Pulldown", "2026-10-21T15:41:39", [(45.0, 20)], eccentric=[(37.0, 15)]),
    ])]
    stats = workouts_to_statistics(workouts)
    start = datetime.datetime(2026, 10, 21, 13, tzinfo=UTC)
    assert stats["egym:oefening_335_gewicht"]["rows"][start]["max"] == 45.0
    assert stats["egym:oefening_335_gewicht"]["rows"][start]["mean"] == 45.0  # classic only
    assert stats["egym:oefening_335_herhalingen"]["rows"][start]["mean"] == 20
    assert stats["egym:oefening_335_excentrisch_gewicht"]["name"] == "Training Lat Pulldown excentrisch gewicht"
    assert stats["egym:oefening_335_excentrisch_herhalingen"]["rows"][start]["mean"] == 15
    # Eccentric: 37 kg lifting, 37 x 1.55 = 57 kg lowering, average 47 kg
    assert stats["egym:oefening_335_excentrisch_gewicht"]["rows"][start]["mean"] == 47.0
    assert stats["egym:oefening_335_volume"]["rows"][start]["mean"] == 45 * 20 + 47 * 15  # all sets
    sensors = latest_sensors(history_values(stats))
    assert "oefening_335_excentrisch_gewicht" not in sensors
    attrs = sensors["oefening_335_gewicht"]["attrs"]
    assert (attrs["excentrisch"], attrs["excentrisch_heen"], attrs["excentrisch_terug"]) == (47.0, 37, 57)
    assert attrs["excentrisch_sessies"] == [["2026-10-21T13:00:00+00:00", 47.0]]
    assert sensors["oefening_335_herhalingen"]["attrs"]["excentrisch"] == 15


def _leg_press(completed, sets):
    return {"completedAt": completed, "timezone": "Europe/Amsterdam", "exercises": [
        {"label": "EGYM Leg Press", "completedAt": completed, "timezone": "Europe/Amsterdam",
         "activity": {"activityId": 581, "name": {"nl": "EGYM Leg Press"}},
         "sets": [{"setType": "REP_BASED", "trainingMethod": method, "weight": weight, "numberOfReps": reps}
                  for method, weight, reps in sets]}]}


def test_intensity_counts_eccentric_sessions():
    stats = {
        **workouts_to_statistics([
            _leg_press("2026-10-21T15:34:21", [("REGULAR_REPBASED", 62.0, 20)]),
            # Eccentric only: 50 kg lifting, 78 kg lowering, average 64 kg
            _leg_press("2026-10-26T15:34:21", [("NEGATIVE_REPBASED", 50.0, 15)]),
        ]),
        **strength_to_statistics(STRENGTH),
    }
    _machine, points = intensity(history_values(stats))["oefening_581"]
    assert [pct for _t, pct in points[-2:]] == [59.0, 61.0]  # 62 / 105 and 64 / 105


def test_unknown_method_gets_its_own_label():
    from .sample_data import _workout
    stats = workouts_to_statistics([_workout("2026-10-21T15:00:00", [
        {"label": "EGYM Leg Press", "completedAt": "2026-10-21T15:00:00", "timezone": "Europe/Amsterdam",
         "activity": {"activityId": 581, "name": {"nl": "EGYM Leg Press"}},
         "sets": [{"setType": "REP_BASED", "trainingMethod": "ISOKINETIC_REPBASED", "weight": 50.0, "numberOfReps": 10}]},
    ])])
    assert "egym:oefening_581_isokinetic_gewicht" in stats
    assert "egym:oefening_581_gewicht" not in stats



def test_eccentric_load_matches_the_machine():
    from custom_components.egym.convert import eccentric_load
    # Values read on the machines: Leg Extension 19 / 29 kg, Chest Press 22 / 34 kg
    assert eccentric_load(19.0, 1.55) == (19.0, 29.0, 24.0)
    assert eccentric_load(22.0, 1.55) == (22.0, 34.0, 28.0)
    assert eccentric_load(22.0, 1.5)[1] == 33.0  # why 1.5 is not the default
