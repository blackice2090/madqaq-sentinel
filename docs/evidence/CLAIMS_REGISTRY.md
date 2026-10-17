# MADQAQ Sentinel — Claims Registry (M5 Evidence Freeze)

Authoritative claims-and-evidence layer for the poster, presentation, pitch, README, QR evidence page, demo narration and judge Q&A. Machine-readable source: [`claims.json`](claims.json). Every number below is read from the archived, frozen M4.2 final evaluation in `docs/evaluation/final/`; nothing was recomputed or re-run.

**Positioning:** research prototype · working proof of concept · finalist demonstration prototype.

**Standing scope:** the benchmark is *synthetic and procedurally generated*; the digital channel is a *SIMULATED DIGITAL CHANNEL*; no live-camera or field accuracy has been measured.

Verify at any time (read-only): `python -m apps.evidence.main check`

## Status summary

| Status | Count | Claims |
|---|---|---|
| VERIFIED | 1 | C001 |
| VERIFIED_WITH_SCOPE | 9 | C002, C003, C004, C005, C006, C007, C008, C013, C014 |
| DEMONSTRATED | 3 | C010, C011, C012 |
| LIMITATION | 1 | C009 |
| NOT_SUPPORTED | 1 | C015 |

Format per claim: CLAIM → EVIDENCE → SCOPE → ALLOWED WORDING → FORBIDDEN WORDING → LIMITATIONS.

## C001 — benchmark — `VERIFIED`

**CLAIM:** The frozen final benchmark contains 1,200 procedurally generated synthetic journeys.

**EVIDENCE:** Archived final summary and manifest: n_cases 1200, seed 20261123, generator mgen-1.0, dataset SHA-256 28a3979e...8697.

**EVIDENCE SOURCE:** `docs/evaluation/final/summary.json#benchmark.n_cases`; `docs/evaluation/final/manifest.json#dataset_sha256`; `docs/evaluation/final/FINAL_RUN_RECORD.json#case_count`  
**Verification type:** archived frozen result

**SCOPE:** Synthetic journeys produced by a seeded procedural generator; ground truth comes from an independent oracle over a latent world, not from the engine.

**ALLOWED WORDING:**
- “The frozen final benchmark has 1,200 procedurally generated synthetic journeys.”
- “1,200 frozen synthetic journeys.”

**FORBIDDEN WORDING (do not say):** “tested on 1,200 real passengers”; “validated on 1,200 checkpoint operations”

**LIMITATIONS:** Synthetic data only; no real passengers, cameras or checkpoint operations are involved.

## C002 — headline_metric — `VERIFIED_WITH_SCOPE`

**CLAIM:** On the frozen 1,200-journey synthetic benchmark the full dual-channel system achieved 95.0% exact violation-set accuracy.

**EVIDENCE:** Archived system_comparison.csv full_dual_channel exact_set_accuracy = 0.95 (95% bootstrap CI 0.9375-0.9625).

**EVIDENCE SOURCE:** `docs/evaluation/final/system_comparison.csv#full_dual_channel.exact_set_accuracy`; `docs/evaluation/final/summary.json#systems.full_dual_channel.metrics.exact_set_accuracy`  
**Verification type:** archived frozen result

**SCOPE:** Frozen synthetic benchmark only. Exact match means the predicted violation-label set equals the oracle set; supersets or subsets do not match.

**ALLOWED WORDING:**
- “On a frozen 1,200-journey synthetic benchmark, the full dual-channel system achieved 95.0% exact violation-set accuracy.”
- “95.0% exact violation-set accuracy (frozen synthetic benchmark).”

**FORBIDDEN WORDING (do not say):** “95% system accuracy”; “95% camera accuracy”; “95% real-world accuracy”

**LIMITATIONS:** Not a camera, field or real-world accuracy. The 5.0% of non-matching journeys are the 60 weak-physical-evidence cases (see C009).

## C003 — headline_metric — `VERIFIED_WITH_SCOPE`

**CLAIM:** On the frozen synthetic benchmark the full dual-channel system achieved a Macro-F1 of 0.981 (95% bootstrap CI 0.976-0.986).

**EVIDENCE:** Archived macro_f1 0.981156; percentile bootstrap CI [0.976081, 0.985872] (2000 resamples, seed 20261017).

**EVIDENCE SOURCE:** `docs/evaluation/final/system_comparison.csv#full_dual_channel.macro_f1`; `docs/evaluation/final/summary.json#bootstrap.intervals.full_dual_channel.macro_f1`  
**Verification type:** archived frozen result

**SCOPE:** Frozen synthetic benchmark; Macro-F1 is the mean of per-violation-type F1 over the four violation types. The CI is a statistical interval over this synthetic sample, not a field interval.

