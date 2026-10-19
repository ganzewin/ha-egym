import datetime

from custom_components.egym.convert import (
    body_metric_types,
    body_metrics_to_statistics,
    current_values,
    history_values,
    latest_sensors,
    latest_values,
    merge_history,
    strength_to_statistics,
    workouts_to_statistics,
)

from .sample_data import ACTIVITY_LEVEL, BIO_AGE, BODY_METRICS, LATEST_BODY, MUSCLE_IMBALANCES, STRENGTH, WORKOUTS

UTC = datetime.UTC


def test_workouts():
    stats = workouts_to_statistics(WORKOUTS)
    assert set(stats) == {
        "egym:oefening_581_gewicht", "egym:oefening_581_herhalingen",
        "egym:oefening_333_gewicht", "egym:oefening_333_herhalingen",
    }
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
