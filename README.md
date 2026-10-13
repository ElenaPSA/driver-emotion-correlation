# Driver emotion correlation

This is a separate integration project for the workspace's
[`driver-emotion-mqtt`](../driver-emotion-mqtt/) and
[`driving-style-profiler`](../driving-style-profiler/) applications. It
subscribes to the emotion app's MQTT topic and receives the profiler's richer
diagnostic score stream over WebSocket. It does not change either application.

The collector stamps both streams with its local receipt time. This avoids
incorrectly treating the emotion app's process-relative camera timestamp and
the vehicle bus timestamp as if they shared a clock. Run the collector and both
publishers on the same computer and keep replay at real time when comparing
live emotion changes.

## Install

```powershell
cd C:\Users\U604618\Stellantis\driver-emotion-correlation
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

Use a Python version supported by both source projects (3.10 through 3.14).
The TensorFlow-backed emotion app may have narrower wheel availability on some
Python/OS combinations.

## Run the live collection

Start the collector first; it creates `outputs/session.jsonl` and listens for
profiler scores on port 8765:

```powershell
driver-emotion-correlation collect --data outputs\session.jsonl `
  --mqtt-host 127.0.0.1 --mqtt-port 1883 `
  --emotion-topic telemetry/DriverEmotionState `
  --ws-host 127.0.0.1 --ws-port 8765
```

Keep the emotion app running with its MQTT broker available on that same host
and port. Its default topic is `telemetry/DriverEmotionState`; override the
collector options if the broker or `MQTT_TOPIC` setting is different.

Run the profiler as usual, adding its full diagnostic output option (not just
the compact `DriverDrivingStyle` score server):

```powershell
cd C:\Users\U604618\Stellantis\driving-style-profiler
.\.venv\Scripts\Activate.ps1
driving-style-profiler serve --output ws://127.0.0.1:8765/score --no-mqtt
```

If the signal feed is already served by another WebSocket source, pass the same
`--source ws://host:port/stream` option you use for the profiler. Otherwise,
keep the profiler's existing signal input configuration. `--no-mqtt` is
optional; omit it if that process also needs to publish its score to the
existing MQTT consumer.

The collector writes one JSON object per line, with `stream`, local
`received_at`, and normalized `data`. The profiler must provide the full
`DrivingStyleProfile` diagnostic payload for per-signal analysis. A compact
aggressiveness-only payload is accepted if sent, but cannot identify which
underlying signal is associated with an emotion.

## Analyze

After collecting a drive:

```powershell
cd C:\Users\U604618\Stellantis\driver-emotion-correlation
.\.venv\Scripts\Activate.ps1
driver-emotion-correlation analyze outputs\session.jsonl `
  --bucket-seconds 1 --lag-seconds 0 --min-pairs 10 `
  --output outputs\analysis.json
```

The JSON report ranks driving-profile fields by absolute Spearman correlation
with each emotion (one-vs-rest) and with an emotion transition between
consecutive buckets. For emotion transitions, it separately ranks absolute
signal changes (`emotion_transition`) and signed changes
(`emotion_transition_direction`) between adjacent matched buckets. A positive
`--lag-seconds` compares driving measurements from earlier than the emotion
bucket, useful for checking whether signal changes tend to precede emotion
changes. `--min-confidence` can exclude low-confidence emotion detections.
Raise `--min-pairs` to avoid emphasizing rankings from very short drives.

Candidate fields include harsh acceleration/braking/cornering rates, speeding,
following/headway, speed and acceleration summaries, jerk, and profiler style
traits. The profiler's diagnostic record reports many fields as cumulative
session summaries; the analysis warns that these are coarse, not raw
per-frame measurements. Signals unavailable in a trip are omitted, not
silently replaced with zero.

## Run the synthetic end-to-end example

Generate a reproducible four-minute fixture with emotion labels deliberately
coupled to four changing driving styles:

