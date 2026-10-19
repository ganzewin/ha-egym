"""Turn EGYM API data into hourly statistic rows. No Home Assistant imports, so it can be tested on its own."""

import datetime
import re
from zoneinfo import ZoneInfo

from .const import DOMAIN

# Body metric types that are reference ranges, not measurements of you.
_RANGE_SUFFIX = re.compile(r"_(LOW|TOP)(_|$)")

# type -> (Dutch name, unit, unit_class, factor)
BODY_METRICS = {
    "WEIGHT_KG": ("Gewicht", "kg", "mass", 1),
    "BMI": ("BMI", None, None, 1),
    "BODY_FAT_PERCENTS": ("Vetpercentage", "%", None, 1),
    "BODY_FAT_MASS_KG": ("Vetmassa", "kg", "mass", 1),
    "FAT_FREE_MASS_KG": ("Vetvrije massa", "kg", "mass", 1),
    "SKELETAL_MUSCLE_MASS_KG": ("Skeletspiermassa", "kg", "mass", 1),
    "BODY_WATER_LITER": ("Lichaamsvocht", "L", "volume", 1),
    "VISCERAL_FAT_LEVEL_CM2": ("Visceraal vet", "cm²", None, 1),
    "BASAL_METABOLIC_RATE_KJ": ("Basaal metabolisme", "kcal", "energy", 1 / 4.184),
    "HEIGHT_CM": ("Lengte", "cm", "distance", 1),
    "SEGMENTAL_LEAN_TRUNK_KG": ("Spiermassa romp", "kg", "mass", 1),
    "SEGMENTAL_LEAN_LEFT_ARM_KG": ("Spiermassa linkerarm", "kg", "mass", 1),
    "SEGMENTAL_LEAN_RIGHT_ARM_KG": ("Spiermassa rechterarm", "kg", "mass", 1),
    "SEGMENTAL_LEAN_LEFT_LEG_KG": ("Spiermassa linkerbeen", "kg", "mass", 1),
    "SEGMENTAL_LEAN_RIGHT_LEG_KG": ("Spiermassa rechterbeen", "kg", "mass", 1),
    "SEGMENTAL_FAT_TRUNK_KG": ("Vetmassa romp", "kg", "mass", 1),
    "SEGMENTAL_FAT_LEFT_ARM_KG": ("Vetmassa linkerarm", "kg", "mass", 1),
    "SEGMENTAL_FAT_RIGHT_ARM_KG": ("Vetmassa rechterarm", "kg", "mass", 1),
    "SEGMENTAL_FAT_LEFT_LEG_KG": ("Vetmassa linkerbeen", "kg", "mass", 1),
    "SEGMENTAL_FAT_RIGHT_LEG_KG": ("Vetmassa rechterbeen", "kg", "mass", 1),
}


def _slug(text):
    return re.sub(r"[^a-z0-9]+", "_", (text or "").lower()).strip("_")


def _hour(moment):
    return moment.astimezone(datetime.UTC).replace(minute=0, second=0, microsecond=0)


def _machine(name):
    """'EGYM Leg Press' -> 'Leg Press'."""
    return (name or "").removeprefix("EGYM ").strip()


def _parse(value, zone_name):
    moment = datetime.datetime.fromisoformat(value)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=ZoneInfo(zone_name or "UTC"))
    return moment


def _add(result, statistic_id, name, unit, unit_class, start, values):
    stat = result.setdefault(
        statistic_id, {"name": name, "unit": unit, "unit_class": unit_class, "rows": {}, "_values": {}}
    )
    stat["_values"].setdefault(start, []).extend(values)


def _finish(result):
    for stat in result.values():
        for start, values in stat.pop("_values").items():
            stat["rows"][start] = {
                "start": start,
                "mean": round(sum(values) / len(values), 2),
                "min": round(min(values), 2),
                "max": round(max(values), 2),
            }
    return result


def body_metric_types(latest):
    """Measured body metric types in a get_latest_body_metrics() answer, without reference ranges."""
    return sorted({m["type"] for m in latest or [] if m.get("type") and not _RANGE_SUFFIX.search(m["type"])})


