# MADQAQ Sentinel — M4.1 comparative evaluation (final benchmark)

## Scope and disclaimers

- This benchmark uses procedurally generated synthetic event sequences. It evaluates deterministic procedure-integrity reasoning, not live-camera accuracy or field performance.
- The physical-only and digital-only systems are internal ablations, not external commercial baselines.
- Confidence intervals are bootstrap statistical intervals over this synthetic benchmark sample; they are not field-performance confidence intervals.
- Latency is engine evaluation latency only: it measures the time to evaluate evidence that already exists as events and excludes camera capture, YOLO detection, tracking and UI rendering. It is not end-to-end latency and it is specific to the machine that measured it.
- This report covers the FINAL split: the frozen benchmark (seed 20261123), evaluated once with the frozen M4.1 systems and metric definitions. No engine, oracle, generator, threshold or case was changed after the results were observed.
- No claim is made about camera accuracy, field accuracy, deployment readiness, real digital-system integration or superiority over any external system.

## Benchmark

- Benchmark version `mbench-1.0`, generator `mgen-1.0`, split `final`, seed `20261123`, **1200 journeys**.
- Dataset SHA-256 `28a3979e7e690cb0957502237f9145a24d816182196179788eaeae8738d48697`; candidates rejected as ambiguous during generation: 0.
- Ground truth is created by the generator and cross-checked by an independent oracle; the ConformanceEngine is never used to produce labels.

**Ground-truth status:** COMPLETED 208, UNCERTAIN 180, VIOLATED 812

**Violation labels by type:** CHANNEL_CONTRADICTION 240, OMISSION 296, ORDER_INVERSION 188, PHANTOM_COMPLETION 368

**Violations per case:** 0: 388 cases, 1: 532 cases, 2: 280 cases

**Subsets:** boundary 180, core 780, robustness 240

**Noise conditions in the robustness subset:** digital_delay 49, digital_duplicate_delivery 46, digital_repeated_record 47, physical_duplicate_delivery 55, physical_low_conf_duplicate 46, physical_repeated_observation 48, timestamp_jitter 48

## Evaluated systems

| System | Channels | Description |
|---|---|---|
| MADQAQ full dual-channel | DIGITAL+PHYSICAL | The unmodified M0 ConformanceEngine given both physical and digital evidence. |
| Physical-only ablation | PHYSICAL | The same ConformanceEngine with the digital channel removed: it receives physical evidence only (an internal ablation, not an external product). |
| Digital-only ablation | DIGITAL | The same ConformanceEngine with the physical channel removed: it receives digital evidence only (an internal ablation, not an external product). |
| Simple procedure-check baseline | DIGITAL+PHYSICAL | Transparent required-steps-present + monotonic-order checker; no cross-channel reasoning. |

**Simple procedure-check baseline — exact rules**

1. A step appears if a physical STEP_OBSERVED (confidence >= 0.50) or a digital STEP_COMPLETED names it; STEP_FAILED never counts.
1. OMISSION:X is raised for every required step X that appears in neither channel.
1. ORDER_INVERSION:X is raised for every step X that occurs after a higher-order step within one channel's collapsed time-ordered sequence; channels are never merged.
1. Status is VIOLATED if any label was raised, otherwise COMPLETED; there is no UNCERTAIN.
1. No cross-channel contradiction and no unsupported-digital-completion (phantom) reasoning.

## Primary results

Intervals: 95% percentile bootstrap, 2000 resamples, seed 20261017. Confidence intervals are bootstrap statistical intervals over this synthetic benchmark sample; they are not field-performance confidence intervals.

| System | Cases | Exact violation-set accuracy | Macro-F1 | Micro-F1 | Status accuracy |
|---|---|---|---|---|---|
| MADQAQ full dual-channel | 1200 | 95.0% [93.8%, 96.2%] | 0.981 [0.976, 0.986] | 0.973 | 95.0% [93.8%, 96.2%] |
| Physical-only ablation | 1200 | 51.7% [48.8%, 54.5%] | 0.395 [0.386, 0.404] | 0.483 | 62.7% [59.8%, 65.4%] |
| Digital-only ablation | 1200 | 56.7% [53.9%, 59.6%] | 0.440 [0.431, 0.447] | 0.548 | 60.1% [57.3%, 62.8%] |
| Simple procedure-check baseline | 1200 | 56.7% [53.9%, 59.6%] | 0.500 [0.500, 0.500] | 0.614 | 54.3% [51.4%, 57.1%] |