```powershell
driver-emotion-correlation simulate `
  --output examples\simulated_session.jsonl --seconds 240 --seed 2026

driver-emotion-correlation analyze examples\simulated_session.jsonl `
  --bucket-seconds 1 --lag-seconds 0 --min-pairs 10 `
  --output examples\simulated_analysis.json
```

The checked-in [simulated input](examples/simulated_session.jsonl) contains 240
paired one-second samples (480 events); the [sample analysis report](examples/simulated_analysis.json)
was produced by the application's `analyze` command. Recreate it with the
commands above. The 240-second simulation cycles through neutral/calm, happy/balanced,
stressed/assertive, and angry/aggressive 20-second blocks three times. It adds
small deterministic measurement variation, while intentionally making multiple
driving fields co-vary with the same underlying style. See
[`explanations.md`](explanations.md) for the complete correlation tables and
an explanation of how to interpret them.

To test a less direct relationship in which angry states tend toward calm
driving and happy states tend toward faster, more assertive driving, generate
the additional 20-minute `not-obvious` fixture and analyze it:

```powershell
driver-emotion-correlation simulate --profile not-obvious `
  --output examples\not_obvious_session.jsonl --seconds 1200 --seed 20261013

driver-emotion-correlation analyze examples\not_obvious_session.jsonl `
  --bucket-seconds 1 --lag-seconds 0 --min-pairs 30 `
  --output examples\not_obvious_analysis.json

driver-emotion-correlation explain examples\not_obvious_session.jsonl `
  --bucket-seconds 1 --output examples\not_obvious_timeline.md
```

The resulting [input](examples/not_obvious_session.jsonl) and
[analysis](examples/not_obvious_analysis.json) are checked in. The
[qualitative transition timeline](examples/not_obvious_timeline.md) lists each
emotion-label change and the driving-signal shifts in adjacent samples. The
[explanation](explanations.md#not-obvious-simulation-results) discusses the
measured associations and clarifies that this remains a designed simulation,
not evidence about real drivers. A coincident signal shift is not proof that
the signal provoked the emotion change.

The checked-in run produced 240 matched buckets. These are the top example
state associations; features in the same style block move together:

| Simulated emotion | Matched buckets | Top association | Spearman ρ |
| --- | ---: | --- | ---: |
| angry | 240 | tailgating time share | +0.750 |
| happy | 240 | tailgating time share | -0.250 |
| neutral | 240 | tailgating time share | -0.750 |
| stressed | 240 | tailgating time share | +0.250 |

Speeding share, aggressiveness, harsh-event rates, jerk, and speed have nearly
the same absolute association in this deliberately coupled dataset. Mean
headway has the opposite sign. The transition-change ranking's top absolute
signal change is tailgating share (ρ = `0.363`); its signed change association
is ρ = `0.231`. These transition rankings are lower because transitions are
sparse relative to the 240 buckets and many features change together.

This verifies input pairing, parsing, ranking, and the CLI report. It does
**not** establish which real signal most affects a driver's emotion. The
simulated features share one designed style driver, so the close rankings
specifically demonstrate that this analysis cannot distinguish interchangeable
correlated predictors. Synthetic reports are explicitly marked in their
warnings; use actual repeated drives and appropriate timing to investigate
real-world associations.

## Interpretation and limitations

This is an exploratory association analysis, **not causal inference**. A strong
association does not show that a vehicle signal caused an emotion. Emotion
detection confidence, lighting/occlusion, road and traffic context, driver
differences, and the profiler's cumulative fields can all affect results.
Observations in adjacent time buckets are also correlated, so the reported
rankings are not independent-sample significance tests or validated safety or
clinical conclusions.

Use repeated drives and consistent sensor setups to compare patterns. To
estimate causal effects, collect a larger controlled dataset and account for
confounders and repeated observations with an appropriate statistical design.

## Tests

```powershell
python -m pytest
```