**ALLOWED WORDING:**
- “Macro-F1 of 0.981 [95% bootstrap CI 0.976-0.986] on the frozen synthetic benchmark.”
- “0.981 Macro-F1 (frozen synthetic benchmark).”

**FORBIDDEN WORDING (do not say):** “98.1% accuracy”; “98.1% detection accuracy”

**LIMITATIONS:** Macro-F1 is an F1 score, not accuracy. Synthetic benchmark only.

## C004 — headline_metric — `VERIFIED_WITH_SCOPE`

**CLAIM:** On the frozen synthetic benchmark the full dual-channel system achieved a Micro-F1 of 0.973.

**EVIDENCE:** Archived micro_f1 0.973262 (MICRO_ALL: 1092 true positives, 60 false positives, 0 false negatives).

**EVIDENCE SOURCE:** `docs/evaluation/final/system_comparison.csv#full_dual_channel.micro_f1`; `docs/evaluation/final/per_class_metrics.csv#full_dual_channel.MICRO_ALL`  
**Verification type:** archived frozen result

**SCOPE:** Frozen synthetic benchmark; micro-averaged over all TYPE:STEP labels.

**ALLOWED WORDING:**
- “Micro-F1 of 0.973 on the frozen synthetic benchmark.”

**FORBIDDEN WORDING (do not say):** “97.3% accuracy”

**LIMITATIONS:** F1 score, not accuracy; synthetic benchmark only.

## C005 — headline_metric — `VERIFIED_WITH_SCOPE`

**CLAIM:** On the frozen synthetic benchmark the full dual-channel system raised an alarm for every one of the 812 violated journeys (0 of 812 without an alarm).

**EVIDENCE:** Archived violated_missed_entirely 0, violated_cases 812, fnr_violated 0.0 for full_dual_channel.

**EVIDENCE SOURCE:** `docs/evaluation/final/system_comparison.csv#full_dual_channel.violated_missed_entirely`; `docs/evaluation/final/system_comparison.csv#full_dual_channel.violated_cases`; `docs/evaluation/final/summary.json#systems.full_dual_channel.metrics`  
**Verification type:** archived frozen result

**SCOPE:** Frozen synthetic benchmark. 'Alarm' means at least one violation label was raised on a journey whose oracle status is VIOLATED.

**ALLOWED WORDING:**
- “The full dual-channel system flagged all 812 violated journeys in the frozen synthetic benchmark (0 of 812 without an alarm).”
- “0 / 812 violated journeys without an alarm.”

**FORBIDDEN WORDING (do not say):** “100% of real security violations are detected”; “100% detection rate in the field”

**LIMITATIONS:** Says nothing about real violations. The same system also raised 60 false phantom-completion alarms on violation-free journeys (C009).

## C006 — per_class — `VERIFIED_WITH_SCOPE`

**CLAIM:** On the frozen synthetic benchmark, phantom completion detection had recall 1.000 and precision 0.860 (F1 0.925).

**EVIDENCE:** Archived per-class row PHANTOM_COMPLETION: truth 368, tp 368, fp 60, fn 0, precision 0.859813, recall 1.0, F1 0.924623.

**EVIDENCE SOURCE:** `docs/evaluation/final/per_class_metrics.csv#full_dual_channel.PHANTOM_COMPLETION`  
**Verification type:** archived frozen result

**SCOPE:** Frozen synthetic benchmark. The 60 false positives are the weak-physical-evidence cases described in C009.

**ALLOWED WORDING:**
- “On the frozen synthetic benchmark, phantom completion recall was 1.000 and precision 0.860 (F1 0.925).”

**FORBIDDEN WORDING (do not say):** “perfect phantom-completion detection”

**LIMITATIONS:** Precision is below 1 because of 60 false alarms; do not describe this class as perfect.

## C007 — per_class — `VERIFIED_WITH_SCOPE`

**CLAIM:** Within the frozen synthetic benchmark, channel contradiction detection had precision, recall and F1 of 1.000 / 1.000 / 1.000.

**EVIDENCE:** Archived per-class row CHANNEL_CONTRADICTION: truth 240, tp 240, fp 0, fn 0.

**EVIDENCE SOURCE:** `docs/evaluation/final/per_class_metrics.csv#full_dual_channel.CHANNEL_CONTRADICTION`  
**Verification type:** archived frozen result

**SCOPE:** Frozen synthetic benchmark only; scope must always be stated alongside the figure.

**ALLOWED WORDING:**
- “Within the frozen synthetic benchmark, channel contradiction was detected with precision, recall and F1 of 1.000.”

**FORBIDDEN WORDING (do not say):** “perfect contradiction detection in practice”; “channel contradictions are always detected”

**LIMITATIONS:** Generated contradiction patterns are clean by construction; real inconsistency patterns may differ.

