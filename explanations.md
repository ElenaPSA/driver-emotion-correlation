# Explanations: simulated session and correlation analysis

This document explains the example session in
[`examples/simulated_session.jsonl`](examples/simulated_session.jsonl) and the
report produced from it in
[`examples/simulated_analysis.json`](examples/simulated_analysis.json).
These are **synthetic test data**, not recordings from a real driver or
emotion detections made by the webcam.

## What “session” means here

A session is one continuous collection/replay of paired emotion and driving
events. This example session spans **240 seconds (four minutes)**. Each second
contains:

1. One simulated dominant-emotion observation, with a confidence between 0.84
   and 0.99.
2. One simulated driving-profile record containing numeric driving features.

That makes **240 emotion events and 240 driving events (480 events total)**.
Each event has a local `received_at` time, a `stream` name, its `data`, and
`"synthetic": true`. The emotion and driving records are placed in the same
one-second time bucket for comparison.

Here, “session” means the collected example drive. This is separate from the
profiler's `session` horizon, which means its cumulative profile for the current
trip (as opposed to its rolling `recent` profile). The checked-in synthetic
fixture is generated directly in the collector's event-log format; it does not
run a vehicle recording through the profiler.

The simulator repeats four deliberately linked scenarios in 20-second blocks:

| Simulated driving style | Simulated emotion | Example aggressiveness |
| --- | --- | ---: |
| calm | neutral | 0.12 |
| balanced | happy | 0.35 |
| assertive | stressed | 0.67 |
| aggressive | angry | 0.91 |

The four-block pattern repeats three times during the 240-second example.
Small deterministic jitter makes values vary within each block, while many
driving features still move together because they were generated from the same
scenario. The emotion label is assigned by the simulator; it is **not** inferred
from video or independently caused by a measured vehicle signal.

## What analysis is performed

The report uses **Spearman rank correlation** (`spearman_rho`) on one-second
receipt-time buckets. Spearman correlation compares the rank ordering of two
variables. Its value ranges from `-1` (opposite ordering), through `0` (no
monotonic association), to `+1` (same ordering).

The analysis uses these settings in this report:

| Setting | Value | Meaning |
| --- | ---: | --- |
| `bucket_seconds` | 1 | Events are grouped by one-second local receipt-time buckets. |
| `lag_seconds` | 0 | Driving and emotion buckets are compared without an additional time shift. |
| `max_gap_seconds` | 2 | A driving bucket farther than two seconds from the target time is not matched. |
| `min_confidence` | 0 | No emotion event is excluded by confidence in this example. |
| `matched_buckets` | 240 | Number of emotion buckets successfully paired with driving features. |

### Emotion-state rankings: `by_emotion`

For each emotion label, the analysis compares each driving feature with a
binary target: **this bucket has this label** versus **this bucket has another
label**. A positive rho means larger feature ranks are associated with the
named label relative to the other labels in this dataset; a negative rho means
smaller ranks are associated with it. This does not measure emotional intensity
or the probability that a signal caused an emotion.

There are 60 buckets for each label in the repeated simulation. The table below
lists every reported state association. Values are rho, rounded to three
decimals; all four columns use 240 paired buckets.

| Driving feature | Angry | Happy | Neutral | Stressed |
| --- | ---: | ---: | ---: | ---: |
| `tailgating_time_share` | +0.750 | -0.250 | -0.750 | +0.250 |
| `speeding_distance_share` | +0.750 | -0.250 | -0.750 | +0.250 |
| `aggressiveness_level` | +0.750 | -0.250 | -0.750 | +0.250 |
| `hard_corner_per_100km` | +0.750 | -0.250 | -0.750 | +0.250 |
| `harsh_accel_per_100km` | +0.750 | -0.250 | -0.750 | +0.250 |
| `harsh_brake_per_100km` | +0.750 | -0.250 | -0.750 | +0.250 |
| `headway_mean_s` | -0.750 | +0.250 | +0.750 | -0.250 |
| `jerk_max_mps3` | +0.750 | -0.250 | -0.750 | +0.250 |
| `jerk_mean_mps3` | +0.750 | -0.250 | -0.750 | +0.250 |
| `speed_max_kmh` | +0.750 | -0.250 | -0.750 | +0.250 |
| `speed_mean_kmh` | +0.750 | -0.250 | -0.750 | +0.250 |
| `style_index` | +0.750 | -0.250 | -0.750 | +0.250 |

