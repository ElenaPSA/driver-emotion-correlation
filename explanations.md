# Explanations: simulated session and correlation analysis

This document explains the original example session in
[`examples/simulated_session.jsonl`](examples/simulated_session.jsonl), the
less directly coupled session in
[`examples/not_obvious_session.jsonl`](examples/not_obvious_session.jsonl), and
their generated analysis reports. These are **synthetic test data**, not
recordings from a real driver or emotion detections made by the webcam.

## Not-obvious simulation results

This is the newer, less directly coupled example. Its files are
[`examples/not_obvious_session.jsonl`](examples/not_obvious_session.jsonl) and
[`examples/not_obvious_analysis.json`](examples/not_obvious_analysis.json).
The qualitative, event-by-event output is
[`examples/not_obvious_timeline.md`](examples/not_obvious_timeline.md).
It was produced and analyzed with:

```powershell
driver-emotion-correlation simulate --profile not-obvious `
  --output examples\not_obvious_session.jsonl --seconds 1200 --seed 20261013

driver-emotion-correlation analyze examples\not_obvious_session.jsonl `
  --bucket-seconds 1 --lag-seconds 0 --min-pairs 30 `
  --output examples\not_obvious_analysis.json

driver-emotion-correlation explain examples\not_obvious_session.jsonl `
  --bucket-seconds 1 --output examples\not_obvious_timeline.md
```

### How this simulation differs

It spans **1,200 seconds (20 minutes)** with 1,200 emotion and 1,200 driving
records, producing **1,200 matched buckets** and 45 emotion-label changes
among 1,199 adjacent bucket pairs. Each label occurs in 300 buckets. Emotion
labels are shuffled into 20-second blocks. A driving style is sampled every
five seconds from an emotion-specific probability distribution, independently
of the other five-second driving blocks. The probabilities are designed only
to make crossed emotion/style pairs plausible in the test data:

| Emotion | Calm style | Balanced style | Assertive style | Aggressive style |
| --- | ---: | ---: | ---: | ---: |
| angry | 52% | 30% | 13% | 5% |
| happy | 5% | 15% | 34% | 46% |
| neutral | 43% | 34% | 17% | 6% |
| stressed | 17% | 34% | 34% | 15% |

These are **simulation parameters, not measured psychological facts**. For the
fixed seed used here, the actual observed driving-style counts were:

| Emotion (300 buckets each) | Calm | Balanced | Assertive | Aggressive |
| --- | ---: | ---: | ---: | ---: |
| angry | 145 (48.3%) | 100 (33.3%) | 35 (11.7%) | 20 (6.7%) |
| happy | 10 (3.3%) | 45 (15.0%) | 90 (30.0%) | 155 (51.7%) |
| neutral | 130 (43.3%) | 95 (31.7%) | 50 (16.7%) | 25 (8.3%) |
| stressed | 45 (15.0%) | 70 (23.3%) | 140 (46.7%) | 45 (15.0%) |

This includes both examples you asked for: angry observations were usually
paired with calm/balanced driving, while happy observations were usually paired
with assertive/aggressive driving. It is still an intentional probabilistic
relationship, not naturally observed data.

### Correlation of each signal with each emotion

The application calculates the same one-versus-rest Spearman association for
each numeric driving feature. These are the results from the checked-in report;
each cell is rho (`+` means higher feature ranks coincide with that emotion
label more often relative to other labels, `-` means lower ranks):

| Driving feature | Angry | Happy | Neutral | Stressed |
| --- | ---: | ---: | ---: | ---: |
| `hard_corner_per_100km` | -0.329 | +0.466 | -0.265 | +0.127 |
| `aggressiveness_level` | -0.326 | +0.450 | -0.253 | +0.129 |
| `headway_mean_s` | +0.326 | -0.449 | +0.249 | -0.126 |
| `harsh_accel_per_100km` | -0.324 | +0.457 | -0.252 | +0.119 |
| `tailgating_time_share` | -0.324 | +0.463 | -0.260 | +0.122 |
| `style_index` | -0.324 | +0.458 | -0.251 | +0.116 |
| `speed_mean_kmh` | -0.323 | +0.447 | -0.246 | +0.121 |
| `jerk_max_mps3` | -0.321 | +0.453 | -0.254 | +0.122 |
| `speed_max_kmh` | -0.321 | +0.458 | -0.268 | +0.131 |
| `harsh_brake_per_100km` | -0.321 | +0.459 | -0.253 | +0.114 |
| `speeding_distance_share` | -0.314 | +0.458 | -0.258 | +0.114 |
| `jerk_mean_mps3` | -0.305 | +0.459 | -0.264 | +0.109 |

For additional context, the generated **mean values** by emotion are:

| Emotion | Mean speed (km/h) | Aggressiveness (0–1) | Harsh braking / 100 km | Speeding distance share | Tailgating time share | Mean headway (s) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| angry | 55.081 | 0.368 | 2.941 | 0.130 | 0.087 | 1.944 |
| happy | 77.788 | 0.738 | 9.328 | 0.418 | 0.259 | 1.264 |
| neutral | 57.273 | 0.401 | 3.459 | 0.153 | 0.099 | 1.878 |
| stressed | 67.969 | 0.590 | 6.078 | 0.275 | 0.169 | 1.543 |