## C008 — comparative — `VERIFIED_WITH_SCOPE`

**CLAIM:** Cross-channel reasoning enabled detection of phantom completion and channel contradiction that the single-channel ablations and the simple procedure check did not identify.

**EVIDENCE:** Archived per-class rows: physical-only, digital-only and simple-check have recall 0.0 for PHANTOM_COMPLETION (368 missed) and CHANNEL_CONTRADICTION (240 missed); the full system has recall 1.0 for both.

**EVIDENCE SOURCE:** `docs/evaluation/final/per_class_metrics.csv#PHANTOM_COMPLETION`; `docs/evaluation/final/per_class_metrics.csv#CHANNEL_CONTRADICTION`; `docs/evaluation/final/summary.json#cross_channel_benefit_by_type`  
**Verification type:** archived frozen result

**SCOPE:** Frozen synthetic benchmark. Physical-only and digital-only are INTERNAL ABLATIONS of the same engine, not products or competitors. The simple check is a documented rule-based baseline written for this evaluation.

**ALLOWED WORDING:**
- “In the frozen synthetic benchmark, only the dual-channel configuration detected phantom completion and channel contradiction; the internal single-channel ablations and the simple check did not.”
- “Internal ablations show the value of cross-channel reasoning.”

**FORBIDDEN WORDING (do not say):** “MADQAQ beats all competing systems”; “outperforms all”; “outperforms existing systems”; “proves superiority”

**LIMITATIONS:** No external or commercial system was evaluated. Those two violation types are definitionally cross-channel, so single-channel systems cannot detect them by design.

## C009 — limitation — `LIMITATION`

**CLAIM:** The primary known benchmark limitation is weak physical evidence: 60 low-confidence cases produced false phantom-completion alerts.

**EVIDENCE:** Archived PHANTOM_COMPLETION fp = 60; family weak_physical_midjourney: 60 cases, 0 exact matches, 60 false-positive labels. The engine treats a sub-threshold physical observation as absent and raises PHANTOM_COMPLETION where the oracle expects UNCERTAIN. fpr_violation_free 0.154639 (60/388).

**EVIDENCE SOURCE:** `docs/evaluation/final/per_class_metrics.csv#full_dual_channel.PHANTOM_COMPLETION.fp`; `docs/evaluation/final/family_breakdown.csv#weak_physical_midjourney`; `docs/evaluation/final/README.md`; `docs/M4_COMPARATIVE_EVALUATION.md#10`  
**Verification type:** archived frozen result

**SCOPE:** Frozen synthetic benchmark. Disclosed after the development run; no engine or oracle change was made.

**ALLOWED WORDING:**
- “The primary known benchmark limitation is weak physical evidence: 60 low-confidence cases produced false phantom-completion alerts.”
- “This reflects conservative evidence handling and has not been validated as an operationally optimal policy.”

**FORBIDDEN WORDING (do not say):** “no false alarms”; “no known limitations”; “zero false positives”

**LIMITATIONS:** Reflects conservative evidence handling; not validated as an operationally optimal policy. Future work: a calibrated treatment of sub-threshold physical evidence.

## C010 — live_demonstration — `DEMONSTRATED`

**CLAIM:** The current prototype can convert live camera observations into temporary physical procedure events.

**EVIDENCE:** M1 live pipeline (person detector, tracker, zone logic, event emitter) demonstrated on a webcam; unit tests cover zone and event logic without a camera.

**EVIDENCE SOURCE:** `docs/M1_LIVE_VISION.md`; `tests/vision/`  
**Verification type:** live demonstration and unit tests

**SCOPE:** Live demonstration of the pipeline. No accuracy, latency or field figure is claimed for it.

**ALLOWED WORDING:**
- “The prototype converts live camera observations into temporary physical procedure events.”

**FORBIDDEN WORDING (do not say):** “The vision system is 95% accurate”; “Validated camera performance”; “validated vision accuracy”

**LIMITATIONS:** No camera accuracy has been measured. The 95.0% figure is NOT a vision metric.

## C011 — live_demonstration — `DEMONSTRATED`

**CLAIM:** The prototype demonstrates live physical evidence combined with a SIMULATED DIGITAL CHANNEL.

**EVIDENCE:** M2 dual-channel coordinator with a local digital event simulator (metadata source m2_digital_simulator, simulated true); shown on the M3 dashboard as SIMULATED DIGITAL CHANNEL.

**EVIDENCE SOURCE:** `docs/M2_DUAL_CHANNEL.md`; `docs/M3_FINALIST_DEMO.md`  
**Verification type:** live demonstration and unit tests

**SCOPE:** Demonstration of cross-channel logic with a local simulator.

**ALLOWED WORDING:**
- “Live physical evidence combined with a SIMULATED DIGITAL CHANNEL.”
- “The digital channel is a local simulator.”