| System | FPR, conformant journeys | FPR, all violation-free journeys | FNR, violated journeys (no violation raised) | Label miss rate | Predicted UNCERTAIN | Ground-truth UNCERTAIN |
|---|---|---|---|---|---|---|
| MADQAQ full dual-channel | 0.0% (0/208) | 15.5% (60/388) | 0.0% (0/812) | 0.0% | 10.0% | 15.0% |
| Physical-only ablation | 0.0% (0/208) | 15.5% (60/388) | 17.2% (140/812) | 55.7% | 35.7% | 15.0% |
| Digital-only ablation | 0.0% (0/208) | 0.0% (0/388) | 28.4% (231/812) | 55.7% | 48.2% | 15.0% |
| Simple procedure-check baseline | 0.0% (0/208) | 0.0% (0/388) | 45.3% (368/812) | 55.7% | 0.0% | 15.0% |

A single-channel system cannot certify dual-channel agreement, so by the engine's design it reports UNCERTAIN rather than COMPLETED on a clean trace; its status accuracy and uncertain rate reflect that design rule. Violation-level metrics are the primary comparison.

### Paired differences (full dual-channel minus each other system)

| Versus | Macro-F1 difference | Exact-set accuracy difference | Status accuracy difference |
|---|---|---|---|
| Physical-only ablation | +0.586 [+0.575, +0.597] | +0.433 [+0.404, +0.461] | +0.323 [+0.298, +0.351] |
| Digital-only ablation | +0.542 [+0.533, +0.551] | +0.383 [+0.350, +0.415] | +0.349 [+0.317, +0.383] |
| Simple procedure-check baseline | +0.481 [+0.476, +0.486] | +0.383 [+0.350, +0.415] | +0.407 [+0.379, +0.435] |

## Per-violation-type metrics

**OMISSION**

| System | Truth labels | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| MADQAQ full dual-channel | 296 | 296 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| Physical-only ablation | 296 | 296 | 428 | 0 | 0.409 | 1.000 | 0.580 |
| Digital-only ablation | 296 | 296 | 189 | 0 | 0.610 | 1.000 | 0.758 |
| Simple procedure-check baseline | 296 | 296 | 0 | 0 | 1.000 | 1.000 | 1.000 |

**ORDER_INVERSION**

| System | Truth labels | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| MADQAQ full dual-channel | 188 | 188 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| Physical-only ablation | 188 | 188 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| Digital-only ablation | 188 | 188 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| Simple procedure-check baseline | 188 | 188 | 0 | 0 | 1.000 | 1.000 | 1.000 |

**PHANTOM_COMPLETION**

| System | Truth labels | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| MADQAQ full dual-channel | 368 | 368 | 60 | 0 | 0.860 | 1.000 | 0.925 |
| Physical-only ablation | 368 | 0 | 0 | 368 | n/a | 0.000 | 0.000 |
| Digital-only ablation | 368 | 0 | 0 | 368 | n/a | 0.000 | 0.000 |
| Simple procedure-check baseline | 368 | 0 | 0 | 368 | n/a | 0.000 | 0.000 |

**CHANNEL_CONTRADICTION**

| System | Truth labels | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| MADQAQ full dual-channel | 240 | 240 | 0 | 0 | 1.000 | 1.000 | 1.000 |
| Physical-only ablation | 240 | 0 | 0 | 240 | n/a | 0.000 | 0.000 |
| Digital-only ablation | 240 | 0 | 0 | 240 | n/a | 0.000 | 0.000 |
| Simple procedure-check baseline | 240 | 0 | 0 | 240 | n/a | 0.000 | 0.000 |

**MICRO_ALL**

| System | Truth labels | TP | FP | FN | Precision | Recall | F1 |
|---|---|---|---|---|---|---|---|
| MADQAQ full dual-channel | 1092 | 1092 | 60 | 0 | 0.948 | 1.000 | 0.973 |
| Physical-only ablation | 1092 | 484 | 428 | 608 | 0.531 | 0.443 | 0.483 |
| Digital-only ablation | 1092 | 484 | 189 | 608 | 0.719 | 0.443 | 0.548 |
| Simple procedure-check baseline | 1092 | 484 | 0 | 608 | 1.000 | 0.443 | 0.614 |

