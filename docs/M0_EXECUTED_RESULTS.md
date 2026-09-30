# MADQAQ Sentinel M0 — Executed Validation Results

**Engine version:** `m0.1`  
**Reference procedure:** `A Entry → B Credential Check → C Screening → D Exit`  
**Data source:** Hand-authored synthetic event sequences for functional logic validation. These are not field-performance results.

## Automated test suite

`10 passed in 0.28s`

## Scenario results

| Scenario | Expected | Engine output | Match | Explanation |
|---|---|---|---|---|
| normal | CONFORMANT | CONFORMANT | YES | All required steps aligned across both evidence channels. |
| omission_b | OMISSION:B | OMISSION:B | YES | Required step B is missing between A and C. |
| order_inversion_bc | ORDER_INVERSION:B | ORDER_INVERSION:B | YES | Step C occurred before required step B. |
| phantom_completion_b | PHANTOM_COMPLETION:B | PHANTOM_COMPLETION:B | YES | Digital completion for step B has no supporting physical evidence. |
| channel_contradiction_b | CHANNEL_CONTRADICTION:B | CHANNEL_CONTRADICTION:B | YES | Physical evidence and digital status contradict each other at step B. |
| uncertain_b | UNCERTAIN | UNCERTAIN | YES | Evidence was insufficient for a deterministic violation. |

## Poster-safe result statement

**M0 functional validation: 6/6 defined scenarios matched their expected classifications.**

This result demonstrates deterministic conformance logic on synthetic event sequences only. It does **not** establish live-camera accuracy, real-world security effectiveness, or superiority over external baselines. Those remain M1–M4 work.

## Four-case core table for the poster

| Test case | Expected classification | Engine output | Match |
|---|---|---|---|
| Normal | Conformant | Conformant | ✓ |
| Omission | Missing B | Missing B | ✓ |
| Order inversion | B/C invalid order | B/C invalid order | ✓ |
| Phantom completion | Digital B unsupported physically | Digital B unsupported physically | ✓ |

Additional checks executed: explicit channel contradiction and low-confidence uncertainty handling.
