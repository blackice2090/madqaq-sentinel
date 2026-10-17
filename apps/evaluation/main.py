"""M4.1 comparative-evaluation CLI.

    python -m apps.evaluation.main generate --split dev
    python -m apps.evaluation.main evaluate --split dev
    python -m apps.evaluation.main report   --split dev
    python -m apps.evaluation.main run      --split dev      # generate + evaluate + report
    python -m apps.evaluation.main generate --split final    # allowed: writes the frozen manifest only

Evaluating the FINAL split is locked (see sentinel.evaluation.runner).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sentinel.evaluation.generator import generate_split, load_split, write_split
from sentinel.evaluation.report import write_report, write_results
from sentinel.evaluation.runner import (
    BOOTSTRAP_RESAMPLES, FinalEvaluationLockedError, assert_evaluation_allowed, evaluate_cases,
)
from sentinel.evaluation.schema import SPLITS

DEFAULT_OUT = "artifacts/evaluation"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m apps.evaluation.main", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=("generate", "evaluate", "report", "run"))
    p.add_argument("--split", choices=sorted(SPLITS), required=True)
    p.add_argument("--out-dir", default=DEFAULT_OUT, help=f"output root (default {DEFAULT_OUT}, git-ignored)")
    p.add_argument("--resamples", type=int, default=BOOTSTRAP_RESAMPLES, help="bootstrap resamples")
    p.add_argument("--latency-repeats", type=int, default=5)
    p.add_argument("--unlock-final-evaluation", action="store_true",
                   help="future M4.2 flag; final evaluation stays locked in M4.1 even with it")
    return p


def _generate(split: str, out_root: Path) -> None:
    generated = write_split(generate_split(split), out_root)
    cases, manifest = load_split(out_root, split)   # re-read and hash-verify what was written
    d = manifest["class_distribution"]
    print(f"[generate] {split}: {len(cases)} cases, seed {manifest['seed']}, sha256 {manifest['dataset_sha256'][:16]}…")
    print(f"           status {d['ground_truth_status']}")
    print(f"           violation types {d['violation_types']}")
    print(f"           written to {generated}")
    if split == "final":
        print("           FINAL split generated and NOT evaluated (evaluation is locked in M4.1).")


def _evaluate(split: str, out_root: Path, args) -> Path:
    cases, manifest = load_split(out_root, split)
    assert_evaluation_allowed(cases, unlock_final=args.unlock_final_evaluation)
    result = evaluate_cases(cases, manifest, unlock_final=args.unlock_final_evaluation,
                            resamples=args.resamples, latency_repeats=args.latency_repeats)
    write_results(result, out_root / split)
    for sid, body in result.summary["systems"].items():
        m = body["metrics"]
        print(f"[evaluate] {body['display_name']:<34} exact {m['exact_set_accuracy']:.3f}  macro-F1 {m['macro_f1']:.3f}  "
              f"status {m['status_accuracy']:.3f}")
    return out_root / split


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    out_root = Path(args.out_dir)
    if args.split == "final" and args.command != "generate" and not args.unlock_final_evaluation:
        # Refuse before touching any file: nothing about the final split may be evaluated or summarised.
        print("[locked] Evaluating the FINAL split is blocked by default and is not part of M4.1. "
              "Only `generate --split final` is available.", file=sys.stderr)
        return 2
    try:
        if args.command == "generate":
            _generate(args.split, out_root)
        elif args.command == "evaluate":
            _evaluate(args.split, out_root, args)
        elif args.command == "report":
            print(f"[report] {write_report(out_root / args.split)}")
        else:
            _generate(args.split, out_root)
            directory = _evaluate(args.split, out_root, args)
            print(f"[report] {write_report(directory)}")
    except FinalEvaluationLockedError as exc:
        print(f"[locked] {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