Zero-denominator convention: precision/recall are undefined (null) when their denominator is 0; F1 = 2TP/(2TP+FP+FN) is undefined only when that denominator is 0; macro-F1 averages the defined per-type F1 values; rates with a zero denominator are null.

## Research questions

### Q1. Does dual-channel reasoning detect violations that physical-only evidence cannot?

| Violation type | Truth labels | Recall: full | Recall: Physical-only ablation | Difference |
|---|---|---|---|---|
| OMISSION | 296 | 1.000 | 1.000 | +0.000 |
| ORDER_INVERSION | 188 | 1.000 | 1.000 | +0.000 |
| PHANTOM_COMPLETION | 368 | 1.000 | 0.000 | +1.000 |
| CHANNEL_CONTRADICTION | 240 | 1.000 | 0.000 | +1.000 |

On this benchmark the full system's recall exceeds the physical-only ablation's for: PHANTOM_COMPLETION, CHANNEL_CONTRADICTION. By exact violation-set match, 520 cases were matched only by the full system and 0 only by the physical-only ablation (620 by both, 60 by neither).

### Q2. Does it detect violations that digital-only evidence cannot?

| Violation type | Truth labels | Recall: full | Recall: Digital-only ablation | Difference |
|---|---|---|---|---|
| OMISSION | 296 | 1.000 | 1.000 | +0.000 |
| ORDER_INVERSION | 188 | 1.000 | 1.000 | +0.000 |
| PHANTOM_COMPLETION | 368 | 1.000 | 0.000 | +1.000 |
| CHANNEL_CONTRADICTION | 240 | 1.000 | 0.000 | +1.000 |

On this benchmark the full system's recall exceeds the digital-only ablation's for: PHANTOM_COMPLETION, CHANNEL_CONTRADICTION. By exact violation-set match, 520 cases were matched only by the full system and 60 only by the digital-only ablation (620 by both, 0 by neither).

### Q3. Which violation types benefit specifically from cross-channel evidence?

| Violation type | Truth labels | Recall: full | Recall: best single channel | Recall gain |
|---|---|---|---|---|
| OMISSION | 296 | 1.000 | 1.000 | +0.000 |
| ORDER_INVERSION | 188 | 1.000 | 1.000 | +0.000 |
| PHANTOM_COMPLETION | 368 | 1.000 | 0.000 | +1.000 |
| CHANNEL_CONTRADICTION | 240 | 1.000 | 0.000 | +1.000 |

Recall gain over the better single-channel ablation is positive for: PHANTOM_COMPLETION, CHANNEL_CONTRADICTION. The benchmark deliberately contains faults that exist only as a disagreement between channels, so part of this gain is structural; the magnitudes, the compound cases and the false-alarm results below are the informative parts.

### Q4. How often does each method produce false alarms?

| System | False alarms on conformant journeys | False alarms on all violation-free journeys | False-positive labels (all cases) |
|---|---|---|---|
| MADQAQ full dual-channel | 0/208 | 60/388 | 60 |
| Physical-only ablation | 0/208 | 60/388 | 428 |
| Digital-only ablation | 0/208 | 0/388 | 189 |
| Simple procedure-check baseline | 0/208 | 0/388 | 0 |

- MADQAQ full dual-channel: weak_physical_midjourney (boundary): 60 labels over 60 cases.
- Physical-only ablation: weak_physical_midjourney (boundary): 60 labels over 60 cases.
- Digital-only ablation: no false alarms on violation-free families.
- Simple procedure-check baseline: no false alarms on violation-free families.

### Q5. What is the deterministic engine-evaluation latency?

| System | Samples | Median (µs) | P95 (µs) | P99 (µs) |
|---|---|---|---|---|
| MADQAQ full dual-channel | 6000 | 23.5 | 48.5 | 69.5 |
| Physical-only ablation | 6000 | 20.5 | 42.1 | 59.0 |
| Digital-only ablation | 6000 | 19.8 | 39.6 | 56.9 |
| Simple procedure-check baseline | 6000 | 5.0 | 6.8 | 26.2 |

