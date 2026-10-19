# EGYM for Home Assistant

An unofficial Home Assistant integration for the EGYM Fitness app. It is not affiliated with or endorsed by EGYM.

It reads your EGYM account and keeps the history in Home Assistant's long-term statistics, with the date of the training or measurement itself, so you can follow your progress in a statistics graph.

## What you get

**Long-term statistics** (history, per person):

| Statistic | Example id | Content |
| --- | --- | --- |
| Training weight per exercise | `egym:marcel_oefening_581_gewicht` | Mean, min and max weight over the sets of a session (kg) |
| Repetitions per exercise | `egym:marcel_oefening_581_herhalingen` | Total repetitions of a session |
| Strength test per machine | `egym:marcel_kracht_1002` | Strength value from the machine's strength test (kg) |
| Body composition | `egym:marcel_lichaam_weight_kg` | Weight, BMI, body fat, muscle mass, visceral fat and more from the Fitness Hub |

**Sensors** (current value): bio age (total, muscles, upper body, core, lower body, metabolic, cardio, flexibility), activity points and level, and muscle balance per muscle pair with its optimal range.

Data is fetched every 6 hours and when Home Assistant starts. The first sync fetches everything since 2019.

## Installation

### HACS

1. HACS → ⋮ → Custom repositories → add `https://github.com/ganzewin/ha-egym`, type *Integration*.
2. Install **EGYM** and restart Home Assistant.

### Manual

Copy `custom_components/egym` to `/config/custom_components/egym` and restart Home Assistant.

## Setup

Settings → Devices & services → Add integration → **EGYM**.

- **Email / password**: your EGYM Fitness app login.
- **Name**: used in the statistic ids, statistic names and the device, for example `Marcel`. Add the integration once per person to track several people in one Home Assistant.
- **Gym address**: leave empty to look it up from your email address. If that fails, enter your gym's Netpulse address, for example `https://yourgym.netpulse.com`.

## Dashboard example

```yaml
type: statistics-graph
title: Strength per machine
period: day
days_to_show: 180
chart_type: line
stat_types: [max]
entities:
  - egym:marcel_kracht_1002
  - egym:marcel_kracht_998
```

Strength tests and workouts use different activity ids for the same machine; the statistic names show which machine is which.

## How it works

The integration bundles the [python-egym](https://github.com/marcelpoelstra/python-egym) connector by Marcel Poelstra in `custom_components/egym/egym_api`, unchanged and under its own GPL-3.0 license. Problems with the EGYM API itself belong there; problems with the Home Assistant side belong in this repository. EGYM does not document this API for members, so it can change without notice.

## Development

```bash
python3.14 -m venv .venv && source .venv/bin/activate
pip install -r requirements_test.txt
pytest
```

The tests run against a real Home Assistant with made-up data; they never contact EGYM.

## License

GPL-3.0, see [LICENSE](LICENSE).
