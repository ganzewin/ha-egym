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
| Volume per exercise | `egym:<name>_oefening_581_volume` | Weight × repetitions, summed over the sets of a session (kg) |
| Total volume | `egym:<name>_training_volume_totaal` | Volume of all exercises of a session (kg) |
| Strength index | `egym:<name>_krachttest_index` | Krachttest index at every strength test, see [Progress](#progress) |
| Body composition | `egym:<name>_lichaam_weight_kg` | Weight, BMI, body fat, muscle mass, visceral fat and more from the Fitness Hub |

**Sensors**, all under one device `EGYM <name>`. Their names start with a group word, so they sort per group:

| Group | Sensors |
| --- | --- |
| Activiteit | points, goal, progress towards the goal (%), points to keep the level, days left, level |
| Bio-leeftijd | total, muscles, upper body, core, lower body, metabolic, cardio, flexibility |
| Krachttest | strength index; last strength test per machine, with first test and change as attributes |
| Lichaam | last body composition values from the Fitness Hub (height starts disabled) |
| Spierbalans | balance per muscle pair, with the optimal range as attributes |
| Training | per exercise: weight of the heaviest set and total repetitions of the last session; total volume of the last session; sessions this week and per week |

Krachttest, Lichaam and Training sensors show the last measured value, with its time in the attribute `gemeten_op`; their history is in the statistics above, so these sensors have no state class on purpose. New exercises get a sensor after the next sync. Entities that were disabled before keep their setting after an update.

Data is fetched every 6 hours and when Home Assistant starts. The first sync fetches everything since 2019.

## Progress

EGYM sets the training weight from the strength test of each machine, as a share of that test (roughly 40–60%, depending on machine and programme). The strength test is therefore the measure of progress; the training weight follows it.

- **Krachttest index**: the sum of the last strength test of every machine, divided by the sum of their first tests, times 100. 100 is where you started; 118 means 18% stronger over all machines together. A machine tested for the first time later joins with its own first test as baseline, so it does not make the index jump. Machines with a high weight, such as the leg press, weigh more in the sum.
- **Krachttest per machine**: attributes `nulmeting`, `nulmeting_op`, `verandering_kg`, `verandering_pct` (since the first test) and `aantal_metingen`.
- **Training gewicht**: attribute `pct_van_krachttest`, the training weight as a share of the last strength test of the same machine.
- **Volume**: weight × repetitions per exercise and per session, a measure of how much work a session was.
- **Training sessies deze week / per week**: training days this week (from Monday) and on average over the last 4 weeks. They are recalculated at every sync, so a new week shows within 6 hours.

Muscle balance between opposing machines, such as leg extension and leg curl, comes from EGYM itself in the Spierbalans sensors.

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

The Krachttest index sensor has its course as the attribute `verloop`, for a chart in the same way:

```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Krachttest index
  show_states: true
graph_span: 180d
span:
  end: day
series:
  - entity: sensor.egym_daan_krachttest_index   # replace daan with your name
    name: Index
    curve: stepline
    stroke_width: 3
    extend_to: now
    data_generator: |
      return (entity.attributes.verloop || []).map(p => [new Date(p[0]).getTime(), p[1]]);
```

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
