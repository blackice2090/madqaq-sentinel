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

## Scope boundary

M0 does not include live camera input, detection, tracking, ReID, face recognition, production integrations, or benchmark claims.
