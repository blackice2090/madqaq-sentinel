"""M5 evidence consistency checker. Read-only: never modifies any file.

    python -m apps.evidence.main check
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVID = ROOT / "docs" / "evidence"
FINAL = ROOT / "docs" / "evaluation" / "final"

REQUIRED_FIELDS = (
    "claim_id", "category", "claim", "evidence", "evidence_source", "evidence_scope",
    "verification_type", "allowed_wording", "prohibited_wording", "limitations", "status",
)
STATUSES = ("VERIFIED", "VERIFIED_WITH_SCOPE", "DEMONSTRATED", "LIMITATION", "NOT_SUPPORTED")
MATRIX_COLUMNS = (
    "claim_id", "short_claim", "evidence_type", "source_file", "source_field_or_section",
    "scope", "safe_for_poster", "safe_for_pitch", "safe_for_demo", "limitations",
)
# Phrases that must never appear as an asserted claim in official evidence documents.
FORBIDDEN_ASSERTIONS = (
    "98.1% accuracy", "98.1% detection accuracy", "95% camera accuracy", "95% system accuracy",
    "95% real-world accuracy", "production ready", "production-ready", "field validated",
    "deployment ready", "government approved", "operationally proven", "beats all competing",
    "real government checkpoint database", "100% of real security violations",
    "perfect phantom-completion detection", "independent real-world validation",
    "out-of-distribution validation", "outperforms all", "proves superiority",
)
DOCS = ("CLAIMS_REGISTRY.md", "FINALIST_CLAIMS_CHEATSHEET.md", "JUDGE_QA.md",
        "POSTER_METRICS.md", "PRESENTATION_RESULTS.md")


def load_claims(path: Path | None = None) -> dict:
    return json.loads((path or EVID / "claims.json").read_text(encoding="utf-8"))


def _csv_rows(name: str) -> list[dict]:
    with (FINAL / name).open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _json_path(obj, path: str):
    for part in path.split("."):
        obj = obj[part]
    return obj


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_negated(text: str, idx: int) -> bool:
    """A forbidden phrase is only tolerated in a clearly marked 'do not say' context."""
    window = text[max(0, idx - 160): idx].lower()
    return any(m in window for m in ("do not say", "forbidden", "prohibited", "never say", "do not use", "not allowed", "must not"))


def check_numeric(check: dict) -> str | None:
    kind = check["kind"]
    if kind == "csv":
        rows = [r for r in _csv_rows(check["file"]) if all(r.get(k) == v for k, v in check["where"].items())]
        if len(rows) != 1:
            return f"{check['file']} {check['where']}: expected 1 row, found {len(rows)}"
        raw = rows[0][check["field"]]
        if raw == "":
            return f"{check['file']} {check['where']} {check['field']}: empty"
        actual = float(raw)
    elif kind == "json":
        actual = _json_path(json.loads((FINAL / check["file"]).read_text(encoding="utf-8")), check["path"])
    elif kind == "text":
        return None if check["contains"] in (FINAL / check["file"]).read_text(encoding="utf-8") else \
            f"{check['file']}: missing text {check['contains']!r}"
    else:
        return f"unknown check kind {kind}"
    if abs(float(actual) - float(check["expected"])) > check.get("tol", 0.0) + 1e-15:
        return f"{check['file']} {check.get('where') or check.get('path')} {check.get('field', '')}: archive {actual} != claimed {check['expected']}"
    return None


def run_checks() -> list[tuple[str, bool, str]]:
    results: list[tuple[str, bool, str]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        results.append((name, ok, detail))

    # 1. claims.json valid
    try:
        data = load_claims()
        claims = data["claims"]
    except Exception as exc:  # noqa: BLE001
        add("claims.json is valid", False, str(exc))
        return results
    problems = []
    ids = [c.get("claim_id") for c in claims]
    if len(set(ids)) != len(ids):
        problems.append("duplicate claim_id")
    for c in claims:
        miss = [f for f in REQUIRED_FIELDS if f not in c]
        if miss:
            problems.append(f"{c.get('claim_id')}: missing {miss}")
        if c.get("status") not in STATUSES:
            problems.append(f"{c.get('claim_id')}: bad status {c.get('status')}")
    expected_ids = [f"C{i:03d}" for i in range(1, 16)]
    if ids != expected_ids:
        problems.append(f"claim ids must be {expected_ids[0]}..{expected_ids[-1]}")
    add("1 claims.json valid, C001-C015 present, schema complete", not problems, "; ".join(problems))

    by_id = {c["claim_id"]: c for c in claims}

    # 2-8: archived metrics (every numeric check of every claim)
    for cid in ("C001", "C002", "C003", "C004", "C005", "C006", "C007", "C008", "C009", "C013", "C014"):
        errs = []
        for chk in by_id[cid].get("numeric_checks", []):
            e = check_numeric(chk)
            if e:
                errs.append(e)
        label = {"C002": "3 C002 = 0.950 as archived", "C003": "4 C003 = 0.981 and CI match archive",
                 "C004": "5 C004 = 0.973 as archived", "C005": "6 C005 = 0 missed / 812 violated",
                 "C006": "7 C006 matches frozen per-class metrics"}.get(cid, f"2 {cid} matches archive")
        add(label, not errs, "; ".join(errs))
    add("8 C009 mentions 60 weak-physical cases",
        "60" in by_id["C009"]["claim"] and "low-confidence" in by_id["C009"]["claim"])

    # 12. numerical claims have evidence source
    bad = [c["claim_id"] for c in claims if c.get("numerical") and not (c["evidence_source"] and c.get("numeric_checks"))]
    add("12 every numerical claim has evidence source and archive checks", not bad, ", ".join(bad))
    missing = []
    for c in claims:
        for s in c["evidence_source"]:
            if not (ROOT / s.split("#")[0]).exists():
                missing.append(s)
    add("12b every evidence source file exists", not missing, ", ".join(missing))

    # 9-11. prohibited wording across claims.json (excluding prohibited_wording fields) and docs
    assertions = []
    for c in claims:
        txt = " ".join([c["claim"], c["evidence"], c["evidence_scope"], c["limitations"], *c["allowed_wording"]]).lower()
        for ph in FORBIDDEN_ASSERTIONS:
            if ph in txt:
                assertions.append(f"{c['claim_id']}: {ph}")
    for name in DOCS:
        p = EVID / name
        if not p.exists():
            assertions.append(f"{name} missing")
            continue
        text = p.read_text(encoding="utf-8")
        low = text.lower()
        for ph in FORBIDDEN_ASSERTIONS:
            for m in re.finditer(re.escape(ph), low):
                if not is_negated(low, m.start()) and not _in_forbidden_line(text, m.start()):
                    assertions.append(f"{name}: {ph}")
    for ph in ("98.1% accuracy",):
        add("9 no claim says '98.1% accuracy'", not any(ph in a for a in assertions))
    add("10 no official claim says '95% camera accuracy'", not any("95% camera accuracy" in a for a in assertions))
    sim_problems = [a for a in assertions if any(k in a for k in ("government", "production", "live checkpoint"))]
    c11 = by_id["C011"]
    if "SIMULATED DIGITAL CHANNEL" not in c11["claim"]:
        sim_problems.append("C011 lacks SIMULATED DIGITAL CHANNEL")
    add("11 simulated digital channel never presented as real integration", not sim_problems, "; ".join(sim_problems))
    add("11b no prohibited wording asserted in claims or evidence documents", not assertions, "; ".join(assertions))

    # 13. benchmark SHA
    try:
        manifest = json.loads((FINAL / "manifest.json").read_text(encoding="utf-8"))["dataset_sha256"]
        summ = json.loads((FINAL / "summary.json").read_text(encoding="utf-8"))["benchmark"]["dataset_sha256"]
        rec = json.loads((FINAL / "FINAL_RUN_RECORD.json").read_text(encoding="utf-8"))["benchmark_sha256"]
        ok = data["benchmark_sha256"] == manifest == summ == rec
        add("13 benchmark SHA in registry matches archived manifest", ok, f"registry={data['benchmark_sha256']} manifest={manifest}")
    except Exception as exc:  # noqa: BLE001
        add("13 benchmark SHA in registry matches archived manifest", False, str(exc))

    # 14. frozen evidence hashes
    bad = []
    for line in (FINAL / "SHA256SUMS.txt").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, name = line.split(None, 1)
        name = name.strip().lstrip("*")
        if sha256(FINAL / name) != digest:
            bad.append(name)
    add("14 frozen evidence hashes (SHA256SUMS.txt) pass", not bad, ", ".join(bad))

    # evidence matrix
    try:
        with (EVID / "EVIDENCE_MATRIX.csv").open(newline="", encoding="utf-8") as fh:
            rdr = csv.DictReader(fh)
            cols = tuple(rdr.fieldnames or ())
            rows = list(rdr)
        cov = {r["claim_id"] for r in rows}
        ok = cols == MATRIX_COLUMNS and cov == set(ids)
        add("15 evidence matrix columns and claim coverage", ok, f"cols={cols} missing={sorted(set(ids) - cov)}")
        srcs = [r["source_file"] for r in rows if not (ROOT / r["source_file"]).exists()]
        add("15b evidence matrix source files exist", not srcs, ", ".join(srcs))
    except Exception as exc:  # noqa: BLE001
        add("15 evidence matrix", False, str(exc))
    return results


def _in_forbidden_line(text: str, idx: int) -> bool:
    start = text.rfind("\n", 0, idx) + 1
    line = text[start: text.find("\n", idx) if text.find("\n", idx) != -1 else len(text)].lower()
    return any(m in line for m in ("do not say", "forbidden", "prohibited", "never say", "not supported", "do not use"))


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["check"]:
        print("usage: python -m apps.evidence.main check")
        return 2
    results = run_checks()
    for name, ok, detail in results:
        print(f"[{'PASS' if ok else 'FAIL'}] {name}" + (f"  -- {detail}" if detail and not ok else ""))
    failed = [r for r in results if not r[1]]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
