# MADQAQ Sentinel M3 — Finalist Demo

**Status:** presentation and evidence UX over the M0/M1/M2 prototype. M3 changes no conformance, vision, coordinator or simulator logic. Field accuracy and comparative performance are not established.

> **The digital channel is simulated.** It is a local simulator used to demonstrate cross-channel conformance logic. It is not an integration with a production checkpoint system.

## Purpose

A SAIF judge should understand, in under 20 seconds: what should happen, what physically happened, what the digital system claimed, the verdict, and the exact step that caused the issue. The dashboard answers these in that order.

## Architecture

```
M1 camera -> detector -> tracker -> zones -> PHYSICAL events --+
                                                               +--> DualChannelCoordinator (M2) --> M0 ConformanceEngine
M2 digital simulator (SIMULATED) -> DIGITAL events ------------+                 |
                                                                                  v
                          sentinel/presentation  (wording, timeline, dashboard model, evidence export)   <- M3, pure Python
                                                                                  v
                          apps/finalist_demo     (Pillow layout + painter, OpenCV window, key handling)  <- M3
```

| Module | Role |
|---|---|
| `sentinel/presentation/labels.py` | judge-friendly wording (presentation mapping only) |
| `sentinel/presentation/timeline.py` | evidence timeline built only from real runtime events |
| `sentinel/presentation/model.py` | `DashboardModel`: everything on screen as plain data |
| `sentinel/presentation/evidence.py` | snapshot filename + JSON evidence export |
| `apps/finalist_demo/render.py`, `fonts.py` | layout (testable, no camera) and Pillow painter |
| `apps/finalist_demo/main.py` | live loop; reuses the M1 pipeline and M2 coordinator unchanged |

The M2 demo (`apps.dual_channel_demo.main`) is kept as is. The only edit to earlier code is one backward-compatible parameter on `parse_args` so the finalist app can add its own options. The panel uses Pillow (installed with the `vision` extra) instead of OpenCV text so it can draw proper typography and symbols; if the machine has no suitable font it falls back to ASCII (`->`, `|`).

## Run

```bash
pip install -e ".[dev,vision]"
python -m apps.finalist_demo.main --confidence 0.50
```

Options: `--debug-zones` (engineering diagnostics), `--canvas 1920x1080` (default `1600x900`, minimum `960x540`), `--evidence-dir <dir>` (default `artifacts/evidence`), plus the M1 options (`--camera`, `--zone-dwell-ms`, ...).

## Interface

Left: live camera with zones A-D, person boxes with a small temporary ID, and a one-line status (tracker ID, current zone, confidence); below it the **evidence timeline**. Right, top to bottom: **expected procedure**, **physical evidence**, **digital evidence** (always tagged SIMULATED DIGITAL CHANNEL), **step states**, **verdict** (the largest element), **primary finding**. Footer: controls, privacy line, simulation disclosure.

- **Step states** use text, not only colour: `OK`, `MISSING`, `CONFLICT`, `UNCERTAIN`, `NOT REACHED`, with a short reason such as "Digital only" or "Channels disagree".
- **Verdict:** `COMPLETED` ("Physical and digital evidence agree."), `UNCERTAIN` ("Awaiting sufficient cross-channel evidence."), or `VIOLATED` with the violation type in words (OMISSION, PHANTOM COMPLETION, ORDER INVERSION, CHANNEL CONTRADICTION) and the step it concerns.
- **Primary finding** is the engine's violation re-worded, for example "Credential Check was recorded digitally, but no supporting physical evidence was observed." The underlying engine violation is unchanged and is also saved verbatim in the evidence JSON.
- **Timeline:** time, channel, step, event type, and confidence for physical events. Latest 8 events, oldest first. Digital rows read "(simulated)". Nothing is generated: the rows are the coordinator's stored events.
- **Finalist mode** (default) shows no raw/candidate zone, dwell timers or smoothed points. `--debug-zones` adds them.

## Controls

| Key | Action |
|---|---|
| `1` / `2` / `3` | inject simulated digital: full trace / without B / B failed (once per journey) |
| `0` | clear digital evidence of the current journey |
| `S` | save evidence snapshot (PNG + JSON) |
| `R` | reset everything |
| `Q` / `ESC` | quit |

## Evidence snapshot

`S` writes `artifacts/evidence/<YYYY-MM-DD>_<HHMMSS>_<VERDICT>.png` (for example `2026-10-17_172015_PHANTOM_COMPLETION.png`) and a JSON file with the same base name. The PNG is the dashboard exactly as displayed, including the live camera frame (a user-triggered local snapshot). The JSON holds: journey ID, expected procedure, physical and digital event traces with exact timestamps, verdict, violation types and findings, step states, engine version, and `"digital_simulated": true` with the disclaimer. It contains no face crops and no identity, not even the temporary tracker ID. Name clashes within one second get a `_2` suffix. With no journey, `S` shows "Nothing to save yet" instead of writing files. `artifacts/` is git-ignored because snapshots can contain the camera image.

## Finalist demo script (about 2 minutes)

1. Start the demo. Say: "The left side is a live camera. The right side compares what *should* happen, what the camera *saw*, and what the digital system *claims*. The digital side is simulated for this demo."
2. **Agreement.** Walk A, B, C, D, pausing about a second in each zone. Physical shows A to D; verdict is UNCERTAIN, "Awaiting sufficient cross-channel evidence." Press `1`: every step becomes OK and the verdict turns COMPLETED.
3. Press `R`. **Phantom completion.** Walk A, C, D, skipping the credential check. Verdict shows OMISSION, "Required step B — Credential Check was skipped." Press `1`: the simulated digital system now claims B. Verdict flips to PHANTOM COMPLETION: "Credential Check was recorded digitally, but no supporting physical evidence was observed." Press `S` to save the evidence.
4. Press `R`. **Contradiction.** Walk A, B, C, D, then press `3`: verdict CHANNEL CONTRADICTION at step B, "Physical evidence and digital status disagree at Credential Check."
5. Close with: "Same engine, same procedure; only the evidence changed. Tracking is temporary, there is no face recognition and no stored identity."

## Privacy design

Temporary tracking only, no face recognition, no biometric identity, no persistent re-identification, no cloud processing. Journey IDs are random and in memory. The footer states this on screen. Reset clears all displayed evidence. Snapshots are written only when the operator presses `S`.

## Limitations

- The M2 digital channel is a local simulator used to demonstrate cross-channel conformance logic. It is not an integration with a production checkpoint system.
- No field accuracy, latency or comparative performance claim is made.
- Layout is verified by automated tests at 1920x1080 and 1600x900 with the fonts available on the test machine; text is shrunk or ellipsized to fit, but appearance on other machines and displays is only confirmed by looking at it.
- Rendering the dashboard costs roughly 30-60 ms per frame on a typical CPU, which can lower the frame rate on slow machines.
- Physical limitations of M1 (single camera, rectangular zones, tracker-ID changes after occlusion, dwell/smoothing latency) still apply.