Measured with `time.perf_counter_ns` after a warm-up of 100 evaluations; Python 3.12.14 (CPython), Linux-6.8.0-138-generic-x86_64-with-glibc2.35, machine x86_64, 2 logical CPUs. Latency is engine evaluation latency only: it measures the time to evaluate evidence that already exists as events and excludes camera capture, YOLO detection, tracking and UI rendering. It is not end-to-end latency and it is specific to the machine that measured it.

**Engine evaluation latency only. This excludes camera capture, YOLO inference, tracking, UI rendering, and external-system latency.**

## Results by scenario family (exact violation-set match rate)

| Subset / family | Cases | MADQAQ full dual-channel | Physical-only ablation | Digital-only ablation | Simple procedure-check baseline |
|---|---|---|---|---|---|
| boundary / uncertain_digital_only | 40 | 100% | 100% | 100% | 100% |
| boundary / uncertain_physical_only | 40 | 100% | 100% | 100% | 100% |
| boundary / weak_physical_midjourney | 60 | 0% | 0% | 100% | 100% |
| boundary / weak_physical_tail | 40 | 100% | 100% | 100% | 100% |
| core / compound_contradiction_omission | 40 | 100% | 0% | 0% | 0% |
| core / compound_phantom_contradiction | 40 | 100% | 0% | 0% | 0% |
| core / compound_phantom_inversion | 40 | 100% | 0% | 0% | 0% |
| core / compound_phantom_omission | 40 | 100% | 0% | 0% | 0% |
| core / conformant_clean | 160 | 100% | 100% | 100% | 100% |
| core / contradiction_single | 100 | 100% | 0% | 0% | 0% |
| core / inversion_single | 100 | 100% | 100% | 100% | 100% |
| core / omission_double | 40 | 100% | 100% | 100% | 100% |
| core / omission_single | 80 | 100% | 100% | 100% | 100% |
| core / phantom_double | 40 | 100% | 0% | 0% | 0% |
| core / phantom_single | 100 | 100% | 0% | 0% | 0% |
| robustness / compound_contradiction_omission | 12 | 100% | 0% | 0% | 0% |
| robustness / compound_phantom_contradiction | 8 | 100% | 0% | 0% | 0% |
| robustness / compound_phantom_inversion | 8 | 100% | 0% | 0% | 0% |
| robustness / compound_phantom_omission | 12 | 100% | 0% | 0% | 0% |
| robustness / conformant_clean | 48 | 100% | 100% | 100% | 100% |
| robustness / contradiction_single | 40 | 100% | 0% | 0% | 0% |
| robustness / inversion_single | 40 | 100% | 100% | 100% | 100% |
| robustness / omission_single | 32 | 100% | 100% | 100% | 100% |
| robustness / phantom_single | 40 | 100% | 0% | 0% | 0% |

## Limitations

- Known development-set limitation: when a procedure step is physically observed only below the configured confidence threshold but is correctly recorded by the digital channel, the current engine may classify the digital completion as PHANTOM_COMPLETION rather than UNCERTAIN. In the development benchmark this occurred in 15 weak-physical-evidence cases. No engine or oracle changes were made after observing this result. This represents conservative evidence handling and has not been validated as an operationally optimal policy.
- The benchmark is procedurally generated from one four-step linear procedure; it contains no real sensor data, no camera or detector errors beyond a confidence band, and no real digital-system logs.
- Ground truth follows benchmark definitions (BDEF-1) written by the same team that built the engine; it is independent of the engine's code but not of the team's notion of correctness.
- Compound cases combine faults on distinct steps only; same-step multi-fault cases are excluded as ambiguous. Journeys are complete (they reach the final step); truncated journeys are out of scope.
- Some families (phantom completion, channel contradiction) are constructed so that they require both channels; the resulting advantage over single-channel ablations is partly by construction.
- The weak-observation families depend on the benchmark's definition that a performed-but-weakly-observed step is not a fault; other defensible definitions exist.
- The ablations reuse the same engine code with one channel removed, so they measure each channel's contribution, not alternative designs. The simple baseline is one possible simple checker.
- Bootstrap intervals assume cases are independent draws from this benchmark's designer-chosen composition and say nothing about field performance.
- These are FINAL-split results from a single frozen run; the weak-observation limitation above was accepted before the run and is not reinterpreted here.
- Latency is machine-specific and measures engine evaluation only.

## Reproduction

```
python -m apps.evaluation.main evaluate --split final --unlock-final-evaluation
```
