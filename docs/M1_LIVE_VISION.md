# MADQAQ Sentinel M1 — Live Physical Perception

**Status:** live physical-perception *prototype*. Field accuracy and comparative performance are **not yet established**. No M1 accuracy figures are claimed anywhere in this repository.

M1 turns a person's movement through four virtual checkpoint zones into the same `NormalizedEvent` model used by the M0 deterministic conformance engine. The M0 engine is used unchanged.

Reference procedure: `A Entry → B Credential Check → C Screening → D Exit`

## Architecture

```
Webcam (camera.py)
  → Person detection, person class only (detector.py, YOLO11n via Ultralytics)
  → Temporary tracking (tracker.py, ByteTrack)
  → Virtual zones A/B/C/D (zones.py, config/checkpoint_zones.json)
  → Zone-transition logic (event_emitter.py)
  → PHYSICAL NormalizedEvents
  → Existing ConformanceEngine (pipeline.py)  → OpenCV demo (apps/vision_demo)
```

| Module | Responsibility | Needs camera/model? |
|---|---|---|
| `sentinel/vision/config.py` | settings, human-readable error types | no |
| `sentinel/vision/zones.py` | normalized geometry, point-in-zone, zone-file loading/validation | no |
| `sentinel/vision/event_emitter.py` | tracker→journey mapping, debounce, dedup, event creation | no |
| `sentinel/vision/pipeline.py` | emitter + M0 engine + status summary | no |
| `sentinel/vision/tracker.py`, `detector.py` | Ultralytics YOLO + ByteTrack wrapper | model |
| `sentinel/vision/camera.py` | OpenCV capture | camera |
| `apps/vision_demo/` | argparse CLI, overlay and status panel | camera + model |

Everything except the last three rows is covered by unit tests that run without a webcam.

## Privacy design

- No face detection, face recognition or biometric identity.
- No persistent re-identification and no appearance embeddings stored by this code.
- Only a temporary integer tracker ID and a random UUID journey ID, both in memory only. They do not survive restart or **R** (reset).
- Frames are processed in memory and never written to disk. Processing is local; nothing is sent to a cloud service.
- Events carry only `tracker_id`, `zone`, `source` in `metadata`. No identity fields exist.
- Note: the first run of Ultralytics downloads model weights over the internet. Weights are git-ignored (`*.pt`).

## Setup and installation

