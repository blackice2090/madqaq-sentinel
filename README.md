# MADQAQ Sentinel — M0 Conformance Proof

MADQAQ Sentinel is a cyber-physical procedure-integrity concept for secure checkpoints. M0 validates the core conformance logic before live camera perception, tracking, or production integration are introduced.

## SAIF 2026 Evidence & References

### Technical evidence
- [M0 Executed Results](docs/M0_EXECUTED_RESULTS.md)
- [M0 Technical Specification](docs/M0_TECHNICAL_SPEC.md)
- [Full Evidence & Scientific References](docs/EVIDENCE_AND_REFERENCES.md)
- [Original ModaQiQ (MADQAQ) repository](https://github.com/blackice2090/ModaQiQ)

### M0 result
**6/6 predefined synthetic procedure-integrity scenarios matched their expected classifications.**  
**10/10 automated tests passed.**

Scope: these results validate deterministic conformance logic on hand-authored synthetic event sequences only. They do not represent live-camera or field-performance accuracy.

## Reference procedure

`A Entry → B Credential Check → C Screening → D Exit`

## M0 evidence source

Hand-authored synthetic event sequences representing the four-step reference checkpoint procedure. These are functional logic tests, not field-performance evidence.

## Run tests

```bash
pytest
```

## Run scenarios

```bash
python -m simulator.run_scenario normal
python -m simulator.run_scenario omission_b
python -m simulator.run_scenario order_inversion_bc
python -m simulator.run_scenario phantom_completion_b
python -m simulator.run_scenario channel_contradiction_b
python -m simulator.run_scenario uncertain_b
```

## Start API

```bash
uvicorn apps.api.main:app --reload
```

## M1 — Live Physical Perception (prototype)

M1 adds a webcam-based physical-perception pipeline (person detection, temporary tracking, virtual zones A/B/C/D) that emits PHYSICAL `NormalizedEvent`s into the existing, unchanged M0 conformance engine.

**M1 is a live physical-perception prototype. Field accuracy and comparative performance are not yet established.** The M0 results above remain synthetic-sequence results and do not describe M1.

- No face recognition, biometric identity, persistent re-identification, or cloud processing. Only temporary tracker IDs and random in-memory journey IDs.
- Physical evidence alone is single-channel: a full `A → B → C → D` walk is reported as `UNCERTAIN` (awaiting digital confirmation), not as confirmed. Skipping B (`A → C → D`) can produce a step-specific `OMISSION` of B.

```bash
pip install -e ".[dev,vision]"
python -m apps.vision_demo.main            # Q/ESC quit, R reset
```

Details: [M1 Live Vision](docs/M1_LIVE_VISION.md)

## M2 — Dual-Channel Integration (prototype)

M2 fuses the live physical channel (M1) with an independent digital channel through the existing, unchanged M0 engine, so the verdict can change when the second channel arrives (for example UNCERTAIN to COMPLETED, or OMISSION to PHANTOM_COMPLETION).

**The M2 digital channel is a local simulator used to demonstrate cross-channel conformance logic. It is not an integration with a production checkpoint system.** Simulated digital events are labeled as such on screen and in their metadata. Field accuracy and comparative performance are not established.

```bash
python -m apps.dual_channel_demo.main --confidence 0.50
# keys: 1 digital A,B,C,D | 2 digital A,C,D | 3 digital with B failed | 0 clear digital | R reset | Q quit
```

Details: [M2 Dual-Channel Integration](docs/M2_DUAL_CHANNEL.md)

## M3 — Finalist Demo (presentation)

M3 is a presentation and evidence-UX layer over M0-M2: a single dashboard that shows what should happen, what the camera saw, what the (simulated) digital channel claimed, the verdict, and the exact step at fault, with an evidence timeline and a one-key evidence snapshot (PNG + JSON). No conformance, vision or coordinator logic was changed.

**The digital channel remains a local simulator, not an integration with a production checkpoint system, and is labeled SIMULATED DIGITAL CHANNEL on screen. Field accuracy and comparative performance are not established.**

```bash
python -m apps.finalist_demo.main --confidence 0.50
# keys: 1/2/3 simulated digital presets | 0 clear digital | S save evidence | R reset | Q quit
```

Details and demo script: [M3 Finalist Demo](docs/M3_FINALIST_DEMO.md)

## M4.1 — Comparative evaluation (synthetic, development split)

M4 is a scientific evaluation layer: a reproducible harness that measures how much the dual-channel reasoning contributes, using internal ablations and a simple transparent baseline. It adds no model and does not touch M0–M3.

```bash
python -m apps.evaluation.main run --split dev          # generate + evaluate + report (artifacts/evaluation/dev/)
python -m apps.evaluation.main generate --split final   # frozen final manifest; NOT evaluated in M4.1
```

- Procedurally generated benchmark (300 development journeys, 1200 final), ground truth from an independent oracle - never from the conformance engine.
- Systems: full dual-channel engine, physical-only ablation, digital-only ablation, simple procedure-check baseline.
- Multi-label metrics, paired bootstrap intervals, and engine-evaluation latency (not end-to-end).
- The FINAL benchmark was evaluated once in M4.2. Its results are frozen and archived under `docs/evaluation/final/`.

This benchmark uses procedurally generated synthetic event sequences. It evaluates deterministic procedure-integrity reasoning, not live-camera accuracy or field performance. The physical-only and digital-only systems are internal ablations, not external commercial baselines. See [docs/M4_COMPARATIVE_EVALUATION.md](docs/M4_COMPARATIVE_EVALUATION.md).

## M5 — Evidence freeze

M5 adds no algorithm and no new result. It fixes one authoritative set of claims, each tied to the archived frozen M4.2 evaluation, with allowed and forbidden wording. Research prototype; synthetic benchmark; SIMULATED DIGITAL CHANNEL.

- [Claims registry](docs/evidence/CLAIMS_REGISTRY.md) (machine-readable: `docs/evidence/claims.json`)
- [Finalist claims cheatsheet](docs/evidence/FINALIST_CLAIMS_CHEATSHEET.md)
- [Judge Q&A](docs/evidence/JUDGE_QA.md)
- [Poster metrics](docs/evidence/POSTER_METRICS.md)
- [Presentation results slide](docs/evidence/PRESENTATION_RESULTS.md)
- [Evidence matrix](docs/evidence/EVIDENCE_MATRIX.csv)

Read-only consistency check: `python -m apps.evidence.main check`

## M6.1 — Local web dashboard

A local Next.js version of the finalist dashboard. The browser owns the webcam and displays its own video. Sampled JPEG frames go over a WebSocket to the existing FastAPI app, where each browser session gets its own M1 tracker/zones/event emitter and its own M2 dual-channel coordinator. The browser draws zones and boxes over its local video. M0–M5 logic, results and claims are unchanged. The digital channel is still the **SIMULATED DIGITAL CHANNEL** (local simulator, not a production checkpoint integration). Nothing is deployed, and this is not hardened for Internet use.

```bash
pip install -e ".[dev,vision,web]"
python -m uvicorn apps.api.main:app --reload --host 127.0.0.1 --port 8000
cd web && npm install && npm run dev      # http://localhost:3000
```

Details: architecture, protocol, privacy and limitations are in [docs/M6_WEB_DASHBOARD.md](docs/M6_WEB_DASHBOARD.md).

## Scope boundary

M0 does not include live camera input, detection, tracking, ReID, face recognition or production integrations. M0 itself makes no benchmark-performance claims. Comparative synthetic benchmark claims were introduced later in M4 and remain explicitly scoped to deterministic procedure-integrity reasoning. M1 (above) adds live camera input, detection and temporary tracking only. M2 adds a simulated digital channel and cross-channel fusion only. ReID, face recognition, real digital-system integrations, and production deployment remain out of scope.
