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

## Scope boundary

M0 does not include live camera input, detection, tracking, ReID, face recognition, production integrations, or benchmark claims. M1 (above) adds live camera input, detection and temporary tracking only; ReID, face recognition, digital evidence, production integrations and benchmark claims remain out of scope.
