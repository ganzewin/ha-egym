# EGYM for Home Assistant

An unofficial Home Assistant integration for the EGYM Fitness app. It is not affiliated with or endorsed by EGYM.

It reads your EGYM account and keeps the history in Home Assistant's long-term statistics, with the date of the training or measurement itself, so you can follow your progress in a statistics graph.

## What you get

**Long-term statistics** (history, per person; `<name>` is explained under [Setup](#setup)):

| Statistic | Example id | Content |
| --- | --- | --- |
| Training weight per exercise | `egym:<name>_oefening_581_gewicht` | Mean, min and max weight over the classic sets of a session (kg) |
| Repetitions per exercise | `egym:<name>_oefening_581_herhalingen` | Total repetitions of the classic sets of a session |
| Eccentric weight and repetitions | `egym:<name>_oefening_581_excentrisch_gewicht`, `..._excentrisch_herhalingen` | The same for the eccentric sets |
| Strength test per machine | `egym:<name>_kracht_1002` | Strength value from the machine's strength test (kg) |
| Volume per exercise | `egym:<name>_oefening_581_volume` | Weight × repetitions, summed over all sets of a session, classic and eccentric (kg) |
| Total volume | `egym:<name>_training_volume_totaal` | Volume of all exercises of a session (kg) |
| Strength index | `egym:<name>_krachttest_index` | Krachttest index at every strength test, see [Progress](#progress) |
| Intensity per exercise | `egym:<name>_oefening_581_intensiteit` | Training weight as % of the strength test in effect, per session |
| Intensity per session | `egym:<name>_training_intensiteit` | Average intensity over the machines of a session |
| Body composition | `egym:<name>_lichaam_weight_kg` | Weight, BMI, body fat, muscle mass, visceral fat and more from the Fitness Hub |

**Sensors**, all under one device `EGYM <name>`. Their names start with a group word, so they sort per group:

| Group | Sensors |
| --- | --- |
| Activiteit | points, goal, progress towards the goal (%), points to keep the level, days left, level |
| Bio-leeftijd | total, muscles, upper body, core, lower body, metabolic, cardio, flexibility |
| Krachttest | strength index; last strength test per machine, with first test and change as attributes |
| Lichaam | last body composition values from the Fitness Hub (height starts disabled) |
| Spierbalans | balance per muscle pair, with the optimal range as attributes |
| Training | intensity of the last session; per exercise: weight of the heaviest set and total repetitions of the last session; total volume of the last session; sessions this week and per week |

Krachttest, Lichaam and Training sensors show the last measured value, with its time in the attribute `gemeten_op`; their history is in the statistics above, so these sensors have no state class on purpose. New exercises get a sensor after the next sync. Entities that were disabled before keep their setting after an update.

Data is fetched every 6 hours and when Home Assistant starts. The first sync fetches everything since 2019.

## Progress

EGYM sets the training weight from the strength test of each machine. In the strength endurance programme the weight lies between 40 and 65% of that test, with a fixed 20 repetitions per set. After a strength test you can raise the weight yourself on the machine to train harder until the next test. That weight is the one thing a member controls, so the integration measures it:

- **Training intensiteit**: training weight (heaviest set) as % of the strength test in effect at that session, averaged over the machines of the last session. Attributes: `positie_in_band_pct` (0 = 40%, 100 = 65%), `per_toestel` and `verloop`. Per machine it is the attribute `pct_van_krachttest` on the Training gewicht sensor, with `positie_in_band_pct`, with its course as `intensiteit`, and a statistic per exercise. After a new strength test the intensity drops back, because the same weight is a smaller share of a higher test; within a cycle it should rise.
- **Krachttest index**: the result. Per machine the last strength test divided by the first, averaged over the machines, times 100: every machine weighs the same. 100 is where you started. A machine tested for the first time later joins at 100. Attribute `groei_per_toestel_pct`.
- **Krachttest per machine**: attributes `nulmeting`, `nulmeting_op`, `verandering_kg`, `verandering_pct` (since the first test) and `aantal_metingen`.
- **Volume**: weight × repetitions per exercise and per session, a measure of how much work a session was.
- **Training sessies deze week / per week**: training days this week (from Monday) and on average over the last 4 weeks. They are recalculated at every sync, so a new week shows within 6 hours.

The band of 40–65% is set in `const.py` (`TRAINING_BAND`) for the strength endurance programme; other EGYM programmes use other ranges.

### Training methods

EGYM stores the method per set: `REGULAR_REPBASED` (classic) and `NEGATIVE_REPBASED` (eccentric). The Training gewicht and herhalingen sensors, the intensity and the band position use only the classic sets, so they stay comparable from session to session. The eccentric sets are kept apart: as statistics (`..._excentrisch_gewicht`, `..._excentrisch_herhalingen`) and as attributes `excentrisch` (last value) and `excentrisch_sessies` (course) on the classic sensors of the same exercise. Volume counts all sets. Another method that EGYM may use gets its own label in the same way, taken from its name.

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
- **Machine order** (optional): the machines in the order of your gym's circuit, one per line, for example `Leg Press`, `Seated Row`, `Leg Curl`. Numbers in front and an `EGYM ` prefix are ignored, so a list copied from elsewhere works. The machines then get their number in their names: `Training 1 Leg Press gewicht`, `Krachttest 8 Chest Press`, so sensor lists, chart pickers and the attributes `per_toestel` and `groei_per_toestel_pct` follow the gym order. Training and Krachttest gewicht sensors get the attribute `volgnummer`.

The order can be changed later under Settings → Devices & services → EGYM → Configure. Names follow right away; entity IDs are only set when an entity is created, so they contain the number only when the order was filled in when adding the integration. Statistic ids never contain the number, so charts keep working when the order changes.

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

The Krachttest index and Training intensiteit sensors have their course as the attribute `verloop`, for a chart in the same way:

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