def workouts_to_statistics(workouts):
    """Per exercise and session: gewicht (mean/min/max over sets, kg) and herhalingen (total over sets).

    Only rep-based sets with a weight are used, so cardio is skipped.
    """
    collected = {}
    for workout in workouts or []:
        for exercise in workout.get("exercises") or []:
            activity = exercise.get("activity") or {}
            key = activity.get("activityId")
            key = f"oefening_{key}" if key is not None else (f"oefening_{_slug(exercise.get('label'))}" if _slug(exercise.get("label")) else None)
            if key is None:
                continue
            sets = [
                s for s in exercise.get("sets") or []
                if s.get("setType") == "REP_BASED" and s.get("weight") is not None
            ]
            if not sets:
                continue
            name = (activity.get("name") or {}).get("nl") or exercise.get("label") or "Onbekende oefening"
            start = _hour(_parse(
                exercise.get("completedAt") or workout["completedAt"],
                exercise.get("timezone") or workout.get("timezone"),
            ))
            entry = collected.setdefault((key, start), {"name": name, "weights": [], "reps": 0})
            entry["weights"].extend(float(s["weight"]) for s in sets)
            entry["reps"] += sum(int(s.get("numberOfReps") or 0) for s in sets)

    result = {}
    for (key, start), entry in collected.items():
        # Names start with a group word, so sensors and chart legends sort per group
        name = _machine(entry["name"])
        _add(result, f"{DOMAIN}:{key}_gewicht", f"Training {name} gewicht", "kg", "mass", start, entry["weights"])
        _add(result, f"{DOMAIN}:{key}_herhalingen", f"Training {name} herhalingen", "herhalingen", None, start, [entry["reps"]])
    return _finish(result)


def strength_to_statistics(strength):
    """Strength tests per machine: the strength value (kg) EGYM calculates, per hour."""
    result = {}
    for item in (strength or {}).get("strengthMeasurements") or []:
        activity = item.get("activity") or {}
        value = (item.get("strength") or {}).get("value")
        if value is None or activity.get("activityId") is None or not item.get("createdAt"):
            continue
        start = _hour(_parse(item["createdAt"], item.get("timezone")))
        label = activity.get("label") or f"Toestel {activity['activityId']}"
        _add(result, f"{DOMAIN}:kracht_{activity['activityId']}", f"Krachttest {_machine(label)}", "kg", "mass", start, [float(value)])
    return _finish(result)


def body_metrics_to_statistics(body_metrics, zone_name):
    """Body composition history. EGYM gives only a date, so each value is placed at 12:00 local time."""
    result = {}
    zone = ZoneInfo(zone_name)
    for series in body_metrics or []:
        metric_type = series.get("type")
        if not metric_type or _RANGE_SUFFIX.search(metric_type):
            continue
        name, unit, unit_class, factor = BODY_METRICS.get(
            metric_type, (metric_type.replace("_", " ").capitalize(), None, None, 1)
        )
        for point in series.get("history") or []:
            if point.get("value") is None or not point.get("date"):
                continue
            day = datetime.date.fromisoformat(point["date"])
            start = _hour(datetime.datetime.combine(day, datetime.time(12), zone))
            label = name if name.isupper() else name[0].lower() + name[1:]
            _add(result, f"{DOMAIN}:lichaam_{_slug(metric_type)}", f"Lichaam {label}", unit, unit_class, start, [float(point["value"]) * factor])
    return _finish(result)


def _value(node):
    return node.get("value") if isinstance(node, dict) else None


def _sensor(name, value, unit, icon, attrs=None, measurement=True, enabled=True):
    return {
        "name": name,
        "value": value,
        "unit": unit,
        "icon": icon,
        "attrs": attrs or {},
        "measurement": measurement and unit is not None,
        "enabled": enabled,
    }


