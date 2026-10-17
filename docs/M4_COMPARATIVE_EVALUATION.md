# M4.1 — Comparative evaluation infrastructure

> This benchmark uses procedurally generated synthetic event sequences. It evaluates deterministic procedure-integrity reasoning, not live-camera accuracy or field performance.
>
> The physical-only and digital-only systems are internal ablations, not external commercial baselines.

M4 is a **scientific evaluation layer**. It adds no model, trains nothing, and does not change M0, M1, M2 or M3. M4.1 builds and reviews the harness and runs it on the **development** benchmark only; the **final** benchmark is generated and frozen but not evaluated (that is M4.2).

## 1. Research question

How much does MADQAQ Sentinel's *dual-channel* reasoning contribute, compared with the same reasoning restricted to one channel and with a simple transparent checker?

1. Does dual-channel reasoning detect procedure-integrity violations that physical-only evidence cannot?
2. Does it detect violations that digital-only evidence cannot?
3. Which violation types benefit specifically from cross-channel evidence?
4. How often does each method produce false alarms?
5. What is the deterministic engine-evaluation latency?

Because nothing is learned, the vocabulary is *development benchmark* and *frozen final benchmark* — not train/test.

## 2. Evaluated systems

| Id | Name | What it receives | What it is |
|---|---|---|---|
| `full_dual_channel` | MADQAQ full dual-channel | physical + digital | the unmodified M0 `ConformanceEngine` |
| `physical_only_ablation` | Physical-only ablation | physical only | the same engine with the digital channel removed |
| `digital_only_ablation` | Digital-only ablation | digital only | the same engine with the physical channel removed |
| `simple_procedure_check` | Simple procedure-check baseline | both, never reasoned across | transparent presence + order checker |

The ablations are **internal**: they measure what each channel contributes to *this* engine. They are not external products and nothing here compares MADQAQ with an external system.

**Channel isolation** is enforced twice. The runner narrows the evidence it passes to a system (`Evidence.restricted_to`), and a single-channel system *refuses* any event from the other channel (`ChannelIsolationError`) rather than silently dropping it.

### Simple procedure-check baseline — exact rules

1. A step *appears* if a physical `STEP_OBSERVED` (confidence ≥ 0.50) or a digital `STEP_COMPLETED` names it. `STEP_FAILED` never counts as appearing.
2. `OMISSION:X` for every required step `X` that appears in neither channel.
3. `ORDER_INVERSION:X` for every step `X` occurring after a higher-order step within **one channel's** time-ordered, consecutive-duplicate-collapsed sequence. Channels are never merged.
4. Status is `VIOLATED` if any label was raised, else `COMPLETED`. There is no `UNCERTAIN`.
5. No cross-channel contradiction and no unsupported-digital-completion (phantom) reasoning.

It is meant to be a reasonable simple checker, not a straw man: it tolerates duplicates, ignores below-threshold physical observations, and is insensitive to clock offsets between channels.

## 3. Ground truth: the oracle (BDEF-1)

**Ground truth is independent of the system under test.** `ConformanceEngine` is never called to produce a label — a test patches `evaluate` to raise during generation, and an AST test forbids the label modules from importing the engine.

Each case is built from a **latent world** — what really happened, before any sensing or logging noise:

- `performed`: the steps really performed, in true order;
- `weak_physical`: performed steps seen by the camera only at low confidence;
- `physical_online` / `digital_online`: whether each channel exists at all (outages);
- `digital_record`: what the digital system recorded (`COMPLETED`/`FAILED`).

Rules (all four steps required; CP = confidently observed performed steps):

| Label | Definition |
|---|---|
| `CHANNEL_CONTRADICTION:X` | X is in CP and the digital record says X `FAILED` |
| `PHANTOM_COMPLETION:X` | digital says X `COMPLETED`, X was **not** performed, and the subject confidently progressed beyond X |
| `ORDER_INVERSION:X` | X is in CP and a higher-order CP step was performed before X (related step = the highest such step) |
| `OMISSION:X` | X not performed, no digital record for X, and a later step is evidenced |
| status | `VIOLATED` if any label; `COMPLETED` if both channels are online and every step is confidently observed *and* digitally completed; otherwise `UNCERTAIN` |

*Principle: no violation without positive evidence of a fault.* A performed step that was only weakly observed is not a fault; it merely prevents certification.

Labels carry both type **and** step (`OMISSION:B`). The label step for an inversion is the step that was due earlier but happened late, matching the project's M0 convention (`A C B D` → `ORDER_INVERSION:B`).

