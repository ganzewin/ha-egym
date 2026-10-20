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
    """Per exercise and session: gewicht (mean/min/max over sets, kg), herhalingen (total over sets)
    and volume (sum of weight x repetitions, kg). Also the total volume of all exercises per session.

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
            entry = collected.setdefault((key, start), {"name": name, "weights": [], "reps": 0, "volume": 0.0})
            entry["weights"].extend(float(s["weight"]) for s in sets)
            entry["reps"] += sum(int(s.get("numberOfReps") or 0) for s in sets)
            entry["volume"] += sum(float(s["weight"]) * int(s.get("numberOfReps") or 0) for s in sets)

    result = {}
    totals = {}
    for (key, start), entry in collected.items():
        # Names start with a group word, so sensors and chart legends sort per group
        name = _machine(entry["name"])
        _add(result, f"{DOMAIN}:{key}_gewicht", f"Training {name} gewicht", "kg", "mass", start, entry["weights"])
        _add(result, f"{DOMAIN}:{key}_herhalingen", f"Training {name} herhalingen", "herhalingen", None, start, [entry["reps"]])
        _add(result, f"{DOMAIN}:{key}_volume", f"Training {name} volume", "kg", "mass", start, [entry["volume"]])
        totals[start] = totals.get(start, 0.0) + entry["volume"]
    for start, volume in totals.items():
        _add(result, f"{DOMAIN}:training_volume_totaal", "Training volume totaal", "kg", "mass", start, [volume])
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


def history_values(statistics):
    """One value per statistic and measurement: {object_id: {"name", "unit", "points": {iso time: value}}}.

    object_id is the statistic id without "egym:", so it matches the statistics.
    gewicht and kracht use the heaviest value of the session, the rest the mean.
    """
    history = {}
    for statistic_id, stat in statistics.items():
        object_id = statistic_id.split(":", 1)[1]
        use_max = object_id.endswith("_gewicht") or object_id.startswith("kracht_")
        history[object_id] = {
            "name": stat["name"],
            "unit": stat["unit"],
            "points": {
                start.isoformat(): row["max"] if use_max else row["mean"] for start, row in stat["rows"].items()
            },
        }
    return history


def merge_history(stored, new):
    """Add new points to the stored history; a newer sync wins for the same time."""
    for object_id, item in new.items():
        entry = stored.setdefault(object_id, {"name": item["name"], "unit": item["unit"], "points": {}})
        entry["name"], entry["unit"] = item["name"], item["unit"]
        entry["points"].update(item["points"])
    return stored


def latest_values(history):
    """Most recent value per object_id in a history_values()/merge_history() dict."""
    latest = {}
    for object_id, item in history.items():
        if not item["points"]:
            continue
        time = max(item["points"])
        latest[object_id] = {"name": item["name"], "value": item["points"][time], "unit": item["unit"], "time": time}
    return latest


def _series(item):
    return [[time, value] for time, value in sorted(item["points"].items())] if item else []


def strength_index(history):
    """Krachttest index per strength-test moment: [(iso time, index)], 100 = first test.

    At each moment: the average over the machines of last test / first test, times 100. Every machine
    weighs the same, whatever its weight. A machine tested for the first time later joins at 100.
    """
    series = {
        object_id: sorted(item["points"].items())
        for object_id, item in history.items() if object_id.startswith("kracht_") and item["points"]
    }
    result = []
    for time in sorted({t for points in series.values() for t, _ in points}):
        ratios = []
        for points in series.values():
            past = [value for t, value in points if t <= time]
            if past and points[0][1]:
                ratios.append(past[-1] / points[0][1])
        if ratios:
            result.append((time, round(sum(ratios) / len(ratios) * 100, 1)))
    return result


def _strength_by_machine(history):
    return {
        item["name"].removeprefix("Krachttest "): sorted(item["points"].items())
        for object_id, item in history.items() if object_id.startswith("kracht_") and item["points"]
    }


def intensity(history):
    """Training weight as % of the strength test in effect at each session: {oefening_X: (name, [(time, pct)])}.

    The weight is the heaviest set of the session; the test in effect is the last one at or before the
    session hour (EGYM runs the test at the start of a session, in the same hour). Sessions before the
    first test of a machine are left out.
    """
    tests = _strength_by_machine(history)
    result = {}
    for object_id, item in history.items():
        if not (object_id.startswith("oefening_") and object_id.endswith("_gewicht")):
            continue
        machine = item["name"].removeprefix("Training ").removesuffix(" gewicht")
        machine_tests = tests.get(machine)
        if not machine_tests:
            continue
        points = []
        for time, weight in sorted(item["points"].items()):
            in_effect = [value for t, value in machine_tests if t <= time]
            if in_effect and in_effect[-1]:
                points.append((time, round(weight / in_effect[-1] * 100, 1)))
        if points:
            result[object_id.removesuffix("_gewicht")] = (machine, points)
    return result


def session_intensity(per_machine):
    """Average intensity over the machines trained per session: [(time, pct)]."""
    by_time = {}
    for _machine, points in per_machine.values():
        for time, pct in points:
            by_time.setdefault(time, []).append(pct)
    return [(time, round(sum(v) / len(v), 1)) for time, v in sorted(by_time.items())]


def band_position(pct, low, high):
    """Where pct lies in the training band: 0 at the bottom, 100 at the top, clipped."""
    return round(min(max((pct - low) / (high - low) * 100, 0), 100))


def derived_statistics(history):
    """Statistics computed from the stored history: Krachttest index and intensity per machine and session."""
    result = {}
    for time, value in strength_index(history):
        _add(result, f"{DOMAIN}:krachttest_index", "Krachttest index", "%", None, datetime.datetime.fromisoformat(time), [value])
    per_machine = intensity(history)
    for key, (machine, points) in per_machine.items():
        for time, pct in points:
            _add(result, f"{DOMAIN}:{key}_intensiteit", f"Training {machine} intensiteit", "%", None,
                 datetime.datetime.fromisoformat(time), [pct])
    for time, pct in session_intensity(per_machine):
        _add(result, f"{DOMAIN}:training_intensiteit", "Training intensiteit", "%", None, datetime.datetime.fromisoformat(time), [pct])
    return _finish(result)


def sessions_per_week(history, now):
    """(sessions this week, average sessions per week over the last 4 weeks), counted as training days.

    now is an aware datetime in the local time zone; weeks start on Monday.
    """
    days = {
        datetime.datetime.fromisoformat(t).astimezone(now.tzinfo).date()
        for object_id, item in history.items() if object_id.startswith("oefening_") and object_id.endswith("_gewicht")
        for t in item["points"]
    }
    today = now.date()
    week_start = today - datetime.timedelta(days=today.weekday())
    this_week = sum(1 for d in days if week_start <= d <= today)
    last_28 = sum(1 for d in days if today - datetime.timedelta(days=27) <= d <= today)
    return this_week, round(last_28 / 4, 1)


def progress_sensors(history, now, band=(40, 65)):
    """Sensors for the Krachttest index, training intensity and training frequency."""
    sensors = {}
    index = strength_index(history)
    if index:
        growth = {machine: round((points[-1][1] / points[0][1] - 1) * 100, 1)
                  for machine, points in _strength_by_machine(history).items() if points[0][1]}
        sensors["krachttest_index"] = _sensor(
            "Krachttest index", index[-1][1], "%", "mdi:chart-line-variant",
            {
                "gemeten_op": index[-1][0],
                "groei_per_toestel_pct": dict(sorted(growth.items())),
                "verloop": [[time, value] for time, value in index],
            },
            measurement=False,
        )
    per_machine = intensity(history)
    sessions = session_intensity(per_machine)
    if sessions:
        low, high = band
        time, pct = sessions[-1]
        latest = {machine: points[-1][1] for machine, points in per_machine.values() if points[-1][0] == time}
        sensors["training_intensiteit"] = _sensor(
            "Training intensiteit", pct, "%", "mdi:speedometer",
            {
                "gemeten_op": time,
                "positie_in_band_pct": band_position(pct, low, high),
                "band_ondergrens": low,
                "band_bovengrens": high,
                "per_toestel": dict(sorted(latest.items())),
                "verloop": [[t, v] for t, v in sessions],
            },
            measurement=False,
        )
    this_week, per_week = sessions_per_week(history, now)
    sensors["training_sessies_deze_week"] = _sensor("Training sessies deze week", this_week, "sessies", "mdi:calendar-week")
    sensors["training_sessies_per_week"] = _sensor("Training sessies per week", per_week, "sessies", "mdi:calendar-sync",
                                                   {"periode": "laatste 4 weken"})
    return sensors


def latest_sensors(history, band=(40, 65)):
    """Sensors with the last value per exercise, machine and body metric; only height starts disabled.

    Training sensors also carry their whole history as the attribute "sessies", and the gewicht sensor
    the strength tests of the same machine as "krachttest", so one chart per machine can show both.
    """
    strength_by_machine = {
        item["name"].removeprefix("Krachttest "): item
        for object_id, item in history.items() if object_id.startswith("kracht_")
    }
    per_machine = intensity(history)
    sensors = {}
    for object_id, item in latest_values(history).items():
        if object_id.startswith("oefening_") and object_id.endswith("_volume"):
            continue  # per-exercise volume stays a statistic only, to keep the sensor list short
        attrs = {"gemeten_op": item["time"]}
        if object_id.startswith("oefening_"):
            icon = "mdi:repeat" if object_id.endswith("_herhalingen") else "mdi:weight-kilogram"
            attrs["sessies"] = _series(history[object_id])
            if object_id.endswith("_gewicht"):
                machine = item["name"].removeprefix("Training ").removesuffix(" gewicht")
                attrs["krachttest"] = _series(strength_by_machine.get(machine))
                machine_intensity = per_machine.get(object_id.removesuffix("_gewicht"))
                if machine_intensity:
                    # Training weight as % of the strength test in effect: the knob a member can turn
                    attrs["pct_van_krachttest"] = machine_intensity[1][-1][1]
                    attrs["positie_in_band_pct"] = band_position(machine_intensity[1][-1][1], *band)
                    attrs["intensiteit"] = [[t, v] for t, v in machine_intensity[1]]
        elif object_id == "training_volume_totaal":
            icon = "mdi:weight-lifter"
            attrs["sessies"] = _series(history[object_id])
        elif object_id.startswith("kracht_"):
            icon = "mdi:arm-flex"
            points = sorted(history[object_id]["points"].items())
            first_time, first = points[0]
            attrs.update({
                "nulmeting": first,
                "nulmeting_op": first_time,
                "verandering_kg": round(item["value"] - first, 1),
                "verandering_pct": round((item["value"] - first) / first * 100, 1) if first else None,
                "aantal_metingen": len(points),
            })
        else:
            icon = "mdi:human"
        # Height hardly changes for adults; everything else is measured again at the Fitness Hub
        enabled = not object_id.startswith("lichaam_height")
        # No state class: the history of these values already exists as statistics with the right dates
        sensors[object_id] = _sensor(
            item["name"], item["value"], item["unit"], icon, attrs, measurement=False, enabled=enabled,
        )
    return sensors


_ORDERED = re.compile(r"^(Training|Krachttest) (.+?)(?: (gewicht|herhalingen|volume|intensiteit))?$")


def parse_order(text):
    """'1 Leg Press, 2 Seated Row' or one per line -> {"leg press": 1, "seated row": 2}.

    Leading numbers, dots and an 'EGYM ' prefix are ignored; the position in the list counts.
    """
    names = [
        re.sub(r"^\d+[.)]?\s*", "", part.strip()).removeprefix("EGYM ").strip()
        for part in re.split(r"[,\n;]", text or "")
    ]
    return {name.lower(): position for position, name in enumerate((n for n in names if n), start=1)}


def ordered_machine(machine, positions):
    """'Leg Press' -> '1 Leg Press' when it is in the order, padded to the same width."""
    position = positions.get(machine.lower())
    if position is None:
        return machine
    return f"{position:0{len(str(len(positions)))}d} {machine}"


def ordered_name(name, positions):
    """Put the machine number in a statistic or sensor name: 'Training Leg Press gewicht' -> 'Training 1 Leg Press gewicht'."""
    match = _ORDERED.match(name)
    if not positions or not match or match.group(2).lower() not in positions:
        return name
    group, machine, suffix = match.groups()
    return " ".join(part for part in (group, ordered_machine(machine, positions), suffix) if part)


def apply_order(sensors, statistics, positions):
    """Numbered names for sensors and statistics, and per-machine attributes sorted in gym order."""
    if not positions:
        return
    for stat in statistics.values():
        stat["name"] = ordered_name(stat["name"], positions)
    for sensor in sensors.values():
        sensor["name"] = ordered_name(sensor["name"], positions)
        attrs = sensor.get("attrs") or {}
        for key in ("per_toestel", "groei_per_toestel_pct"):
            if isinstance(attrs.get(key), dict):
                renamed = {ordered_machine(machine, positions): value for machine, value in attrs[key].items()}
                attrs[key] = dict(sorted(renamed.items()))
        number = re.match(r"^(?:Training|Krachttest) (\d+) ", sensor["name"])
        if number:
            attrs["volgnummer"] = int(number.group(1))
            sensor["attrs"] = attrs
