"""Benchmark runner (M4.1): evaluates the four systems on a loaded split.

FINAL LOCK: evaluating the FINAL split is blocked at the lowest level (this function),
so no CLI path, script or test helper can reach it by accident. It needs an explicit
``unlock_final=True`` (CLI: --unlock-final-evaluation) AND ``FINAL_EVALUATION_ENABLED``,
which stays False in M4.1 and may only change in a reviewed M4.2 commit.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sentinel.evaluation import metrics as M
from sentinel.evaluation.adapters import EvaluatedSystem, Evidence
from sentinel.evaluation.baselines import RULES, default_systems
from sentinel.evaluation.latency import environment_info, measure_latency
from sentinel.evaluation.schema import VIOLATION_TYPES, BenchmarkCase, case_to_domain
from sentinel.evaluation.statements import (
    ABLATION_SCOPE, CI_SCOPE, DEV_STATUS, LATENCY_SCOPE, SYNTHETIC_SCOPE,
)

FINAL_EVALUATION_ENABLED = False      # M4.1: final evaluation is not permitted
BOOTSTRAP_SEED = 20261017
BOOTSTRAP_RESAMPLES = 2000
REFERENCE_SYSTEM = "full_dual_channel"
SUMMARY_SCHEMA = "madqaq-sentinel-eval/1"


class FinalEvaluationLockedError(RuntimeError):
    pass


def assert_evaluation_allowed(cases: list[BenchmarkCase], *, unlock_final: bool = False) -> None:
    if not any(c.split == "final" for c in cases):
        return
    if not unlock_final:
        raise FinalEvaluationLockedError(
            "Evaluating the FINAL split is blocked by default. It requires the explicit --unlock-final-evaluation flag "
            "and is not part of M4.1.")
    if not FINAL_EVALUATION_ENABLED:
        raise FinalEvaluationLockedError(
            "FINAL evaluation is locked in M4.1 (FINAL_EVALUATION_ENABLED is False). It may be enabled only in M4.2, "
            "after the benchmark implementation has been reviewed and frozen.")


@dataclass
class EvaluationResult:
    split: str
    summary: dict
    case_rows: list[dict]
    outcomes: dict[str, list[M.CaseOutcome]]
    latency: dict | None = None
    systems: list[EvaluatedSystem] = field(default_factory=list)


def build_evidence(case: BenchmarkCase) -> Evidence:
    procedure, journey, physical, digital = case_to_domain(case)
    return Evidence(procedure, journey, tuple(physical), tuple(digital))


def evaluate_cases(
    cases: list[BenchmarkCase],
    manifest: dict,
    systems: list[EvaluatedSystem] | None = None,
    *,
    unlock_final: bool = False,
    resamples: int = BOOTSTRAP_RESAMPLES,
    bootstrap_seed: int = BOOTSTRAP_SEED,
    measure_latency_: bool = True,
    latency_repeats: int = 5,
    latency_warmup: int = 100,
) -> EvaluationResult:
    assert_evaluation_allowed(cases, unlock_final=unlock_final)
    systems = systems or default_systems()
    evidences = [build_evidence(c) for c in cases]

    outcomes: dict[str, list[M.CaseOutcome]] = {s.system_id: [] for s in systems}
    case_rows: list[dict] = []
    for case, evidence in zip(cases, evidences):
        row = {
            "case_id": case.case_id, "split": case.split, "subset": case.subset,
            "scenario_family": case.scenario_family, "noise_conditions": case.noise_conditions,
            "ground_truth_status": case.ground_truth_status, "ground_truth_labels": case.ground_truth_labels,
            "systems": {},
        }
        for system in systems:
            out = system.evaluate(evidence.restricted_to(system.channels))
            outcome = M.CaseOutcome(
                case_id=case.case_id, subset=case.subset, family=case.scenario_family,
                truth_status=case.ground_truth_status, pred_status=out.status,
                truth_labels=frozenset(case.ground_truth_labels), pred_labels=out.labels)
            outcomes[system.system_id].append(outcome)
            row["systems"][system.system_id] = {
                "status": out.status, "labels": sorted(out.labels),
                "exact_match": outcome.exact_match, "status_correct": outcome.status_correct,
                "false_positive_labels": sorted(outcome.pred_labels - outcome.truth_labels),
                "false_negative_labels": sorted(outcome.truth_labels - outcome.pred_labels),
            }
        case_rows.append(row)

    summary = _build_summary(cases, manifest, systems, outcomes, resamples, bootstrap_seed)

    latency = None
    if measure_latency_:
        latency = {"scope": LATENCY_SCOPE, "environment": environment_info(), "repeats": latency_repeats, "systems": {}}
        for system in systems:
            restricted = [e.restricted_to(system.channels) for e in evidences]
            latency["systems"][system.system_id] = measure_latency(
                system, restricted, warmup=latency_warmup, repeats=latency_repeats)
    return EvaluationResult(cases[0].split if cases else "", summary, case_rows, outcomes, latency, systems)


def _build_summary(cases, manifest, systems, outcomes, resamples, bootstrap_seed) -> dict:
    per_system = {}
    for s in systems:
        body = M.summarize_system(outcomes[s.system_id])
        per_system[s.system_id] = {
            "display_name": s.display_name, "description": s.description,
            "channels": sorted(c.value for c in s.channels), **body,
        }
    cross = {}
    for t in VIOLATION_TYPES:
        cell = {sid: {k: per_system[sid]["per_violation_type"][t][k] for k in ("precision", "recall", "f1", "tp", "fp", "fn")}
                for sid in per_system}
        full_recall = cell.get(REFERENCE_SYSTEM, {}).get("recall")
        singles = [cell[sid]["recall"] or 0.0 for sid in ("physical_only_ablation", "digital_only_ablation") if sid in cell]
        cross[t] = {
            "truth_labels": per_system[REFERENCE_SYSTEM]["per_violation_type"][t]["truth_labels"]
            if REFERENCE_SYSTEM in per_system else None,
            "by_system": cell,
            "recall_gain_over_best_single_channel":
                (full_recall - max(singles)) if full_recall is not None and singles else None,
        }
    return {
        "summary_schema": SUMMARY_SCHEMA,
        "milestone": "M4.1",
        "benchmark": {k: manifest[k] for k in (
            "benchmark_version", "generator_version", "split", "seed", "n_cases", "dataset_sha256",
            "rejected_candidates", "subsets", "scenario_families", "noise_conditions", "class_distribution",
            "composition_per_300", "composition_scale")},
        "scope_statements": {"synthetic": SYNTHETIC_SCOPE, "ablations": ABLATION_SCOPE, "intervals": CI_SCOPE,
                             "latency": LATENCY_SCOPE, "split_status": DEV_STATUS},
        "conventions": {"zero_division": M.ZERO_DIVISION_CONVENTION},
        "engine_version": "m0.1 (ConformanceEngine, unmodified)",
        "simple_baseline_rules": list(RULES),
        "systems": per_system,
        "bootstrap": M.bootstrap_intervals(outcomes, resamples=resamples, seed=bootstrap_seed, reference=REFERENCE_SYSTEM),
        "subset_metrics": M.subset_summaries(outcomes),
        "family_breakdown": M.family_rows(outcomes),
        "complementarity_exact_match": {
            sid: M.complementarity(outcomes[REFERENCE_SYSTEM], outcomes[sid])
            for sid in outcomes if sid != REFERENCE_SYSTEM and REFERENCE_SYSTEM in outcomes},
        "cross_channel_benefit_by_type": cross,
    }