Requires Python ≥ 3.12.

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate      macOS/Linux: source .venv/bin/activate
pip install -e ".[dev,vision]"
```

The vision group (`opencv-python`, `ultralytics`) is optional; M0 installs and tests without it. Ultralytics pulls in PyTorch, which is a large download.

## Run

```bash
python -m apps.vision_demo.main
python -m apps.vision_demo.main --camera 0 --model yolo11n.pt --zones config/checkpoint_zones.json --confidence 0.45
```

Keys: **Q** or **ESC** quit, **R** reset journeys and events. `--no-mirror` disables the mirrored preview (mirroring is on so on-screen motion matches yours).

Tests (no camera needed): `pytest`

## Zone configuration

`config/checkpoint_zones.json` maps zone id to a rectangle in normalized coordinates (0.0–1.0, origin top-left), independent of resolution:

```json
{ "A": {"name": "Entry", "x1": 0.02, "y1": 0.10, "x2": 0.24, "y2": 1.0}, "...": "..." }
```

Rules enforced at load time with readable errors: file exists and is valid JSON; each zone has a non-empty `name` and finite `x1,y1,x2,y2` in [0, 1] with `x1<x2`, `y1<y2`; zone ids are unique; zones do not overlap; zone ids must be steps of the procedure.

A person is located by the **bottom-center of the bounding box** (ground-position estimate). Edges are inclusive. The default layout is four vertical bands left to right so a person can walk across the frame. If a person's feet are out of frame, the box bottom is the frame bottom, so the shipped zones extend to y = 1.0.

## Event-generation behavior and zone stability

Live testing showed that the raw bottom-center point jitters around zone boundaries and produced repeated B/C and C/D events (`A -> B -> C -> B -> C -> D -> C -> D`). M1 now de-noises the *perception* side; the M0 engine was not changed.

Pipeline per tracker, per frame:

1. **Smoothing** - zone membership uses the median of the last `smoothing_window` (default 5) ground points. Only coordinates are kept, in memory, per temporary tracker ID.
2. **Hysteresis / deadband** - once stable in a zone, the smoothed point must leave that zone by more than `boundary_margin` (default 0.02 normalized) before it counts as left. Zones never overlap; the margin only widens the *current* stable zone for the "stay" test. Keep a gap between zones at least as wide as the margin (the shipped config has 0.03).
3. **Dwell confirmation** - a candidate zone must be held continuously for `zone_dwell_ms` (default 600 ms, time-based) and for at least `min_consecutive_frames` (default 3) frames. If the candidate changes first, the timer restarts. No event fires on a one-frame entry.
4. **First stable visit only** - within one journey each step is emitted at most once, in the order of *first* stable visits. Nothing is sorted or invented: a deliberate `A -> C -> B` is emitted as `A -> C -> B` and M0 reports the order inversion. Only repeats of an already-emitted step are suppressed, so `A,B,C,B,C,D,C,D` emits `A -> B -> C -> D`.

Journeys: a journey starts when a tracker is *stable* in Zone A. A tracker first stable in B, C or D gets no journey and no events; if it later becomes stable in A, a journey starts then. Event confidence is the mean detector confidence over the confirming frames. Trackers unseen for `track_timeout_s` (default 10 s) are forgotten along with their smoothing history; the journey record stays until reset.

Trade-off: stability costs latency. A step registers roughly `zone_dwell_ms` plus about half the smoothing window (a few frames) after the person actually arrives. Tune with `--zone-dwell-ms`, `--smoothing-window`, `--boundary-margin`.

A genuine return to an earlier zone is deliberately not re-emitted in M1 (the reference procedure is linear). This is perception de-noising, not a claim that the person's real path was linear.

### Debug overlay

`--debug-zones` shows, for the focus person: raw zone, candidate zone, stable zone, dwell (ms / target) and the smoothed ground point (also drawn as a cross on the video). Omit the flag for the final demo.

## M0 integration and displayed semantics

Only physical events are supplied; `digital_events` is empty unless a caller passes some. Nothing digital is fabricated.

| Physical trace | M0 outcome | Demo shows |
|---|---|---|
| `A → B → C → D` | `UNCERTAIN` (single channel is never `CONFIRMED`) | PHYSICAL TRACE COMPLETE; awaiting digital-channel confirmation |
| `A → C → D` | `VIOLATED`, `OMISSION`, step B | VIOLATED, Missing step: B |
| `A → B` (in progress) | `UNCERTAIN` | PHYSICAL TRACE IN PROGRESS |

M0 is not modified to make the demo look better.

## Limitations

- Dwell and smoothing add latency, and a fast pass through a zone shorter than the dwell time is not registered.
- Prototype only: no accuracy, latency, or comparative benchmark has been measured.
- Single camera, single flat view; rectangular zones only; the ground point is a 2D image-plane proxy, not a calibrated floor position.
- Occlusion, crowding or a lost track can produce a new tracker ID. A new ID only starts a journey in Zone A, so a person re-acquired mid-procedure is not tracked.
- Lighting, camera angle and partial bodies (for example a seated person) affect detection and the ground point.
- ByteTrack IDs are temporary and may be reassigned.
- OpenCV text is ASCII-only, so the trace is drawn `A -> B -> C`.

## Relationship to M2 (digital evidence)

M1 provides the physical channel only. M2 is expected to supply independent DIGITAL events (for example credential-system records) using the same `NormalizedEvent` model, keyed to the same journey. Feeding both channels to the existing M0 engine is what enables `CONFIRMED`, `PHANTOM_COMPLETION` and `CHANNEL_CONTRADICTION`. M2 is out of scope here and has not been started.
