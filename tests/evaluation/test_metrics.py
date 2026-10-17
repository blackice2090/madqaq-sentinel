"""Metrics audited against hand-calculated toy examples."""
import math

import pytest

from sentinel.evaluation import metrics as M
from sentinel.evaluation.latency import measure_latency, percentile
from sentinel.evaluation.metrics import CaseOutcome

OM_B, OM_C, PH_B, INV_C = "OMISSION:B", "OMISSION:C", "PHANTOM_COMPLETION:B", "ORDER_INVERSION:C"


def out(i, truth_status, pred_status, truth=(), pred=()):
    return CaseOutcome(f"c{i}", "core", "fam", truth_status, pred_status, frozenset(truth), frozenset(pred))


TOY = [
    out(1, "VIOLATED", "VIOLATED", [OM_B], [OM_B]),                       # correct
    out(2, "VIOLATED", "VIOLATED", [PH_B], [OM_B]),                       # wrong type: PH missed, OM false alarm
    out(3, "COMPLETED", "VIOLATED", [], [OM_C]),                          # false alarm on a conformant journey
    out(4, "VIOLATED", "VIOLATED", [OM_B, INV_C], [OM_B]),                # partial: INV missed
    out(5, "COMPLETED", "COMPLETED", [], []),                             # correct
    out(6, "UNCERTAIN", "UNCERTAIN", [], []),                             # correct
]


def test_per_type_counts_by_hand():
    c = M.per_type_counts(TOY)
    assert c["OMISSION"] == (2, 2, 0)              # TP: cases 1,4  FP: cases 2,3
    assert c["PHANTOM_COMPLETION"] == (0, 0, 1)    # FN: case 2
    assert c["ORDER_INVERSION"] == (0, 0, 1)       # FN: case 4
    assert c["CHANNEL_CONTRADICTION"] == (0, 0, 0)


def test_precision_recall_f1_by_hand():
    p, r, f = M.prf(2, 2, 0)
    assert (p, r) == (0.5, 1.0) and f == pytest.approx(4 / 6)
    assert M.prf(0, 0, 1) == (None, 0.0, 0.0)      # never predicted, exists in truth: F1 is 0, precision undefined
    assert M.prf(0, 0, 0) == (None, None, None)    # absent everywhere: undefined


def test_macro_and_micro_f1_by_hand():
    per_type = M.per_type_counts(TOY)
    macro, counted = M.macro_f1(per_type)
    assert counted == 3 and macro == pytest.approx((4 / 6 + 0 + 0) / 3)          # contradiction type is undefined, excluded
    assert M.micro_f1(per_type) == pytest.approx(4 / 8)                           # TP 2, FP 2, FN 2
    assert M.micro_f1(per_type) != macro


def test_exact_set_match_is_multi_label_aware():
    assert M.exact_set_accuracy(TOY) == pytest.approx(3 / 6)                      # cases 1, 5, 6
    a = out(1, "VIOLATED", "VIOLATED", [OM_B, OM_C], [OM_C, OM_B])                # order-independent
    b = out(2, "VIOLATED", "VIOLATED", [OM_B], [OM_B, OM_C])                      # superset is NOT a match
    c = out(3, "VIOLATED", "VIOLATED", [OM_B, OM_C], [OM_B])                      # subset is NOT a match
    d = out(4, "COMPLETED", "COMPLETED")                                          # two empty sets match
    assert [x.exact_match for x in (a, b, c, d)] == [True, False, False, True]


def test_false_positive_rate_on_conformant_journeys():
    assert M.false_positive_rate_conformant(TOY) == pytest.approx(1 / 2)          # COMPLETED cases: 3 (alarm), 5
    assert M.false_positive_rate_violation_free(TOY) == pytest.approx(1 / 3)      # cases 3, 5, 6


def test_false_negative_rate_on_violated_journeys():
    assert M.false_negative_rate_violated(TOY) == 0.0                             # every violated journey got some alarm
    miss = TOY + [out(7, "VIOLATED", "COMPLETED", [OM_B], [])]
    assert M.false_negative_rate_violated(miss) == pytest.approx(1 / 4)
    assert M.summarize_system(TOY)["metrics"]["label_miss_rate"] == pytest.approx(2 / 4)


def test_status_accuracy_and_uncertain_rate():
    assert M.status_accuracy(TOY) == pytest.approx(5 / 6)
    assert M.uncertain_rate(TOY) == pytest.approx(1 / 6)


