"""Result files and the human-readable report (M4.1)."""
from __future__ import annotations

import csv
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

from sentinel.evaluation.runner import EvaluationResult
from sentinel.evaluation.schema import VIOLATION_TYPES
from sentinel.evaluation.statements import (
    ABLATION_SCOPE, CI_SCOPE, DEV_STATUS, FINAL_STATUS, KNOWN_LIMITATION, LATENCY_LABEL, KNOWN_LIMITATION_NOTE, LATENCY_SCOPE, SYNTHETIC_SCOPE,
)

SYSTEM_ORDER = ("full_dual_channel", "physical_only_ablation", "digital_only_ablation", "simple_procedure_check")


# ---- writers ---------------------------------------------------------------------------------
def _cell(x):
    if x is None:
        return ""
    if isinstance(x, float):
        return repr(round(x, 6))
    return x


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for r in rows:
            w.writerow([_cell(c) for c in r])


def _ordered(systems: dict) -> list[str]:
    return [s for s in SYSTEM_ORDER if s in systems] + [s for s in systems if s not in SYSTEM_ORDER]


def write_results(result: EvaluationResult, out_dir: str | Path) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    summary = result.summary
    paths: dict[str, Path] = {}

    paths["summary"] = out / "summary.json"
    paths["summary"].write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    ci = summary["bootstrap"]["intervals"]
    rows = []
    for sid in _ordered(summary["systems"]):
        m = summary["systems"][sid]["metrics"]
        rows.append([
            sid, summary["systems"][sid]["display_name"], m["total_cases"],
            m["exact_set_accuracy"], ci[sid]["exact_set_accuracy"]["ci_low"], ci[sid]["exact_set_accuracy"]["ci_high"],
            m["macro_f1"], ci[sid]["macro_f1"]["ci_low"], ci[sid]["macro_f1"]["ci_high"], m["micro_f1"],
            m["fpr_conformant"], m["conformant_false_alarms"], m["conformant_cases"],
            m["fpr_violation_free"], m["violation_free_false_alarms"], m["violation_free_cases"],
            m["fnr_violated"], m["violated_missed_entirely"], m["violated_cases"], m["label_miss_rate"],
            m["status_accuracy"], ci[sid]["status_accuracy"]["ci_low"], ci[sid]["status_accuracy"]["ci_high"],
            m["uncertain_rate"], m["ground_truth_uncertain_rate"],
        ])
    paths["comparison"] = out / "system_comparison.csv"
    _write_csv(paths["comparison"], [
        "system_id", "system", "total_cases", "exact_set_accuracy", "exact_set_ci_low", "exact_set_ci_high",
        "macro_f1", "macro_f1_ci_low", "macro_f1_ci_high", "micro_f1",
        "fpr_conformant", "conformant_false_alarms", "conformant_cases",
        "fpr_violation_free", "violation_free_false_alarms", "violation_free_cases",
        "fnr_violated", "violated_missed_entirely", "violated_cases", "label_miss_rate",
        "status_accuracy", "status_ci_low", "status_ci_high", "uncertain_rate", "ground_truth_uncertain_rate"], rows)

    rows = []
    for sid in _ordered(summary["systems"]):
        for t, v in summary["systems"][sid]["per_violation_type"].items():
            rows.append([sid, t, v["truth_labels"], v["tp"], v["fp"], v["fn"], v["precision"], v["recall"], v["f1"]])
    paths["per_class"] = out / "per_class_metrics.csv"
    _write_csv(paths["per_class"], ["system_id", "violation_type", "truth_labels", "tp", "fp", "fn",
                                    "precision", "recall", "f1"], rows)

    rows = [[r["system_id"], r["subset"], r["family"], r["cases"], r["exact_matches"], r["exact_match_rate"],
             r["status_correct"], r["status_accuracy"], r["false_positive_labels"], r["false_negative_labels"]]
            for r in summary["family_breakdown"]]
    paths["family"] = out / "family_breakdown.csv"
    _write_csv(paths["family"], ["system_id", "subset", "family", "cases", "exact_matches", "exact_match_rate",
                                 "status_correct", "status_accuracy", "false_positive_labels",
                                 "false_negative_labels"], rows)

    paths["cases"] = out / "case_results.jsonl"
    with open(paths["cases"], "w", encoding="utf-8", newline="\n") as fh:
        for row in result.case_rows:
            fh.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")

    if result.latency is not None:
        paths["latency"] = out / "latency.json"
        paths["latency"].write_text(json.dumps(result.latency, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    paths["run_info"] = out / "run_info.json"
    paths["run_info"].write_text(json.dumps({
        "note": "Non-deterministic run metadata; excluded from reproducibility checks.",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0], "platform": platform.platform(),
        "benchmark_sha256": summary["benchmark"]["dataset_sha256"],
    }, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return paths


# ---- report ----------------------------------------------------------------------------------
def pct(x, digits: int = 1) -> str:
    return "n/a" if x is None else f"{x * 100:.{digits}f}%"


def num(x, digits: int = 3) -> str:
    return "n/a" if x is None else f"{x:.{digits}f}"


def with_ci(entry: dict) -> str:
    return f"{pct(entry['point'])} [{pct(entry['ci_low'])}, {pct(entry['ci_high'])}]"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return out + [""]


def render_report(summary: dict, latency: dict | None = None) -> str:
    sy = summary["systems"]
    order = _ordered(sy)
    name = {sid: sy[sid]["display_name"] for sid in order}
    bm = summary["benchmark"]
    ci = summary["bootstrap"]["intervals"]
    lines: list[str] = []
    A = lines.append
    E = lines.extend

    A(f"# MADQAQ Sentinel — M4.1 comparative evaluation ({bm['split']} benchmark)")
    A("")
    A("## Scope and disclaimers")
    A("")
    is_final = bm["split"] == "final"
    for text in (SYNTHETIC_SCOPE, ABLATION_SCOPE, CI_SCOPE, LATENCY_SCOPE, FINAL_STATUS if is_final else DEV_STATUS):
        A(f"- {text}")
    A("- No claim is made about camera accuracy, field accuracy, deployment readiness, real digital-system integration "
      "or superiority over any external system.")
    A("")

    A("## Benchmark")
    A("")
    A(f"- Benchmark version `{bm['benchmark_version']}`, generator `{bm['generator_version']}`, split `{bm['split']}`, "
      f"seed `{bm['seed']}`, **{bm['n_cases']} journeys**.")
    A(f"- Dataset SHA-256 `{bm['dataset_sha256']}`; candidates rejected as ambiguous during generation: "
      f"{bm['rejected_candidates']}.")
    A("- Ground truth is created by the generator and cross-checked by an independent oracle; "
      "the ConformanceEngine is never used to produce labels.")
    A("")
    dist = bm["class_distribution"]
    A("**Ground-truth status:** " + ", ".join(f"{k} {v}" for k, v in dist["ground_truth_status"].items()))
    A("")
    A("**Violation labels by type:** " + ", ".join(f"{k} {v}" for k, v in dist["violation_types"].items()))
    A("")
    A("**Violations per case:** " + ", ".join(f"{k}: {v} cases" for k, v in dist["violations_per_case"].items()))
    A("")
    A("**Subsets:** " + ", ".join(f"{k} {v}" for k, v in bm["subsets"].items()))
    A("")
    A("**Noise conditions in the robustness subset:** " + ", ".join(f"{k} {v}" for k, v in bm["noise_conditions"].items()))
    A("")

    A("## Evaluated systems")
    A("")
    E(_table(["System", "Channels", "Description"],
              [[name[s], "+".join(sy[s]["channels"]), sy[s]["description"]] for s in order]))
    A("**Simple procedure-check baseline — exact rules**")
    A("")
    for rule in summary["simple_baseline_rules"]:
        A(f"1. {rule}")
    A("")

    A("## Primary results")
    A("")
    A(f"Intervals: 95% percentile bootstrap, {summary['bootstrap']['resamples']} resamples, seed "
      f"{summary['bootstrap']['seed']}. {CI_SCOPE}")
    A("")
    rows = []
    for s in order:
        m = sy[s]["metrics"]
        rows.append([name[s], m["total_cases"], with_ci(ci[s]["exact_set_accuracy"]), f"{num(ci[s]['macro_f1']['point'])} [{num(ci[s]['macro_f1']['ci_low'])}, {num(ci[s]['macro_f1']['ci_high'])}]",
                     num(m["micro_f1"]), with_ci(ci[s]["status_accuracy"])])
    E(_table(["System", "Cases", "Exact violation-set accuracy", "Macro-F1", "Micro-F1", "Status accuracy"], rows))
    rows = []
    for s in order:
        m = sy[s]["metrics"]
        rows.append([name[s],
                     f"{pct(m['fpr_conformant'])} ({m['conformant_false_alarms']}/{m['conformant_cases']})",
                     f"{pct(m['fpr_violation_free'])} ({m['violation_free_false_alarms']}/{m['violation_free_cases']})",
                     f"{pct(m['fnr_violated'])} ({m['violated_missed_entirely']}/{m['violated_cases']})",
                     pct(m["label_miss_rate"]), pct(m["uncertain_rate"]), pct(m["ground_truth_uncertain_rate"])])
    E(_table(["System", "FPR, conformant journeys", "FPR, all violation-free journeys",
               "FNR, violated journeys (no violation raised)", "Label miss rate", "Predicted UNCERTAIN",
               "Ground-truth UNCERTAIN"], rows))
    A("A single-channel system cannot certify dual-channel agreement, so by the engine's design it reports UNCERTAIN "
      "rather than COMPLETED on a clean trace; its status accuracy and uncertain rate reflect that design rule. "
      "Violation-level metrics are the primary comparison.")
    A("")

    deltas = summary["bootstrap"]["paired_delta_reference_minus_system"]["deltas"]
    if deltas:
        A("### Paired differences (full dual-channel minus each other system)")
        A("")
        rows = []
        for s in order:
            if s in deltas:
                d = deltas[s]
                rows.append([name[s]] + [f"{d[m]['point']:+.3f} [{d[m]['ci_low']:+.3f}, {d[m]['ci_high']:+.3f}]"
                                         for m in ("macro_f1", "exact_set_accuracy", "status_accuracy")])
        E(_table(["Versus", "Macro-F1 difference", "Exact-set accuracy difference", "Status accuracy difference"], rows))

    A("## Per-violation-type metrics")
    A("")
    for t in list(VIOLATION_TYPES) + ["MICRO_ALL"]:
        A(f"**{t}**")
        A("")
        rows = []
        for s in order:
            v = sy[s]["per_violation_type"][t]
            rows.append([name[s], v["truth_labels"], v["tp"], v["fp"], v["fn"], num(v["precision"]), num(v["recall"]), num(v["f1"])])
        E(_table(["System", "Truth labels", "TP", "FP", "FN", "Precision", "Recall", "F1"], rows))
    A("Zero-denominator convention: " + summary["conventions"]["zero_division"])
    A("")

    A("## Research questions")
    A("")
    cross = summary["cross_channel_benefit_by_type"]

    def recall(s, t):
        return cross[t]["by_system"].get(s, {}).get("recall")

    for qn, title, other in (("Q1", "Does dual-channel reasoning detect violations that physical-only evidence cannot?", "physical_only_ablation"),
                             ("Q2", "Does it detect violations that digital-only evidence cannot?", "digital_only_ablation")):
        A(f"### {qn}. {title}")
        A("")
        rows, better = [], []
        for t in VIOLATION_TYPES:
            f, o = recall("full_dual_channel", t), recall(other, t)
            rows.append([t, cross[t]["truth_labels"], num(f), num(o), "n/a" if f is None or o is None else f"{f - o:+.3f}"])
            if f is not None and o is not None and f > o:
                better.append(t)
        E(_table(["Violation type", "Truth labels", "Recall: full", f"Recall: {name[other]}", "Difference"], rows))
        comp = summary["complementarity_exact_match"].get(other)
        if comp:
            A(f"On this benchmark the full system's recall exceeds the {name[other].lower()}'s for: "
              f"{', '.join(better) if better else 'no violation type'}. "
              f"By exact violation-set match, {comp['reference_only_exact']} cases were matched only by the full system and "
              f"{comp['other_only_exact']} only by the {name[other].lower()} ({comp['both_exact']} by both, "
              f"{comp['neither_exact']} by neither).")
        A("")

    A("### Q3. Which violation types benefit specifically from cross-channel evidence?")
    A("")
    rows, gain_types = [], []
    for t in VIOLATION_TYPES:
        g = cross[t]["recall_gain_over_best_single_channel"]
        singles = [recall(s, t) or 0.0 for s in ("physical_only_ablation", "digital_only_ablation") if s in sy]
        rows.append([t, cross[t]["truth_labels"], num(recall("full_dual_channel", t)),
                     num(max(singles) if singles else None), "n/a" if g is None else f"{g:+.3f}"])
        if g is not None and g > 0:
            gain_types.append(t)
    E(_table(["Violation type", "Truth labels", "Recall: full", "Recall: best single channel", "Recall gain"], rows))
    A(f"Recall gain over the better single-channel ablation is positive for: {', '.join(gain_types) if gain_types else 'no violation type'}. "
      "The benchmark deliberately contains faults that exist only as a disagreement between channels, so part of this gain "
      "is structural; the magnitudes, the compound cases and the false-alarm results below are the informative parts.")
    A("")

    A("### Q4. How often does each method produce false alarms?")
    A("")
    rows = []
    for s in order:
        m = sy[s]["metrics"]
        rows.append([name[s], f"{m['conformant_false_alarms']}/{m['conformant_cases']}",
                     f"{m['violation_free_false_alarms']}/{m['violation_free_cases']}",
                     sy[s]["per_violation_type"]["MICRO_ALL"]["fp"]])
    E(_table(["System", "False alarms on conformant journeys", "False alarms on all violation-free journeys",
               "False-positive labels (all cases)"], rows))
    fam_fp = {}
    for r in summary["family_breakdown"]:
        if r["truth_label_count"] == 0 and r["false_positive_labels"] > 0:
            fam_fp.setdefault(r["system_id"], []).append(f"{r['family']} ({r['subset']}): {r['false_positive_labels']} labels over {r['cases']} cases")
    for s in order:
        A(f"- {name[s]}: " + ("; ".join(fam_fp.get(s, [])) if fam_fp.get(s) else "no false alarms on violation-free families") + ".")
    A("")

    A("### Q5. What is the deterministic engine-evaluation latency?")
    A("")
    if latency:
        env = latency["environment"]
        rows = [[name.get(s, s), v["samples"], f"{v['median_us']:.1f}", f"{v['p95_us']:.1f}", f"{v['p99_us']:.1f}"]
                for s, v in ((s, latency["systems"][s]) for s in order if s in latency["systems"])]
        E(_table(["System", "Samples", "Median (µs)", "P95 (µs)", "P99 (µs)"], rows))
        A(f"Measured with `{env['timer']}` after a warm-up of {next(iter(latency['systems'].values()))['warmup_evaluations']} "
          f"evaluations; Python {env['python']} ({env['implementation']}), {env['platform']}, machine {env['machine']}, "
          f"{env['cpu_count']} logical CPUs. {LATENCY_SCOPE}")
    else:
        A("Latency was not measured in this run.")
    A("")
    A(f"**{LATENCY_LABEL}**")
    A("")

    A("## Results by scenario family (exact violation-set match rate)")
    A("")
    fams = sorted({(r["subset"], r["family"]) for r in summary["family_breakdown"]})
    idx = {(r["system_id"], r["subset"], r["family"]): r for r in summary["family_breakdown"]}
    rows = []
    for subset, fam in fams:
        n = idx[(order[0], subset, fam)]["cases"]
        rows.append([f"{subset} / {fam}", n] + [pct(idx[(s, subset, fam)]["exact_match_rate"], 0) for s in order])
    E(_table(["Subset / family", "Cases"] + [name[s] for s in order], rows))

    A("## Limitations")
    A("")
    A(f"- {KNOWN_LIMITATION} {KNOWN_LIMITATION_NOTE}")
    for text in (
        "The benchmark is procedurally generated from one four-step linear procedure; it contains no real sensor data, no camera or detector errors beyond a confidence band, and no real digital-system logs.",
        "Ground truth follows benchmark definitions (BDEF-1) written by the same team that built the engine; it is independent of the engine's code but not of the team's notion of correctness.",
        "Compound cases combine faults on distinct steps only; same-step multi-fault cases are excluded as ambiguous. Journeys are complete (they reach the final step); truncated journeys are out of scope.",
        "Some families (phantom completion, channel contradiction) are constructed so that they require both channels; the resulting advantage over single-channel ablations is partly by construction.",
        "The weak-observation families depend on the benchmark's definition that a performed-but-weakly-observed step is not a fault; other defensible definitions exist.",
        "The ablations reuse the same engine code with one channel removed, so they measure each channel's contribution, not alternative designs. The simple baseline is one possible simple checker.",
        "Bootstrap intervals assume cases are independent draws from this benchmark's designer-chosen composition and say nothing about field performance.",
        ("These are FINAL-split results from a single frozen run; the weak-observation limitation above was accepted before the run and is not reinterpreted here."
         if is_final else
         "These are development-split results: the development benchmark was visible during implementation. The frozen FINAL split has not been evaluated."),
        "Latency is machine-specific and measures engine evaluation only.",
    ):
        A(f"- {text}")
    A("")
    A("## Reproduction")
    A("")
    A("```")
    A(f"python -m apps.evaluation.main run --split {bm['split']}" if not is_final else
      "python -m apps.evaluation.main evaluate --split final --unlock-final-evaluation")
    A("```")
    A("")
    return "\n".join(lines)


def write_report(out_dir: str | Path) -> Path:
    out = Path(out_dir)
    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    latency_path = out / "latency.json"
    latency = json.loads(latency_path.read_text(encoding="utf-8")) if latency_path.exists() else None
    path = out / "report.md"
    path.write_text(render_report(summary, latency), encoding="utf-8")
    return path