**FORBIDDEN WORDING (do not say):** “real government checkpoint database”; “production border systems integration”; “connected to a live checkpoint system”; “integrated with government systems”

**LIMITATIONS:** No integration with any real checkpoint, credential or border system exists.

## C012 — design_property — `DEMONSTRATED`

**CLAIM:** The current prototype uses temporary journey tracking and does not require face recognition or persistent identity.

**EVIDENCE:** Design and code: only a temporary tracker ID and a random journey UUID held in memory; no face detection, embeddings or identity fields; frames are processed in memory.

**EVIDENCE SOURCE:** `docs/M1_LIVE_VISION.md#privacy-design`; `docs/M3_FINALIST_DEMO.md#privacy-design`  
**Verification type:** design property and code review

**SCOPE:** Current prototype design. This is a design property, not a certified privacy or security guarantee.

**ALLOWED WORDING:**
- “The prototype uses temporary journey tracking and does not require face recognition or persistent identity.”

**FORBIDDEN WORDING (do not say):** “guarantees privacy”; “completely anonymous”; “privacy-proof”; “cannot be misused”

**LIMITATIONS:** No formal privacy assessment has been performed. Deployment would need its own privacy and legal review.

## C013 — performance — `VERIFIED_WITH_SCOPE`

**CLAIM:** Deterministic engine evaluation required tens of microseconds per case in the recorded benchmark environment (ENGINE EVALUATION ONLY).

**EVIDENCE:** Archived final report latency table, full system: median 23.5 us, P95 48.5 us, P99 69.5 us over 6000 samples, measured in a sandbox (Python 3.12, Intel i7-10750H, 2 CPUs).

**EVIDENCE SOURCE:** `docs/evaluation/final/report.md#latency`; `docs/evaluation/final/FINAL_RUN_RECORD.json#environment`  
**Verification type:** archived frozen result

**SCOPE:** ENGINE EVALUATION ONLY: evidence already present as domain events. Excludes camera capture, YOLO inference, tracking, UI rendering and any external-system latency. Environment-specific.

**ALLOWED WORDING:**
- “ENGINE EVALUATION ONLY: deterministic engine evaluation required tens of microseconds per case in the recorded benchmark environment.”

**FORBIDDEN WORDING (do not say):** “system latency”; “camera latency”; “end-to-end latency”; “real-time guarantee”

**LIMITATIONS:** Measured once in a sandbox. Not a system, camera or end-to-end figure.

## C014 — reproducibility — `VERIFIED_WITH_SCOPE`

**CLAIM:** The frozen final split reproduced the development benchmark's overall full-system metrics closely.

**EVIDENCE:** Development run (300 journeys, seed 20261017): exact-set accuracy 0.950, Macro-F1 0.981156, Micro-F1 0.973262, PHANTOM_COMPLETION precision 0.859813. Final run: 0.950, 0.981156, 0.973262, 0.859813. Dev point estimates are from the local, regenerable dev run (not archived in docs/).

**EVIDENCE SOURCE:** `docs/evaluation/final/system_comparison.csv#full_dual_channel`; `docs/M4_COMPARATIVE_EVALUATION.md#5`; `docs/evaluation/final/README.md`  
**Verification type:** archived frozen result and descriptive comparison

**SCOPE:** The final split is independently seeded but is generated from the same procedural distribution and composition design as the development split. It is a frozen held-out synthetic benchmark, not an out-of-distribution or real-world validation set.

**ALLOWED WORDING:**
- “The frozen final split, independently seeded but generated from the same procedural distribution and composition design, reproduced the development benchmark's overall full-system metrics closely.”

**FORBIDDEN WORDING (do not say):** “independent real-world validation”; “out-of-distribution validation”; “statistically significant”

**LIMITATIONS:** Descriptive comparison only; no significance test was run. Agreement is expected because both splits share a generator design.

## C015 — readiness — `NOT_SUPPORTED`

**CLAIM:** Production readiness, field validation and operational deployment readiness are NOT supported by the evidence.

**EVIDENCE:** No field trial, no real checkpoint integration, no measured camera accuracy, synthetic benchmark only.

**EVIDENCE SOURCE:** `docs/evaluation/final/README.md`; `docs/M4_COMPARATIVE_EVALUATION.md`  
**Verification type:** absence of evidence (explicitly not claimed)

**SCOPE:** Applies to every material in the finalist package.

**ALLOWED WORDING:**
- “research prototype”
- “working proof of concept”
- “finalist demonstration prototype”

**FORBIDDEN WORDING (do not say):** “production ready”; “production-ready”; “field validated”; “deployment ready”; “government approved”; “operationally proven”

**LIMITATIONS:** Position the work as a research prototype, a working proof of concept and a finalist demonstration prototype.
