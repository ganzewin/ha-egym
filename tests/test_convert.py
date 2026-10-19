import datetime

from custom_components.egym.convert import (
    body_metric_types,
    body_metrics_to_statistics,
    current_values,
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
    assert values["bio_leeftijd"][1] == 40
    assert values["bio_leeftijd_cardio"][1] is None
    balance = values["spierbalans_quadriceps_hamstring"]
    assert balance[1] == 45.0 and balance[3]["optimaal_vanaf"] == 40.0
