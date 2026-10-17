"""Transparent evaluation metrics (M4.1). Pure Python, no third-party statistics code.

Conventions (also written into summary.json and the report)
------------------------------------------------------------
* A prediction/truth item is a violation LABEL "TYPE:STEP". A predicted label counts as a
  true positive only if BOTH type and step match a ground-truth label.
* Per-type TP/FP/FN are counted over labels of that type. Micro counts pool all types.
* precision = TP/(TP+FP), recall = TP/(TP+FN); undefined (None) when the denominator is 0.
* F1 = 2TP/(2TP+FP+FN); undefined (None) only when 2TP+FP+FN = 0 (type absent from both
  truth and predictions). A type that exists in truth but is never predicted has F1 = 0.
* Macro-F1 = unweighted mean of the DEFINED per-type F1 values over the four types.
* Rates with a zero denominator are None, never silently 0.
* Exact violation-set accuracy = share of cases whose predicted label set equals the
  truth set (two empty sets match).
* False-positive rate on conformant journeys = share of ground-truth-COMPLETED cases on
  which the system raised >= 1 violation. A second rate is reported over ALL violation-
  free cases (COMPLETED + UNCERTAIN ground truth).
* False-negative rate on violated journeys = share of ground-truth-VIOLATED cases on which
  the system raised NO violation. The stricter label-level miss rate is FN/(TP+FN).
* Bootstrap: percentile interval over cases, resampled with replacement, fixed seed.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from sentinel.evaluation.rng import StableRandom
from sentinel.evaluation.schema import VIOLATION_TYPES

ZERO_DIVISION_CONVENTION = (
    "precision/recall are undefined (null) when their denominator is 0; F1 = 2TP/(2TP+FP+FN) is undefined only when "
    "that denominator is 0; macro-F1 averages the defined per-type F1 values; rates with a zero denominator are null."
)
METRIC_NAMES = ("macro_f1", "exact_set_accuracy", "status_accuracy")


@dataclass(frozen=True)
class CaseOutcome:
    case_id: str
    subset: str
    family: str
    truth_status: str
    pred_status: str
    truth_labels: frozenset
    pred_labels: frozenset

    @property
    def exact_match(self) -> bool:
        return self.truth_labels == self.pred_labels

    @property
    def status_correct(self) -> bool:
        return self.truth_status == self.pred_status


def label_type(label: str) -> str:
    return label.split(":", 1)[0]


def _ratio(num: int, den: int):
    return num / den if den else None


def prf(tp: int, fp: int, fn: int):
    precision = _ratio(tp, tp + fp)
    recall = _ratio(tp, tp + fn)
    f1 = _ratio(2 * tp, 2 * tp + fp + fn)
    return precision, recall, f1


def per_type_counts(outcomes) -> dict[str, tuple[int, int, int]]:
    counts = {t: [0, 0, 0] for t in VIOLATION_TYPES}
    for o in outcomes:
        for t in VIOLATION_TYPES:
            truth = {l for l in o.truth_labels if label_type(l) == t}
            pred = {l for l in o.pred_labels if label_type(l) == t}
            counts[t][0] += len(truth & pred)
            counts[t][1] += len(pred - truth)
            counts[t][2] += len(truth - pred)
    return {t: tuple(v) for t, v in counts.items()}


def macro_f1(per_type: dict[str, tuple[int, int, int]]):
    """(value or None, number of types whose F1 was defined)."""
    f1s = [prf(*c)[2] for c in per_type.values()]
    defined = [f for f in f1s if f is not None]
    return (sum(defined) / len(defined) if defined else None), len(defined)


def micro_f1(per_type: dict[str, tuple[int, int, int]]):
    tp = sum(c[0] for c in per_type.values())
    fp = sum(c[1] for c in per_type.values())
    fn = sum(c[2] for c in per_type.values())
    return prf(tp, fp, fn)[2]


def exact_set_accuracy(outcomes):
    return _ratio(sum(o.exact_match for o in outcomes), len(outcomes))


def status_accuracy(outcomes):
    return _ratio(sum(o.status_correct for o in outcomes), len(outcomes))


def uncertain_rate(outcomes):
    return _ratio(sum(o.pred_status == "UNCERTAIN" for o in outcomes), len(outcomes))


def false_positive_rate_conformant(outcomes):
    pool = [o for o in outcomes if o.truth_status == "COMPLETED"]
    return _ratio(sum(bool(o.pred_labels) for o in pool), len(pool))


def false_positive_rate_violation_free(outcomes):
    pool = [o for o in outcomes if not o.truth_labels]
    return _ratio(sum(bool(o.pred_labels) for o in pool), len(pool))


def false_negative_rate_violated(outcomes):
    pool = [o for o in outcomes if o.truth_labels]
    return _ratio(sum(not o.pred_labels for o in pool), len(pool))


def summarize_system(outcomes) -> dict:
    outcomes = list(outcomes)
    per_type = per_type_counts(outcomes)
    macro, n_types = macro_f1(per_type)
    tp = sum(c[0] for c in per_type.values())
    fp = sum(c[1] for c in per_type.values())
    fn = sum(c[2] for c in per_type.values())
    conformant = [o for o in outcomes if o.truth_status == "COMPLETED"]
    free = [o for o in outcomes if not o.truth_labels]
    violated = [o for o in outcomes if o.truth_labels]
    per_type_rows = {}
    for t, (a, b, c) in per_type.items():
        p, r, f = prf(a, b, c)
        per_type_rows[t] = {"truth_labels": a + c, "tp": a, "fp": b, "fn": c, "precision": p, "recall": r, "f1": f}
    p, r, f = prf(tp, fp, fn)
    per_type_rows["MICRO_ALL"] = {"truth_labels": tp + fn, "tp": tp, "fp": fp, "fn": fn,
                                  "precision": p, "recall": r, "f1": f}
    return {
        "metrics": {
            "total_cases": len(outcomes),
            "exact_set_accuracy": exact_set_accuracy(outcomes),
            "macro_f1": macro,
            "macro_f1_types_counted": n_types,
            "micro_f1": micro_f1(per_type),
            "fpr_conformant": false_positive_rate_conformant(outcomes),
            "conformant_cases": len(conformant),
            "conformant_false_alarms": sum(bool(o.pred_labels) for o in conformant),
            "fpr_violation_free": false_positive_rate_violation_free(outcomes),
            "violation_free_cases": len(free),
            "violation_free_false_alarms": sum(bool(o.pred_labels) for o in free),
            "fnr_violated": false_negative_rate_violated(outcomes),
            "violated_cases": len(violated),
            "violated_missed_entirely": sum(not o.pred_labels for o in violated),
            "label_miss_rate": _ratio(fn, tp + fn),
            "status_accuracy": status_accuracy(outcomes),
            "uncertain_rate": uncertain_rate(outcomes),
            "ground_truth_uncertain_rate": _ratio(sum(o.truth_status == "UNCERTAIN" for o in outcomes), len(outcomes)),
        },
        "per_violation_type": per_type_rows,
    }


# ---- breakdowns ----------------------------------------------------------------------
def family_rows(outcomes_by_system: dict[str, list[CaseOutcome]]) -> list[dict]:
    rows = []
    for sid, outs in outcomes_by_system.items():
        groups: dict[tuple[str, str], list[CaseOutcome]] = {}
        for o in outs:
            groups.setdefault((o.subset, o.family), []).append(o)
        for (subset, family), g in sorted(groups.items()):
            rows.append({
                "system_id": sid, "subset": subset, "family": family, "cases": len(g),
                "exact_matches": sum(o.exact_match for o in g),
                "exact_match_rate": sum(o.exact_match for o in g) / len(g),
                "status_correct": sum(o.status_correct for o in g),
                "status_accuracy": sum(o.status_correct for o in g) / len(g),
                "false_positive_labels": sum(len(o.pred_labels - o.truth_labels) for o in g),
                "false_negative_labels": sum(len(o.truth_labels - o.pred_labels) for o in g),
                "truth_label_count": sum(len(o.truth_labels) for o in g),
            })
    return rows


def subset_summaries(outcomes_by_system: dict[str, list[CaseOutcome]]) -> dict:
    out: dict = {}
    for sid, outs in outcomes_by_system.items():
        for subset in sorted({o.subset for o in outs}):
            sub = [o for o in outs if o.subset == subset]
            m = summarize_system(sub)["metrics"]
            out.setdefault(subset, {})[sid] = {
                k: m[k] for k in ("total_cases", "exact_set_accuracy", "macro_f1", "micro_f1", "status_accuracy",
                                  "fpr_violation_free", "fnr_violated")}
    return out


def complementarity(reference: list[CaseOutcome], other: list[CaseOutcome]) -> dict:
    both = ref_only = other_only = neither = 0
    for a, b in zip(reference, other):
        assert a.case_id == b.case_id
        if a.exact_match and b.exact_match:
            both += 1
        elif a.exact_match:
            ref_only += 1
        elif b.exact_match:
            other_only += 1
        else:
            neither += 1
    return {"both_exact": both, "reference_only_exact": ref_only, "other_only_exact": other_only, "neither_exact": neither}


# ---- bootstrap ----------------------------------------------------------------------------
def _vector(o: CaseOutcome) -> list[int]:
    v: list[int] = []
    for t in VIOLATION_TYPES:
        truth = {l for l in o.truth_labels if label_type(l) == t}
        pred = {l for l in o.pred_labels if label_type(l) == t}
        v += [len(truth & pred), len(pred - truth), len(truth - pred)]
    v += [int(o.exact_match), int(o.status_correct)]
    return v


def _stats_from_sums(sums: list[int], n: int) -> dict:
    per_type = {t: (sums[3 * j], sums[3 * j + 1], sums[3 * j + 2]) for j, t in enumerate(VIOLATION_TYPES)}
    k = 3 * len(VIOLATION_TYPES)
    return {"macro_f1": macro_f1(per_type)[0], "exact_set_accuracy": sums[k] / n, "status_accuracy": sums[k + 1] / n}


def _interval(samples: list, level: float):
    s = sorted(x for x in samples if x is not None)
    if not s:
        return None, None
    lo = s[int(math.floor((1 - level) / 2 * (len(s) - 1)))]
    hi = s[int(math.ceil((1 + level) / 2 * (len(s) - 1)))]
    return lo, hi


def bootstrap_intervals(outcomes_by_system: dict[str, list[CaseOutcome]], *, resamples: int, seed: int,
                        level: float = 0.95, reference: str = "full_dual_channel") -> dict:
    """Percentile bootstrap over cases; the SAME resamples are used for every system so
    differences versus ``reference`` are paired. Intervals describe sampling variability
    over this synthetic benchmark only, not field performance."""
    ids = list(outcomes_by_system)
    n = len(next(iter(outcomes_by_system.values())))
    for outs in outcomes_by_system.values():
        assert len(outs) == n
    vecs = {sid: [_vector(o) for o in outs] for sid, outs in outcomes_by_system.items()}
    point = {sid: _stats_from_sums([sum(c) for c in zip(*vecs[sid])], n) for sid in ids}

    rng = StableRandom(seed, "bootstrap")
    samples = {sid: {m: [] for m in METRIC_NAMES} for sid in ids}
    for _ in range(resamples):
        idx = [int(rng.random() * n) for _ in range(n)]
        for sid in ids:
            v = vecs[sid]
            stats = _stats_from_sums([sum(c) for c in zip(*[v[i] for i in idx])], n)
            for m in METRIC_NAMES:
                samples[sid][m].append(stats[m])

    intervals = {}
    for sid in ids:
        intervals[sid] = {}
        for m in METRIC_NAMES:
            lo, hi = _interval(samples[sid][m], level)
            intervals[sid][m] = {"point": point[sid][m], "ci_low": lo, "ci_high": hi}
    deltas = {}
    if reference in samples:
        for sid in ids:
            if sid == reference:
                continue
            deltas[sid] = {}
            for m in METRIC_NAMES:
                diffs = [a - b if a is not None and b is not None else None
                         for a, b in zip(samples[reference][m], samples[sid][m])]
                lo, hi = _interval(diffs, level)
                pr, ps = point[reference][m], point[sid][m]
                deltas[sid][m] = {"point": (pr - ps) if pr is not None and ps is not None else None,
                                  "ci_low": lo, "ci_high": hi}
    return {
        "method": "percentile bootstrap over cases (resampling with replacement), shared resamples across systems",
        "level": level, "resamples": resamples, "seed": seed,
        "scope": "statistical intervals over this synthetic benchmark sample, not field-performance confidence intervals",
        "intervals": intervals, "paired_delta_reference_minus_system": {"reference": reference, "deltas": deltas},
    }