def current_values(bio_age, activity_level, imbalances):
    """Sensors for values EGYM only gives as a current value: {key: sensor dict}."""
    bio = bio_age or {}
    strength = bio.get("strengthBioAgeDetails") or {}
    age = "mdi:account-clock"
    values = {
        "bio_leeftijd": _sensor("Bio-leeftijd", _value((bio.get("totalDetails") or {}).get("totalBioAge")), "jaar", age),
        "bio_leeftijd_spieren": _sensor("Bio-leeftijd spieren", _value(strength.get("muscleBioAge")), "jaar", age),
        "bio_leeftijd_bovenlichaam": _sensor("Bio-leeftijd bovenlichaam", _value(strength.get("upperBodyAge")), "jaar", age),
        "bio_leeftijd_romp": _sensor("Bio-leeftijd romp", _value(strength.get("coreAge")), "jaar", age),
        "bio_leeftijd_onderlichaam": _sensor("Bio-leeftijd onderlichaam", _value(strength.get("lowerBodyAge")), "jaar", age),
        "bio_leeftijd_metabolisme": _sensor("Bio-leeftijd metabolisme", _value((bio.get("metabolicDetails") or {}).get("metabolicAge")), "jaar", age),
        "bio_leeftijd_cardio": _sensor("Bio-leeftijd cardio", _value((bio.get("cardioBioAgeDetails") or {}).get("cardioAge")), "jaar", age),
        "bio_leeftijd_flexibiliteit": _sensor("Bio-leeftijd flexibiliteit", _value((bio.get("flexibilityDetails") or {}).get("flexibilityAge")), "jaar", age),
    }
    level = activity_level or {}
    points, goal = level.get("points"), level.get("goal")
    progress = round(points / goal * 100, 1) if isinstance(points, (int, float)) and goal else None
    values.update({
        "activiteit_punten": _sensor("Activiteit punten", level.get("points"), "punten", "mdi:star-circle"),
        "activiteit_doel": _sensor("Activiteit doel", level.get("goal"), "punten", "mdi:flag-checkered"),
        "activiteit_voortgang": _sensor("Activiteit voortgang", progress, "%", "mdi:progress-check"),
        "activiteit_behouden": _sensor("Activiteit punten om niveau te behouden", level.get("maintainPoints"), "punten", "mdi:shield-star"),
        "activiteit_dagen_over": _sensor("Activiteit dagen over in periode", level.get("daysLeft"), "dagen", "mdi:calendar-clock"),
        "activiteit_niveau": _sensor("Activiteit niveau", level.get("level"), None, "mdi:trophy"),
    })
    for item in (imbalances or {}).get("muscleImbalances") or []:
        size = item.get("rangeSize") or 10000.0
        if item.get("position") is None:
            continue
        key = f"spierbalans_{_slug(item.get('agonistMuscle'))}_{_slug(item.get('antagonistMuscle'))}"
        name = f"Spierbalans {item['agonistMuscle'].replace('_', ' ').lower()} / {item['antagonistMuscle'].replace('_', ' ').lower()}"
        values[key] = _sensor(
            name,
            round(item["position"] / size * 100, 1),
            "%",
            "mdi:scale-balance",
            {
                "optimaal_vanaf": round(item["optimalRangeStartPosition"] / size * 100, 1),
                "optimaal_tot": round(item["optimalRangeEndPosition"] / size * 100, 1),
                "kracht_agonist": item.get("agonistStrengthValue"),
                "kracht_antagonist": item.get("antagonistStrengthValue"),
                "lichaamsdeel": item.get("bodyRegion"),
            },
        )
    return values


def latest_values(statistics):
    """Most recent value per statistic, for "last measured" sensors: {object_id: dict}.

    object_id is the statistic id without "egym:", so it matches the statistics.
    gewicht and kracht use the heaviest value of the session, the rest the mean.
    """
    latest = {}
    for statistic_id, stat in statistics.items():
        if not stat["rows"]:
            continue
        start = max(stat["rows"])
        row = stat["rows"][start]
        object_id = statistic_id.split(":", 1)[1]
        use_max = object_id.endswith("_gewicht") or object_id.startswith("kracht_")
        latest[object_id] = {
            "name": stat["name"],
            "value": row["max"] if use_max else row["mean"],
            "unit": stat["unit"],
            "time": start.isoformat(),
        }
    return latest


def latest_sensors(latest):
    """Sensor dicts for latest_values() output; segment and height values start disabled."""
    sensors = {}
    for object_id, item in latest.items():
        if object_id.startswith("oefening_"):
            icon = "mdi:repeat" if object_id.endswith("_herhalingen") else "mdi:weight-kilogram"
        elif object_id.startswith("kracht_"):
            icon = "mdi:arm-flex"
        else:
            icon = "mdi:human"
        enabled = not object_id.startswith(("lichaam_segmental_", "lichaam_height"))
        # No state class: the history of these values already exists as statistics with the right dates
        sensors[object_id] = _sensor(
            item["name"], item["value"], item["unit"], icon,
            {"gemeten_op": item["time"]}, measurement=False, enabled=enabled,
        )
    return sensors
