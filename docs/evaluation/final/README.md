# M4.2 FINAL evaluation — archived provenance

This directory archives the frozen evidence of the single M4.2 FINAL evaluation of MADQAQ Sentinel. The files are byte-for-byte copies of the run outputs in `artifacts/evaluation/final/`; no metric value was altered or regenerated. Verify them with `SHA256SUMS.txt`:

```bash
cd docs/evaluation/final && sha256sum -c SHA256SUMS.txt
```

## Provenance

| Item | Value |
|---|---|
| Frozen M4.1 commit | `f3b544d` |
| Final benchmark seed | `20261123` |
| Case count | 1200 |
| Benchmark SHA-256 | `28a3979e7e690cb0957502237f9145a24d816182196179788eaeae8738d48697` (`28a3979e…8697`) |
| Benchmark / generator version | `mbench-1.0` / `mgen-1.0` |
| Execution (UTC) | 2026-10-17 18:19:15–18:19:20 |

- **What ran:** the run used the frozen commit `f3b544d` **plus** explicitly documented, uncommitted working-tree changes made at M4.2: (1) the final-unlock change — `FINAL_EVALUATION_ENABLED = True` in `runner.py`, the CLI guard in `apps/evaluation/main.py` that lets `--unlock-final-evaluation` through, and the three tests that had asserted the M4.1 lock; (2) split-aware report wording only — `report.py`, `statements.py` and one test, so the final report does not claim the final split is unevaluated. Evaluation, metrics, oracle, generator, adapters, baselines, thresholds and cases were not changed. See `working_tree_note` in `FINAL_RUN_RECORD.json`.
- **Executed once:** the FINAL evaluation was executed once and was not rerun. The report was generated from the saved results of that run.
- **Ablations:** the physical-only and digital-only systems are internal ablations (the same engine with one channel removed), not external commercial baselines.
- **Scope:** this is a synthetic procedure-integrity evaluation (procedurally generated event sequences). It is not field accuracy and not live-camera accuracy.
- **Known limitation retained:** `weak_physical_midjourney` — the engine raised `PHANTOM_COMPLETION` on all 60 such final cases where the oracle expects `UNCERTAIN`. It was accepted before the run and is not reinterpreted.

## Limitation: nature of the FINAL split

The FINAL split is independently seeded but is generated from the same procedural distribution and composition design as the development split. It is therefore a frozen held-out synthetic benchmark, not an out-of-distribution or real-world validation set.

## Contents

`report.md`, `summary.json`, `per_class_metrics.csv`, `system_comparison.csv`, `family_breakdown.csv`, `FINAL_RUN_RECORD.json`, `manifest.json`, `SHA256SUMS.txt`. Not archived here (large or machine-specific; kept in `artifacts/evaluation/final/`, git-ignored): `benchmark.jsonl` (its hash is above and in the manifest), `case_results.jsonl`, `latency.json`, `run_info.json`.