Within this particular synthetic run, the clearest state-level pattern is:
**happy** has the strongest positive associations with the aggressive-driving
features (top: cornering rate, rho `+0.466`), while **angry** has negative
associations with those features (top inverse: cornering rate, rho `-0.329`)
and a positive association with longer mean headway (`+0.326`). The happy
association is somewhat stronger than the angry association; these are not
perfect one-to-one mappings because driving modes were sampled probabilistically.
Neutral associations are modestly negative, and stressed associations are
small and positive in this generated sample.

The numeric driving features also correlate with one another because they
share the sampled driving-style mode. The similar coefficients therefore do
not establish which particular signal is uniquely associated with emotion
after accounting for the other signals.

### Signal changes at emotion-label transitions

The program's `emotion_transition` correlation relates **absolute changes** in
each signal between adjacent buckets to whether the emotion label changed.
`emotion_transition_direction` relates **signed changes** (up or down) to
whether a label changed. The report's transition sample contains 1,199 adjacent
pairs:

| Signal change | Absolute-change rho | Signed-change rho |
| --- | ---: | ---: |
| `tailgating_time_share` | +0.232 | +0.000 |
| `hard_corner_per_100km` | +0.224 | +0.009 |
| `harsh_accel_per_100km` | +0.220 | +0.015 |
| `jerk_mean_mps3` | +0.219 | +0.013 |
| `jerk_max_mps3` | +0.218 | +0.007 |
| `speed_mean_kmh` | +0.212 | -0.009 |
| `harsh_brake_per_100km` | +0.210 | +0.021 |
| `speeding_distance_share` | +0.204 | +0.012 |
| `aggressiveness_level` | +0.201 | +0.040 |
| `style_index` | +0.200 | +0.049 |
| `headway_mean_s` | +0.198 | -0.008 |
| `speed_max_kmh` | +0.196 | +0.001 |

**Conclusion for transitions:** the largest result is a modest association
between an emotion-label change and the size of the tailgating-share change
(rho `+0.232`). Signed-change correlations are all close to zero (largest
absolute value `0.049`), so the simulation does not show a consistent signal
direction at emotion changes. Furthermore, the simulator deliberately
re-samples driving mode when the emotion block changes; this can itself make
signal values shift near emotion transitions. These values cannot establish
that vehicle signals precede or cause emotion changes.

These are descriptive correlations only. The report does not calculate
confidence intervals, p-values, or adjusted/multivariable feature importance.
Repeated one-second buckets are not independent observations.

## What “when and why” can be concluded

The qualitative timeline gives each label transition's **session-relative
bucket time**, the previous and new labels, and the signal fields with a
noticeable shift between adjacent matched buckets. For this simulation,
emotion-label changes occur in the following one-second buckets:

`00:20`, `00:40`, `01:00`, `01:20`, `02:00`, `02:20`, `03:00`, `03:20`,
`04:00`, `04:20`, `04:40`, `05:00`, `05:20`, `05:40`, `06:00`, `06:20`,
`06:40`, `07:00`, `07:20`, `07:40`, `08:00`, `08:20`, `08:40`, `09:00`,
`09:20`, `09:40`, `10:00`, `10:20`, `10:40`, `11:00`, `11:20`, `11:40`,
`12:00`, `12:20`, `12:40`, `13:00`, `13:20`, `13:40`, `14:00`, `14:20`,
`14:40`, `15:00`, `15:20`, `15:40`, `16:00`.

These times identify the one-second receipt-time bucket containing the changed
emotion detection; they do not provide subsecond onset time or physiological
ground truth. For example, the first transition is
`angry → stressed` around `00:20`; the timeline says which signals shifted in
the neighboring driving records. At `03:00`, only peak and average speed were
large enough to be described as shifting in that adjacent sample. Other
transitions show several co-moving profiler fields, and two have no notable
signal shift by the report's qualitative filter.

**The timeline cannot determine “why” or which signal provoked the emotion.**
It checks signals in the same/current receipt-time bucket against the previous
matched bucket. This establishes only temporal co-occurrence at the available
sampling resolution; it does not prove that a signal changed first. The signal
changes could follow the emotion label, be caused by a third factor, or reflect
the simulation's design. Even when only one feature is listed as changing, that
does not establish it as the cause.

For the live project, this limitation is stronger: many fields published in
`DrivingStyleProfile` are session/cumulative summaries rather than raw
per-frame inputs. To investigate which vehicle signal precedes a real emotion
change, record synchronized short-window or per-frame speed, acceleration,
braking, cornering, jerk, headway, and emotion-confidence data, then compare
candidate driving changes from before the emotion transition. Establishing
causation requires a controlled study; co-occurrence alone is insufficient.

## What “session” means in the original obvious fixture

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