These fields mean:

- `tailgating_time_share`: fraction of measured time classified as tailgating.
- `speeding_distance_share`: fraction of measured distance above the speed
  limit.
- `aggressiveness_level`: profiler style score on the 0–1 scale.
- `hard_corner_per_100km`, `harsh_accel_per_100km`, and
  `harsh_brake_per_100km`: event rates per 100 km.
- `headway_mean_s`: average following time headway, in seconds. Its negative
  sign for angry/aggressive scenarios means the synthetic angry blocks use
  shorter headway.
- `jerk_max_mps3` and `jerk_mean_mps3`: maximum and mean jerk in metres per
  second cubed.
- `speed_max_kmh` and `speed_mean_kmh`: maximum and mean speed in kilometres
  per hour.
- `style_index`: profiler's descriptive 0–100 index. It is not a validated
  driver-risk or emotion score.

### Emotion-transition rankings

The report also examines **whether the categorical emotion label changes
between two adjacent one-second buckets**. For each adjacent pair, it computes
the change in each driving feature and correlates that change with a binary
“emotion label changed” indicator:

- `emotion_transition`: correlations with the **absolute size** of the signal
  change, named `abs_change_<feature>`.
- `emotion_transition_direction`: correlations with the **signed** signal
  change, named `change_<feature>`; positive values mean an upward change tends
  to coincide with a label transition in this simulation, negative values a
  downward change.

This target means **any** label change; it does not distinguish, for example,
neutral-to-angry from happy-to-stressed, and it does not test whether a
particular feature change precedes an emotion change.

The transition comparison uses **239 adjacent pairs**. Its complete rankings
are:

| Signal change | Absolute-change rho | Signed-change rho |
| --- | ---: | ---: |
| `tailgating_time_share` | +0.363 | +0.231 |
| `speeding_distance_share` | +0.363 | +0.231 |
| `aggressiveness_level` | +0.363 | +0.231 |
| `hard_corner_per_100km` | +0.363 | +0.231 |
| `harsh_accel_per_100km` | +0.363 | +0.231 |
| `harsh_brake_per_100km` | +0.363 | +0.231 |
| `headway_mean_s` | +0.363 | -0.231 |
| `jerk_max_mps3` | +0.363 | +0.231 |
| `jerk_mean_mps3` | +0.363 | +0.231 |
| `speed_max_kmh` | +0.363 | +0.231 |
| `speed_mean_kmh` | +0.363 | +0.231 |
| `style_index` | +0.363 | +0.231 |

Transition correlations are smaller than the emotion-state correlations. In
this generated session there are only **11 label changes** among the 239
adjacent pairs, and the signal features change together at those scenario
boundaries. The similar values therefore should not be read as evidence that
one of these signals is uniquely important.

## Conclusions from this analysis

**For this synthetic input only:** the assigned `angry` label occurs in the
high-aggressiveness scenario. It is positively associated with higher
tailgating share, speeding share, aggressiveness, harsh-event rates, jerk,
speed and style index (rho about `+0.750`), and negatively associated with
mean headway (about `-0.750`). The `neutral` scenario has the reverse pattern.
The `happy` and `stressed` comparisons have smaller associations (about
`-0.250` and `+0.250` for the higher-is-more-aggressive fields), because each
label is one of four equally repeated ordered scenarios.

The run does **not** identify which signal causes or most strongly impacts a
real driver's emotion. Many predictors are deliberately driven by the same
simulated style level, producing tied or near-tied correlations. This is a
multicollinearity/confounding limitation: the ranking can show that features
co-vary with labels, but cannot separate their independent effects here. The
simulated emotion labels were also assigned from the scenario, rather than
detected from a person's face.

Use this report to confirm that the software joins event streams and produces
the expected association and transition outputs. For a real conclusion, collect
real emotion detections and time-aligned **per-frame or short-window vehicle
signals** across repeated drives. The profiler fields currently include
session-level summaries, which are coarse for second-by-second emotion changes.
Control for road, traffic, driver, and sensor conditions, and use an appropriate
repeated-measures or causal design before making claims about impact.
