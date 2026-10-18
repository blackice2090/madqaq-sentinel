# MADQAQ Sentinel M6.1 — Local Web Dashboard

**Status:** local web version of the M3 finalist dashboard. M6.1 adds a browser front end and a WebSocket session layer. It changes no M0 conformance logic, no M1 vision/zone/event semantics, no M2 coordinator or simulator behaviour, no M3 presentation wording, no frozen M4 artifact and no M5 claim.

> **The digital channel is simulated.** It is the M2 local simulator (`SIMULATED DIGITAL CHANNEL` — *Local simulator — not a production checkpoint integration.*). M6.1 is a **local** prototype: nothing is deployed, there is no authentication, and it is not suitable for Internet exposure.

## 1. Architecture

```
Browser webcam ── getUserMedia() ──► <video> (displayed LOCALLY, never round-tripped)
        │
        └─ sampled frames (canvas → JPEG, ~6 fps, ≤ 960 px, q≈0.75) ── WebSocket (binary) ──►
                                                                                           FastAPI  /ws/session
     one WebSession per socket:  cv2.imdecode → M1 tracker (YOLO + ByteTrack) → M1 zones / PhysicalEventEmitter
                                 → physical NormalizedEvents → M2 DualChannelCoordinator (+ M2 simulator presets)
                                 → M0 ConformanceEngine → M3 dashboard model / evidence export
        ◄── WebSocket JSON "state" (detections, zones, traces, step states, verdict, finding, timeline) ──
Next.js dashboard: draws zones + boxes on a <canvas> over its own <video>
```

Reused unchanged:

| Layer | Reused code |
|---|---|
| M0 | `sentinel.conformance.engine.ConformanceEngine` |
| M1 | `PerceptionPipeline`, `PhysicalEventEmitter`, `ZoneSet` + `config/checkpoint_zones.json`, `VisionConfig` defaults, `UltralyticsByteTrackTracker` |
| M2 | `DualChannelCoordinator`, `inject_digital_preset` / `clear_digital` / `reset`, `PRESETS` (`full_trace`, `without_b`, `b_failed`), `DigitalEventSimulator` |
| M3 | `build_dashboard_model`, `build_evidence`, `build_timeline`, `labels` (verdict, findings, privacy and simulator wording) |

New code: `apps/web_api/` (config, protocol validation, per-session wrapper, routes), two additive lines in `apps/api/main.py` (router + localhost-only CORS), and the `web/` Next.js app. No zone, event or conformance logic was re-implemented, in Python or in TypeScript.

## 2. Browser camera flow

1. The page opens a WebSocket (one backend session) but sends **no frames**.
2. **Start Camera** calls `navigator.mediaDevices.getUserMedia({video, audio: false})`. Permission denial, a missing camera, a busy camera and insecure origins produce a clear message; **Stop Camera** stops all tracks.
3. The `<video>` element shows the browser's own `MediaStream` (mirrored, like the M1 desktop demo). Its frame rate never depends on the backend.
4. While the camera is active **and** the backend is connected, a sampler draws the video into an off-screen canvas, mirrored the same way as the preview, downscaled to at most 960 px wide, encodes JPEG (quality 0.75) and sends it as one binary message.
5. **At most one frame is in flight**: the next frame is sent only after the server's `state` reply (or after a 3 s timeout). A slow backend therefore lowers the analysed frame rate instead of building a queue.

Sampling constants live in `web/lib/config.ts` (overridable via `NEXT_PUBLIC_SAMPLE_FPS`, `NEXT_PUBLIC_MAX_ANALYSIS_WIDTH`, `NEXT_PUBLIC_JPEG_QUALITY`) and the advertised defaults in `apps/web_api/config.py`. **They are starting points, not tuned or optimal values.**

Because the sampled frame is mirrored exactly like the preview, the analysed image *is* what the user sees: M1 zones (defined on the mirrored image, as in the desktop demo) and returned boxes map directly onto the preview.

Timing note: the M1 emitter's dwell confirmation is time-based (600 ms and ≥ 3 frames). Event timestamps are taken from the **server clock on receipt**; client-supplied timestamps are not trusted. At ~6 fps a zone is confirmed after ~0.6–0.8 s; at lower effective rates confirmation takes longer but semantics are unchanged.

