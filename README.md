# EGYM for Home Assistant

An unofficial Home Assistant integration for the EGYM Fitness app. It is not affiliated with or endorsed by EGYM.

It reads your EGYM account and keeps the history in Home Assistant's long-term statistics, with the date of the training or measurement itself, so you can follow your progress in a statistics graph.

## What you get

**Long-term statistics** (history, per person; `<name>` is explained under [Setup](#setup)):

| Statistic | Example id | Content |
| --- | --- | --- |
| Training weight per exercise | `egym:<name>_oefening_581_gewicht` | Mean, min and max weight over the sets of a session (kg) |
| Repetitions per exercise | `egym:<name>_oefening_581_herhalingen` | Total repetitions of a session |
| Strength test per machine | `egym:<name>_kracht_1002` | Strength value from the machine's strength test (kg) |
| Body composition | `egym:<name>_lichaam_weight_kg` | Weight, BMI, body fat, muscle mass, visceral fat and more from the Fitness Hub |

**Sensors**, all under one device `EGYM <name>`. Their names start with a group word, so they sort per group:

| Group | Sensors |
| --- | --- |
| Activiteit | points, goal, progress towards the goal (%), points to keep the level, days left, level |
| Bio-leeftijd | total, muscles, upper body, core, lower body, metabolic, cardio, flexibility |
| Krachttest | last strength test per machine |
| Lichaam | last body composition values from the Fitness Hub (height starts disabled) |
| Spierbalans | balance per muscle pair, with the optimal range as attributes |
| Training | per exercise: weight of the heaviest set and total repetitions of the last session |

Krachttest, Lichaam and Training sensors show the last measured value, with its time in the attribute `gemeten_op`; their history is in the statistics above, so these sensors have no state class on purpose. New exercises get a sensor after the next sync. Entities that were disabled before keep their setting after an update.

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
- **Name**: the person this account belongs to, for example `Daan`. Add the integration once per person to track several people in one Home Assistant.
- **Gym address**: leave empty to look it up from your email address. If that fails, enter your gym's Netpulse address, for example `https://yourgym.netpulse.com`.

### The name in ids and entities

If you leave **Name** empty, the part of your email address before the `@` is used. The name is written in lowercase with underscores for the ids:

| Name entered | Statistic id | Device | Sensor |
| --- | --- | --- | --- |
| `Daan` | `egym:daan_kracht_1002` | EGYM Daan | `sensor.egym_daan_bio_leeftijd` |
| `Daan Jansen` | `egym:daan_jansen_kracht_1002` | EGYM Daan Jansen | `sensor.egym_daan_jansen_bio_leeftijd` |
| *(empty)*, email `daan.jansen@example.com` | `egym:daan_jansen_kracht_1002` | EGYM daan.jansen | `sensor.egym_daan_jansen_bio_leeftijd` |

To see which name an account uses, open Settings → Devices & services → EGYM: the name is the title of the entry. In a statistics graph card, type `egym:` to list all EGYM statistics.

The name is set once, when you add the integration. To change it, remove the integration and add it again; statistics under the old name stay until you delete them in Developer tools → Statistics.

## Dashboard example

```yaml
type: statistics-graph
title: Strength per machine
period: day
days_to_show: 180
chart_type: line
stat_types: [max]
entities:
  - egym:daan_kracht_1002   # replace daan with your name
  - egym:daan_kracht_998
```

Use `chart_type: line`: a bar chart stacks the machines on top of each other, which adds up weights that do not belong together.

A Krachttest statistic only gets a point when the machine runs a strength test, which EGYM does now and then, not every session. The Training statistics get a point every session.

Strength tests and workouts use different activity ids for the same machine; the statistic names show which machine is which.

### Progress per machine with ApexCharts

The Training gewicht sensors carry their history as attributes: `sessies` (heaviest set per session) and `krachttest` (the strength tests of the same machine). With [apexcharts-card](https://github.com/RomRider/apexcharts-card) that gives one chart per machine, with the strength test as a stepped baseline and the training weight per session as a line:

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Leg Press
  show_states: true
  colorize_states: true
graph_span: 90d
span:
  end: day
yaxis:
  - min: 0
    decimals: 0
series:
  - entity: sensor.egym_daan_training_leg_press_gewicht   # replace daan with your name
    name: Training
    curve: straight
    stroke_width: 3
    extend_to: false
    data_generator: |
      return (entity.attributes.sessies || []).map(p => [new Date(p[0]).getTime(), p[1]]);
  - entity: sensor.egym_daan_training_leg_press_gewicht
    name: Krachttest
    curve: stepline
    stroke_width: 2
    stroke_dash: 6
    extend_to: now
    show:
      in_header: false
    data_generator: |
      return (entity.attributes.krachttest || []).map(p => [new Date(p[0]).getTime(), p[1]]);
```

These attributes are not written to the recorder; the statistics already hold the same history.

## Icon

The integration brings its own icon in `custom_components/egym/brand/`. Home Assistant shows it on the integration and device pages. It is an original image, not the EGYM logo.

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
