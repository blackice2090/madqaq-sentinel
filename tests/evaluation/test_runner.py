"""Runner, outputs and the FINAL lock."""
import hashlib
import json

import pytest

from sentinel.evaluation import runner
from sentinel.evaluation.generator import BenchmarkIntegrityError, generate_split, load_split, write_split
from sentinel.evaluation.report import write_results
from sentinel.evaluation.schema import case_to_json_line
from sentinel.evaluation.runner import FinalEvaluationLockedError, assert_evaluation_allowed, evaluate_cases


def test_dev_evaluation_covers_all_four_systems(dev_eval):
    s = dev_eval.summary
    assert list(s["systems"]) == ["full_dual_channel", "physical_only_ablation", "digital_only_ablation",
                                  "simple_procedure_check"]
    assert all(m["metrics"]["total_cases"] == 300 for m in s["systems"].values())
    assert len(dev_eval.case_rows) == 300
    assert s["benchmark"]["split"] == "dev" and s["milestone"] == "M4.1"


def test_summary_has_every_required_metric(dev_eval):
    m = dev_eval.summary["systems"]["full_dual_channel"]["metrics"]
    for key in ("total_cases", "exact_set_accuracy", "macro_f1", "micro_f1", "fpr_conformant", "fnr_violated",
                "status_accuracy", "uncertain_rate"):
        assert key in m
    for t, v in dev_eval.summary["systems"]["full_dual_channel"]["per_violation_type"].items():
        assert {"tp", "fp", "fn", "precision", "recall", "f1"} <= set(v)
    ci = dev_eval.summary["bootstrap"]["intervals"]["full_dual_channel"]
    assert set(ci) == {"macro_f1", "exact_set_accuracy", "status_accuracy"}


def test_ablations_are_actually_blind_to_the_other_channel(dev_eval):
    cross = dev_eval.summary["cross_channel_benefit_by_type"]
    for t in ("PHANTOM_COMPLETION", "CHANNEL_CONTRADICTION"):
        assert cross[t]["by_system"]["physical_only_ablation"]["tp"] == 0
        assert cross[t]["by_system"]["digital_only_ablation"]["tp"] == 0
        assert cross[t]["by_system"]["full_dual_channel"]["recall"] == 1.0
        assert cross[t]["recall_gain_over_best_single_channel"] > 0


def test_case_rows_record_each_system_against_stored_truth(dev_eval, dev_split):
    row = dev_eval.case_rows[0]
    case = dev_split.cases[0]
    assert row["case_id"] == case.case_id and row["ground_truth_labels"] == case.ground_truth_labels
    sysrow = row["systems"]["full_dual_channel"]
    assert sysrow["exact_match"] == (sysrow["labels"] == case.ground_truth_labels)


def test_evaluation_does_not_mutate_ground_truth(dev_split):
    before = dev_split.jsonl
    evaluate_cases(dev_split.cases, dev_split.manifest, resamples=10, measure_latency_=False)
    assert "".join(case_to_json_line(c) + "\n" for c in dev_split.cases) == before


def test_runner_loads_labels_from_disk_and_checks_integrity(tmp_path, dev_split):
    write_split(dev_split, tmp_path)
    cases, manifest = load_split(tmp_path, "dev")
    assert [c.ground_truth_labels for c in cases] == [c.ground_truth_labels for c in dev_split.cases]
    path = tmp_path / "dev" / "benchmark.jsonl"
    path.write_text(path.read_text().replace("COMPLETED", "VIOLATED", 1), encoding="utf-8")   # tamper with the labels
    with pytest.raises(BenchmarkIntegrityError):
        load_split(tmp_path, "dev")


def test_missing_split_asks_for_generation(tmp_path):
    with pytest.raises(FileNotFoundError, match="generate --split dev"):
        load_split(tmp_path, "dev")


# ---- the FINAL lock ------------------------------------------------------------------------------
def test_final_evaluation_lock_is_open_in_m42():
    assert runner.FINAL_EVALUATION_ENABLED is True


def test_final_evaluation_is_blocked_by_default(final_split):
    with pytest.raises(FinalEvaluationLockedError, match="--unlock-final-evaluation"):
        evaluate_cases(final_split.cases, final_split.manifest, resamples=5, measure_latency_=False)
    with pytest.raises(FinalEvaluationLockedError):
        assert_evaluation_allowed(final_split.cases)


def test_unlock_flag_passes_the_guard_without_running_any_system(final_split):
    assert_evaluation_allowed(final_split.cases, unlock_final=True)   # guard only; nothing is evaluated


def test_a_single_final_case_mixed_into_dev_still_trips_the_lock(dev_split, final_split):
    with pytest.raises(FinalEvaluationLockedError):
        evaluate_cases(dev_split.cases[:5] + final_split.cases[:1], dev_split.manifest, resamples=5, measure_latency_=False)


def test_the_lock_never_runs_a_system_on_final_cases(final_split):
    class Tripwire:
        system_id, display_name, description = "t", "t", "t"
        channels = frozenset()

        def evaluate(self, evidence):
            raise AssertionError("a system was run on FINAL cases")

    with pytest.raises(FinalEvaluationLockedError):
        evaluate_cases(final_split.cases, final_split.manifest, systems=[Tripwire()], measure_latency_=False)


def test_dev_evaluation_is_allowed(dev_split):
    assert_evaluation_allowed(dev_split.cases)


def test_written_results_have_the_required_files(tmp_path, dev_split):
    result = evaluate_cases(dev_split.cases, dev_split.manifest, resamples=20, latency_repeats=1, latency_warmup=3)
    paths = write_results(result, tmp_path)
    for name in ("summary", "per_class", "comparison", "cases", "family", "latency", "run_info"):
        assert paths[name].exists()
    assert paths["summary"].name == "summary.json" and paths["per_class"].name == "per_class_metrics.csv"
    assert paths["comparison"].name == "system_comparison.csv" and paths["cases"].name == "case_results.jsonl"
    header = paths["comparison"].read_text().splitlines()[0].split(",")
    for col in ("total_cases", "exact_set_accuracy", "macro_f1", "micro_f1", "fpr_conformant", "fnr_violated",
                "status_accuracy", "uncertain_rate"):
        assert col in header
    pc = paths["per_class"].read_text().splitlines()
    assert pc[0] == "system_id,violation_type,truth_labels,tp,fp,fn,precision,recall,f1" and len(pc) == 1 + 4 * 5
    lat = json.loads(paths["latency"].read_text())
    assert lat["systems"]["full_dual_channel"]["median_us"] >= 0 and "environment" in lat