## 3. Overlay coordinates

Zones (from `config/checkpoint_zones.json`) and person boxes are sent **normalized (0..1) relative to the analysed frame**. The browser computes the rectangle the video actually occupies inside its container (`object-fit: contain`, letter/pillar-boxing), maps normalized coordinates onto it, and redraws on container resize (`ResizeObserver`), video size change and every new state. Canvas size follows the device pixel ratio. No coordinates are hard-coded in CSS pixels. Boxes are hidden when the last state is older than 1.5 s or the backend is disconnected.

## 4. WebSocket protocol `madqaq-web/1`

Endpoint: `ws://127.0.0.1:8000/ws/session` — one connection = one isolated session.

**Client → server**

| Message | Format |
|---|---|
| camera frame | binary, one JPEG (≤ 2,000,000 bytes, ≤ 1920×1920 px — dimensions are read from the JPEG header **before** decoding) |
| command | text, exactly `{"command": "<name>"}` — no other fields are accepted |

Commands: `reset`, `digital_full`, `digital_without_b`, `digital_b_failed`, `digital_clear`, `ping`, `get_evidence`. Text messages are limited to 4096 bytes.

**Server → client** (JSON text, always with `type`)

| type | When | Content |
|---|---|---|
| `hello` | on connect | `session_id`, `protocol`, normalized `zones`, `limits`, `recommended` sampling, `digital_simulated: true`, `disclosures` |
| `state` | after connect, every frame and every state-changing command | see below |
| `ack` | after a command | `command`, `ok`, `message` (e.g. why a digital preset was rejected) |
| `error` | invalid input | `code` ∈ `invalid_json`, `invalid_command`, `message_too_large`, `invalid_image`, `frame_too_large`, `vision_unavailable`, `analysis_failed`, `no_journey`, `session_limit`; `message` is safe to display and never contains paths or stack traces |
| `pong` | reply to `ping` | `session_id` |
| `evidence` | reply to `get_evidence` | `evidence` object (§7) |

`state` fields: `type`, `protocol`, `session_id`, `journey_id`, `frame {width, height, seq}`, `vision {status, message}`, `detections [{tracker_id, confidence, box[x1,y1,x2,y2], zone_id, in_active_journey}]`, `zones [{zone_id, name, x1, y1, x2, y2}]`, `active_zone`, `expected`, `physical_trace`, `digital_trace [{step_id, failed}]`, `step_states [{step_id, name, state, indicator, word}]`, `verdict` (`WAITING | IN PROGRESS | COMPLETED | VIOLATED | UNCERTAIN`), `engine_status`, `violation_types`, `violation_labels`, `finding`, `finding_where`, `extra_findings`, `timeline` (latest 10, oldest first, ISO-8601 UTC timestamps), `digital_active`, `digital_simulated` (always `true`), `notice`, `disclosures`.

The schema is fixed by `tests/web_api/test_m6_web_session.py::test_state_schema_is_stable`; the TypeScript types and runtime validator are in `web/lib/protocol.ts`. Malformed server messages are dropped by the client.

## 5. Session isolation

