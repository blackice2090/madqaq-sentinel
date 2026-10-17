# MADQAQ Sentinel M2 — Dual-Channel Integration

**Status:** prototype. The M2 digital channel is a local simulator used to demonstrate cross-channel conformance logic. It is not an integration with a production checkpoint system. Field accuracy and comparative performance are not established.

M2 adds an independent DIGITAL evidence channel and fuses it with the live PHYSICAL channel from M1 through the existing, unchanged M0 `ConformanceEngine`.

## Architecture

```
Expected procedure (A -> B -> C -> D)
        |
        +--------------------+---------------------+
        v                                          v
Physical evidence (M1: camera, tracker, zones)   Digital evidence (M2: SIMULATED digital events)
        |                                          |
        +------------------+-----------------------+
                           v
              DualChannelCoordinator  (sentinel/dual_channel)
                           v
              Existing ConformanceEngine (M0, unchanged)
                           v
                 Procedure-integrity verdict
```

| Module | Role |
|---|---|
| `sentinel/digital/presets.py` | the three named digital traces |
| `sentinel/digital/simulator.py` | builds simulated DIGITAL `NormalizedEvent`s |
| `sentinel/dual_channel/state.py` | per-journey evidence record, summary type, errors |
| `sentinel/dual_channel/coordinator.py` | owns evidence per journey, re-evaluates M0 on every change |
| `apps/dual_channel_demo/` | live demo (reuses M1 camera, detector, tracker, zones, pipeline) |

## Relationship to M0 and M1

- **M0** is untouched: the coordinator calls `ConformanceEngine.evaluate(procedure, journey, physical_events, digital_events)` and reports what it returns. Verdict text for violations is the engine's own message. A test asserts the coordinator's result equals a direct engine call on the same evidence.
- **M1** is reused by import (`PerceptionPipeline`, tracker, zones, camera, overlay). Its only changes are two backward-compatible parameters: `parse_args(prog=, description=)` and a `subtitle` on the scene overlay. Physical behaviour (dwell, smoothing, hysteresis, first-visit de-duplication) is unchanged.

## How the channels stay independent

- Physical and digital events live in separate lists per journey. An event of the wrong source offered to a channel is rejected.
- Events are stored exactly as received (same objects, timestamps, arrival order). Nothing is sorted into procedure order, edited, or invented. Traces are displayed in arrival order.
- The digital simulator never reads the camera or the physical events; it only receives the active journey ID and procedure ID. It cannot make the physical channel agree with it.
- Digital evidence may bind only to the **active** live journey (the most recently started one). With no journey, injection is refused with: "Enter Zone A to begin a journey before injecting digital evidence." A journey is never created by the digital side.
- Verdict transitions (for example OMISSION to PHANTOM_COMPLETION) happen only because the engine is re-run on the new evidence; there is no display special-casing.

## Simulator disclosure

Every digital event has `source = DIGITAL`, `STEP_COMPLETED` or `STEP_FAILED`, a UUID `event_id`, a timezone-aware UTC timestamp, the live journey's `journey_id` and `procedure_id`, and `metadata = {"source": "m2_digital_simulator", "simulated": true}`. The demo shows **SIMULATED DIGITAL CHANNEL - local simulator - not a real checkpoint system** in an orange banner that is always on screen, labels the digital row `DIGITAL (SIMULATED)`, and puts "SIMULATED" in the window title. Timestamps within a preset are 50 ms apart and strictly increasing so the engine's (timestamp, event_id) ordering cannot scramble the preset.

## Run

```bash
pip install -e ".[dev,vision]"
python -m apps.dual_channel_demo.main --confidence 0.50
# optional: --debug-zones, --camera 1, --zone-dwell-ms 400
```

## Demo controls

| Key | Action |
|---|---|
| `1` | inject simulated digital **A,B,C,D** (all STEP_COMPLETED) |
| `2` | inject simulated digital **A,C,D** (no B) |
| `3` | inject simulated digital **A,B(FAILED),C,D** |
| `0` | clear digital evidence of the current journey (physical untouched) |
| `R` | reset everything: physical journeys and tracker, digital evidence, coordinator |
| `Q` / `ESC` | quit |

Each preset is injected once. While a journey has digital evidence, pressing 1, 2 or 3 again is refused with a message (press `0` first). Injection is also refused when there is no journey. The panel shows EXPECTED, PHYSICAL, DIGITAL (SIMULATED), per-step states, VERDICT and FINDING.

## The five scenarios

| # | Physical | Digital (simulated) | Verdict |
|---|---|---|---|
| 1 Full agreement | A,B,C,D | A,B,C,D | `COMPLETED` - every step CONFIRMED - "Dual-channel evidence agrees." |
| 2 Phantom completion | A,C,D | A,B,C,D | `VIOLATED` `PHANTOM_COMPLETION` at B - digital completion has no supporting physical evidence |
| 3 Omission | A,C,D | A,C,D | `VIOLATED` `OMISSION` - missing step B |
| 4 Channel contradiction | A,B,C,D | B `STEP_FAILED` | `VIOLATED` `CHANNEL_CONTRADICTION` at B |
| 5 Physical only | A,B,C,D | none | `UNCERTAIN` - awaiting digital-channel confirmation (unchanged M0/M1 behaviour) |

Natural transitions: physical A,B,C,D goes UNCERTAIN to COMPLETED after key 1; physical A,C,D goes OMISSION to PHANTOM_COMPLETION after key 1, and stays OMISSION after key 2.

## Privacy design

No face recognition, biometric identity, persistent re-identification or cloud processing. Only temporary tracker IDs and random in-memory journey IDs exist; digital events carry no personal identity. Frames are not stored. Reset clears all evidence; nothing persists across restarts.

## Limitations

- The M2 digital channel is a local simulator used to demonstrate cross-channel conformance logic. It is not an integration with a production checkpoint system.
- The digital presets are hand-defined traces; they do not model real system latency, failures, or clock skew between channels (cross-channel timestamps are not compared by the M0 engine).
- Automated tests build physical evidence with the real M1 emitter from synthetic tracker positions; live camera behaviour must be verified on hardware.
- One active journey at a time receives digital evidence; physical M1 limitations (single camera, rectangular zones, tracker-ID changes after occlusion) still apply.
- No field accuracy, latency or comparative performance claim is made.