Two independent paths must agree: every scenario family states its labels *by construction*, and `oracle.derive_ground_truth` re-derives them from the latent world. A disagreement raises `GeneratorInvariantError` (a bug, never a silent relabel). `oracle.audit_case` then audits every case: stored vs derived truth, ambiguity, and whether the (possibly noisy) event streams still realise the latent world.

### Ambiguity — rejected, never silently labelled

A candidate case is **rejected and regenerated** (deterministically, with the next attempt number) when:

- two ground-truth violations target the same step;
- a `FAILED` digital record sits on a step that is not confidently observed;
- a weakly observed step is also out of order, or a step is revisited;
- noise changes a channel's step order, ties timestamps, or otherwise stops the evidence matching the latent world.

Consequently compound cases combine faults on *distinct steps only*, and journeys are complete (they reach the final step). The manifest records `rejected_candidates`.

## 4. Benchmark composition

Per 300 journeys (the development split is 1× this, the final split 4×):

| Subset | Family | Cases | Ground truth |
|---|---|---:|---|
| core | `conformant_clean` | 40 | `COMPLETED` |
| core | `omission_single` / `omission_double` | 20 / 10 | `OMISSION:B\|C` / both |
| core | `inversion_single` | 25 | `ORDER_INVERSION` (3 patterns) |
| core | `phantom_single` / `phantom_double` | 25 / 10 | `PHANTOM_COMPLETION` |
| core | `contradiction_single` | 25 | `CHANNEL_CONTRADICTION:B\|C\|D` |
| core | four `compound_*` families | 10 each | two labels on distinct steps |
| boundary | `uncertain_physical_only`, `uncertain_digital_only` | 10 each | `UNCERTAIN` (a channel is offline) |
| boundary | `weak_physical_midjourney`, `weak_physical_tail` | 15 / 10 | `UNCERTAIN` (a performed step seen only weakly) |
| robustness | noisy copies of the families above | 60 | unchanged by the noise |

Robustness noise operators (applied only where the truth stays unambiguous): `timestamp_jitter` (±3 s), `digital_delay` (+3–30 s), `physical_repeated_observation`, `digital_repeated_record`, `physical_low_conf_duplicate`, `physical_duplicate_delivery`, `digital_duplicate_delivery`. Confidence bands are kept far from the 0.50 threshold (confident 0.80–1.00, weak 0.10–0.35).

Cases are JSONL (`benchmark.jsonl`) with: `case_id`, `benchmark_version`, `generator_version`, `split`, `seed`, `index`, `subset`, `scenario_family`, `noise_conditions`, `procedure`, `world`, `physical_events`, `digital_events`, `ground_truth_status`, `ground_truth_violations` (type, step, related step), `ground_truth_labels`. No images, no identity, no personal data.

## 5. Development vs final split

| | development | final |
|---|---|---|
| seed | `20261017` | `20261123` |
| size | 300 | 1200 |
| ids | `DEV-0001…` | `FIN-0001…` |
| M4.1 | generated **and evaluated** | generated, verified, **not evaluated** |

The final split exists so the implementation cannot be tuned after seeing final scores. In M4.1 only the schema, case count, determinism and class distribution of the final split are checked; **no system metric is computed on it.** Golden SHA-256 hashes of both datasets are pinned in `tests/evaluation/test_reproducibility.py`; changing a dataset requires bumping the generator/benchmark version and the hashes on purpose.

### Final-evaluation lock

- `evaluate`/`run`/`report` with `--split final` exit with code 2 before any file is touched.
- Below the CLI, `evaluate_cases` itself refuses any `final` case: without `unlock_final` it raises, and with it (`--unlock-final-evaluation`) it *still* raises while `FINAL_EVALUATION_ENABLED` is `False`. Enabling it is a deliberate, reviewed code change for M4.2.
- Mixing a single final case into a dev run trips the lock too; a tripwire test proves no system is ever invoked on final cases.

## 6. Metrics

Violation detection is evaluated as **multi-label classification** over labels `TYPE:STEP`; a predicted label is a true positive only if type *and* step match.

- per-violation-type TP / FP / FN, precision, recall, F1; macro-F1 and micro-F1;
- exact violation-set match accuracy (two empty sets match; a superset or subset does not);
- false-positive rate on conformant journeys (ground truth `COMPLETED`), and over *all* violation-free journeys (adds `UNCERTAIN` ground truth);
- false-negative rate on violated journeys (no violation raised) and the stricter label-level miss rate;
- overall status accuracy over `COMPLETED / VIOLATED / UNCERTAIN` (`ACTIVE` can be predicted and is then wrong), and uncertain rate.

`UNCERTAIN` is a status, not a violation.