`SessionManager` creates one `WebSession` per WebSocket. Each session owns its **own** tracker instance (its own YOLO/ByteTrack state, loaded on the session's first frame), `PhysicalEventEmitter`, `PerceptionPipeline`, `DualChannelCoordinator` (journeys, physical list, digital list, verdict) and timeline. There is no global journey. `RESET JOURNEY` resets only that session. When the socket closes, the session is removed and its state is cleared. A reconnect therefore starts a **new** session and a new journey; the UI says so. At most 4 concurrent sessions are accepted (each loads its own detector).

## 6. Controls (existing M2 semantics)

| Web control | Command | M2 key | Behaviour |
|---|---|---|---|
| FULL DIGITAL | `digital_full` | 1 | simulated A, B, C, D completed |
| WITHOUT B | `digital_without_b` | 2 | simulated A, C, D completed |
| B FAILED | `digital_b_failed` | 3 | simulated A, C, D completed; B failed |
| CLEAR DIGITAL | `digital_clear` | 0 | remove simulated digital evidence of the active journey |
| RESET JOURNEY | `reset` | R | clear this session's physical journey, digital evidence and verdict |

Presets bind only to the active journey, inject once (clear first), and are rejected with no journey — exactly as in M2 (`test_digital_commands_match_m2_keyboard_semantics` compares the web path with the M2 `handle_key` path).

## 7. SAVE EVIDENCE

The button sends `get_evidence`; the backend returns the M3 `build_evidence` JSON for the active journey, plus the full evidence `timeline`, `disclosures` and `export: {source: "m6.1-web-dashboard", frames_saved: false, image_file: null}`. The browser downloads it as `madqaq-evidence_<local time>_<VERDICT or violation types>.json`. It contains the journey ID (random UUID), verdict, violation types and findings, step states, both event traces with timestamps, the simulated-channel disclaimer and the privacy statement. It contains no image and no biometric or identity data. PNG capture is not implemented in M6.1 (optional; not needed for the gate).

## 8. Privacy behaviour

- **Temporary tracking only • No face recognition • No persistent identity** (shown in the footer).
- **Sampled camera frames are sent to the local MADQAQ analysis backend while the web demo is active.** They are decoded in memory, analysed and discarded; the backend does not save frames and does not log image data.
- No frames are sent before the user presses Start Camera, and none after Stop Camera.
- Only a temporary tracker integer and a random journey UUID exist; both disappear on reset or disconnect.
- First use of Ultralytics may download model weights (`*.pt`, git-ignored).

## 9. Local launch

Backend (repository root, Python ≥ 3.12). Install the vision extras **and** the `web` extra; plain `uvicorn` has no WebSocket implementation, so without `websockets` the `/ws/session` upgrade fails (`/web/health` reports `"websocket_support": false` and the dashboard shows a warning):

```bash
pip install -e ".[dev,vision,web]"
```


```bash
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend (Node.js ≥ 20; versions are pinned in `web/package.json` and `web/package-lock.json`):

```bash
cd web
npm install
npm run dev
```

Open http://localhost:3000 in Chrome. `localhost` is a secure context, so camera access works without HTTPS. Configuration: copy `web/.env.example` to `web/.env.local` (`NEXT_PUBLIC_API_BASE_URL`, `NEXT_PUBLIC_WS_URL`). Allowed origins default to `http://localhost:3000` and `http://127.0.0.1:3000`; override with `MADQAQ_WEB_ORIGINS` (comma-separated; `*` is ignored). CORS is enabled for those origins only, and WebSocket connections whose `Origin` header is not allowed are refused.

Checks: `python -m pytest`, `python -m apps.evidence.main check`, `cd web && npm run lint && npm run build && npm test` (`npm run typecheck` runs `tsc --noEmit`).

Tooling note: Vitest is pinned to 3.2.4 because Vitest 4/5 made npm 10 fail dependency resolution in this setup, and ESLint to 9.39.5 because the Next.js lint plugins do not yet support ESLint 10 (npm prints a deprecation notice for 9.x; it is harmless).

## 10. Robustness basics (local prototype)

Frame byte and pixel limits, JPEG-only validation before decoding, strict command whitelist, closed message schema, a session cap, origin checks, no client-supplied paths or code, no frame persistence and session cleanup on disconnect. Errors are reported to the client with safe messages; details go to the backend log. **This is not sufficient for Internet production deployment.** No authentication, TLS or rate limiting is provided.

## 11. Limitations

- Not hardware/browser tested by the automated suite: webcam permission, live detection quality and the browser rendering are part of the user's hardware gate (A–J). Backend tests use a scripted tracker, synthetic JPEGs and a fake clock.
- Live-camera accuracy and end-to-end latency are **not measured** in M6.1. The M4/M5 benchmark figures are not shown on the dashboard and do not describe this camera pipeline.
- The analysed frame rate depends on the machine running YOLO; detection boxes lag the live video by the analysis round-trip.
- One shared model weights file; each session loads its own model instance, so memory grows with sessions (capped at 4).
- The digital channel remains the M2 simulator: there is no real digital system to integrate with in this prototype, and presenting one would contradict the M5 claims registry (C011).
- Deployment (Vercel, public FastAPI, authentication) is **not** part of M6.1.
