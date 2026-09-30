# MADQAQ Sentinel — M0 Technical Specification

## Goal

Prove the procedure-conformance concept before adding computer vision, tracking, UI, or production integrations.

## Frozen M0 decisions

- Repository: `blackice2090/madqaq-sentinel`
- Reference procedure: `A Entry → B Credential Check → C Screening → D Exit`
- Stack: Python 3.12, FastAPI, Pydantic, pytest, SQLite selected for persistence
- No frontend in M0
- No live camera, detector, tracker, ReID, or face recognition in the functional core proof

## Core model

```text
Procedure Definition
      ↓
Journey
      ↓
Physical Events + Digital Events
      ↓
Dual-Channel Conformance Engine
      ↓
Conformance Result
```

## Event channels

- `PHYSICAL`: independent evidence of a procedure step being observed in the real world
- `DIGITAL`: digital-system claims such as step completed or failed

## M0 violation taxonomy

- `OMISSION`: a required step is absent while the journey progresses to a later required step
- `ORDER_INVERSION`: required steps occur in an invalid order
- `PHANTOM_COMPLETION`: the digital system claims completion while physical evidence does not support the step
- `CHANNEL_CONTRADICTION`: physical and digital channels make explicitly incompatible claims
- `UNCERTAIN`: available evidence is insufficient for a deterministic classification

## Rule precedence

1. Explicit channel contradiction
2. Phantom completion
3. Order inversion
4. Omission
5. Uncertainty
6. Conformant

## Required functional scenarios

1. Normal: `A → B → C → D`
2. Omission: `A → C → D`
3. Order inversion: `A → C → B → D`
4. Phantom completion: physical `A → C → D`, digital `A → B → C → D`
5. Explicit channel contradiction at B
6. Low-confidence uncertain case

## Acceptance criterion for the functional core

The engine must generate the expected classification from the procedure definition and event traces, not from scenario-specific hard-coded outputs.

See `M0_EXECUTED_RESULTS.md` for the executed functional validation.

## Scope boundary

The executed M0 functional result is based on hand-authored synthetic event sequences. It does not establish camera accuracy, tracking continuity, field performance, operational security impact, or superiority over external baselines.

## Next milestone

M1 replaces simulated physical events with:

```text
Camera → Detection → Tracking → Zone / Action Logic → Normalized Physical Events
```

The conformance engine should remain independent from the perception implementation.