**Zero-denominator convention.** Precision and recall are *undefined* (`null`) when their denominator is 0. F1 = 2TP/(2TP+FP+FN) is undefined only when that denominator is 0 (type absent from truth and predictions); a type present in truth but never predicted has F1 = 0. Macro-F1 averages the defined per-type F1 values. Rates with a zero denominator are `null`.

A single-channel system cannot certify dual-channel agreement, so by the engine's design it reports `UNCERTAIN` rather than `COMPLETED` on a clean trace. Its status accuracy and uncertain rate reflect that rule; violation-level metrics are the primary comparison.

## 7. Statistical intervals

95 % percentile bootstrap over cases (2000 resamples, fixed seed `20261017`, `StableRandom` so it does not depend on the Python version). The **same resamples** are used for every system, so differences versus the full system are *paired*. These are statistical intervals over this synthetic benchmark sample, not field-performance confidence intervals. A macro-F1 interval can be degenerate (`[0.5, 0.5]`) when a system's per-type F1 values are exactly 1 or 0 on every resample.

## 8. Latency scope

Engine **evaluation** latency only: the time for a system to evaluate evidence that already exists as domain events, measured with `time.perf_counter_ns` after a 100-evaluation warm-up (garbage collection paused while timing), 5 passes over the dev cases. Median, P95 (nearest-rank) and P99, in microseconds, with Python / OS / CPU information. It excludes camera capture, YOLO detection, tracking, event construction and UI rendering, so it is **not** end-to-end latency, and it is specific to the machine that measured it. It is written to `latency.json`, not `summary.json`, so the deterministic files stay byte-reproducible.

## 9. Outputs

`artifacts/evaluation/<split>/` (git-ignored): `benchmark.jsonl`, `manifest.json`, and for `dev` also `summary.json`, `per_class_metrics.csv`, `system_comparison.csv`, `family_breakdown.csv`, `case_results.jsonl`, `report.md`, `latency.json`, `run_info.json`. All except `report.md`'s latency section, `latency.json` and `run_info.json` are byte-identical across runs.

## 10. Known development-set limitation (reported, not tuned)

> Known development-set limitation: when a procedure step is physically observed only below the configured confidence threshold but is correctly recorded by the digital channel, the current engine may classify the digital completion as PHANTOM_COMPLETION rather than UNCERTAIN. In the development benchmark this occurred in 15 weak-physical-evidence cases. No engine or oracle changes were made after observing this result.

This represents conservative evidence handling and has not been validated as an operationally optimal policy.

Details: in `weak_physical_midjourney` a performed step is seen only below the 0.50 threshold while the digital record is correct. The engine's phantom rule treats a sub-threshold observation as absent; BDEF-1 treats it as not a fault (status `UNCERTAIN`, empty violation set). The digital-only ablation and the simple baseline raise no violation there.

**Oracle review decision (M4.1 freeze):** the oracle definition is kept unchanged. These cases are *not* relabelled to match the engine, and the 15 false `PHANTOM_COMPLETION` predictions are accepted as a genuine known limitation. The engine, oracle semantics, generator, development cases, final cases and thresholds were not modified. The M4.1 benchmark definition (`mbench-1.0` / `mgen-1.0`) is frozen; golden hashes pin both splits.

## 11. Limitations

- Procedurally generated from one linear four-step procedure; no real sensor data, no detector errors beyond a confidence band, no real digital-system logs.
- BDEF-1 was written by the team that built the engine: independent of the engine's *code*, not of the team's notion of correctness. Agreement on families where definitions coincide is expected; disagreement is most informative in the boundary families.
- Phantom and contradiction families are constructed to need both channels, so part of the advantage over single-channel ablations is structural. The informative parts are the magnitudes, the compound cases and the false-alarm results.
- Same-step multi-fault cases and truncated journeys are out of scope.
- Ablations reuse the same engine code, so they measure channel contribution, not alternative designs; the simple baseline is one possible simple checker.
- Bootstrap intervals assume cases are independent draws from a designer-chosen composition.
- Development results only; the development set was visible during implementation.
- Latency is machine-specific.

## 12. Reproduce

```bash
pip install -e ".[dev]"    # no vision extras needed

python -m apps.evaluation.main generate --split dev    # benchmark + manifest
python -m apps.evaluation.main evaluate --split dev    # metrics, CSV/JSON, latency
python -m apps.evaluation.main report --split dev      # report.md
python -m apps.evaluation.main run --split dev         # all three in one command

python -m apps.evaluation.main generate --split final  # allowed: frozen manifest only

python -m pytest                                       # includes tests/evaluation
```

Do **not** run `evaluate`/`run` with `--split final` in M4.1; they are blocked and `--unlock-final-evaluation` does not lift the M4.1 lock.
