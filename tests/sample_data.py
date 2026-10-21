"""Made-up EGYM API answers in the shape the real API returns."""


def _exercise(activity_id, label, completed, sets, eccentric=()):
    return {
        "label": label,
        "completedAt": completed,
        "timezone": "Europe/Amsterdam",
        "activity": {"activityId": activity_id, "name": {"en": label, "nl": label}},
        "sets": [
            {"setType": "REP_BASED", "trainingMethod": "REGULAR_REPBASED", "numberOfReps": reps, "weight": weight,
             "duration": 30} for weight, reps in sets
        ] + [
            {"setType": "REP_BASED", "trainingMethod": "NEGATIVE_REPBASED", "numberOfReps": reps, "weight": weight,
             "duration": 90} for weight, reps in eccentric
        ],
    }


def _workout(completed, exercises):
    return {"completedAt": completed, "timezone": "Europe/Amsterdam", "exercises": exercises}


WORKOUTS = [
    _workout("2026-10-01T10:42:18", [
        _exercise(581, "EGYM Leg Press", "2026-10-01T10:42:18", [(50.0, 20), (50.0, 20)]),
        _exercise(333, "EGYM Chest Press", "2026-10-01T10:42:18", [(5.0, 6), (20.0, 20)]),
    ]),
    _workout("2026-10-08T17:05:00", [
        _exercise(581, "EGYM Leg Press", "2026-10-08T17:05:00", [(52.0, 20), (53.0, 20)]),
        {"label": "Treadmill", "completedAt": "2026-10-08T17:05:00", "timezone": "Europe/Amsterdam",
         "activity": {"activityId": 9}, "sets": [{"setType": "DURATION_BASED", "duration": 600}]},
    ]),
]


def _strength(id_, created, activity_id, label, value):
    return {
        "id": id_, "createdAt": created, "timezone": "Europe/Amsterdam",
        "activity": {"activityId": activity_id, "label": label},
        "strength": {"value": value}, "strengthSet": {"reps": 1, "weight": value + 0.3},
    }


STRENGTH = {"strengthMeasurements": [
    _strength(3, "2026-10-08T15:20:00.000Z", 1002, "EGYM Leg Press", 105),
    _strength(2, "2026-10-08T15:05:00.000Z", 1002, "EGYM Leg Press", 101),
    _strength(1, "2026-10-01T08:31:00.000Z", 1002, "EGYM Leg Press", 100),
]}

LATEST_BODY = [
    {"type": "WEIGHT_KG", "value": 80.0}, {"type": "BODY_FAT_PERCENTS", "value": 20.0},
    {"type": "BODY_FAT_PERCENTS_TOP", "value": 20.0}, {"type": "BASAL_METABOLIC_RATE_KJ", "value": 8368.0},
]

BODY_METRICS = [
    {"type": "WEIGHT_KG", "history": [{"value": 81.0, "date": "2026-10-01"}, {"value": 80.0, "date": "2026-10-15"}]},
    {"type": "BODY_FAT_PERCENTS", "history": [{"value": 20.0, "date": "2026-10-01"}]},
    {"type": "BASAL_METABOLIC_RATE_KJ", "history": [{"value": 8368.0, "date": "2026-10-01"}]},
]

BIO_AGE = {
    "totalDetails": {"totalBioAge": {"value": 40}},
    "metabolicDetails": {"metabolicAge": {"value": 42}},
    "flexibilityDetails": {"flexibilityAge": None},
    "cardioBioAgeDetails": {"cardioAge": None},
    "strengthBioAgeDetails": {
        "upperBodyAge": {"value": 38}, "coreAge": {"value": 41},
        "lowerBodyAge": {"value": 39}, "muscleBioAge": {"value": 39},
    },
}

ACTIVITY_LEVEL = {"points": 500, "daysLeft": 10, "level": "silver", "goal": 1400, "maintainPoints": 800}

MUSCLE_IMBALANCES = {"muscleImbalances": [{
    "agonistMuscle": "QUADRICEPS", "antagonistMuscle": "HAMSTRING", "position": 4500.0,
    "optimalRangeStartPosition": 4000.0, "optimalRangeEndPosition": 6000.0, "rangeSize": 10000.0,
    "bodyRegion": "LOWER", "agonistStrengthValue": 60, "antagonistStrengthValue": 50,
}]}


def all_data():
    return {
        "workouts": WORKOUTS,
        "strength": STRENGTH,
        "body_metrics": BODY_METRICS,
        "bio_age": BIO_AGE,
        "activity_level": ACTIVITY_LEVEL,
        "muscle_imbalances": MUSCLE_IMBALANCES,
    }
