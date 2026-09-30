# MADQAQ Sentinel — M0 Conformance Proof

M0 validates the core research logic before cameras, tracking, or UI are introduced.

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