def test_zero_denominators_are_explicit_none():
    assert M.false_positive_rate_conformant([out(1, "VIOLATED", "VIOLATED", [OM_B], [OM_B])]) is None
    assert M.false_negative_rate_violated([out(1, "COMPLETED", "COMPLETED")]) is None
    assert M.exact_set_accuracy([]) is None and M.macro_f1({t: (0, 0, 0) for t in M.VIOLATION_TYPES}) == (None, 0)
    assert "undefined" in M.ZERO_DIVISION_CONVENTION


def test_summarize_system_matches_the_hand_numbers():
    s = M.summarize_system(TOY)
    m = s["metrics"]
    assert m["total_cases"] == 6 and m["exact_set_accuracy"] == pytest.approx(0.5)
    assert m["conformant_cases"] == 2 and m["conformant_false_alarms"] == 1
    assert s["per_violation_type"]["OMISSION"]["precision"] == 0.5
    assert s["per_violation_type"]["MICRO_ALL"]["f1"] == pytest.approx(0.5)


def test_family_rows_and_complementarity():
    rows = M.family_rows({"s": TOY})
    assert rows[0]["cases"] == 6 and rows[0]["exact_matches"] == 3 and rows[0]["false_positive_labels"] == 2
    other = [out(i + 1, o.truth_status, o.truth_status, o.truth_labels, o.truth_labels) for i, o in enumerate(TOY)]
    comp = M.complementarity(TOY, other)
    assert comp == {"both_exact": 3, "reference_only_exact": 0, "other_only_exact": 3, "neither_exact": 0}


# ---- bootstrap ------------------------------------------------------------------------------
def _systems():
    return {"full_dual_channel": TOY * 5, "other": [out(i, o.truth_status, "UNCERTAIN", o.truth_labels, ()) for i, o in enumerate(TOY * 5)]}


def test_bootstrap_intervals_are_deterministic_and_seed_dependent():
    a = M.bootstrap_intervals(_systems(), resamples=80, seed=7)
    b = M.bootstrap_intervals(_systems(), resamples=80, seed=7)
    c = M.bootstrap_intervals(_systems(), resamples=80, seed=8)
    assert a == b and a != c


def test_bootstrap_point_estimates_equal_the_direct_metrics():
    r = M.bootstrap_intervals(_systems(), resamples=40, seed=1)
    point = r["intervals"]["full_dual_channel"]
    full = M.summarize_system(TOY * 5)["metrics"]
    assert point["exact_set_accuracy"]["point"] == pytest.approx(full["exact_set_accuracy"])
    assert point["macro_f1"]["point"] == pytest.approx(full["macro_f1"])
    assert point["status_accuracy"]["point"] == pytest.approx(full["status_accuracy"])
    for m in M.METRIC_NAMES:
        e = point[m]
        assert e["ci_low"] <= e["ci_high"]
    assert "not field-performance" in r["scope"]


def test_paired_difference_of_identical_systems_is_zero():
    same = {"full_dual_channel": TOY * 4, "twin": TOY * 4}
    d = M.bootstrap_intervals(same, resamples=40, seed=3)["paired_delta_reference_minus_system"]["deltas"]["twin"]
    assert all(d[m]["point"] == 0 and d[m]["ci_low"] == 0 and d[m]["ci_high"] == 0 for m in M.METRIC_NAMES)


# ---- latency ---------------------------------------------------------------------------------
class CountingSystem:
    def __init__(self):
        self.calls = 0

    def evaluate(self, evidence):
        self.calls += 1


def test_percentile_is_nearest_rank():
    data = list(range(1, 101))
    assert percentile(data, 50) == 50 and percentile(data, 95) == 95 and percentile(data, 99) == 99
    assert percentile([7], 99) == 7


def test_latency_measurement_is_non_negative_ordered_and_warmed_up():
    system = CountingSystem()
    r = measure_latency(system, ["x", "y", "z"], warmup=5, repeats=4)
    assert system.calls == 5 + 3 * 4 and r["samples"] == 12
    assert 0 <= r["min_us"] <= r["median_us"] <= r["p95_us"] <= r["p99_us"] <= r["max_us"]
    assert not math.isnan(r["mean_us"])


def test_latency_rejects_empty_input():
    with pytest.raises(ValueError):
        measure_latency(CountingSystem(), [])
