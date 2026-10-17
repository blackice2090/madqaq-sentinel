import csv
import json
import re
from pathlib import Path

import pytest

from apps.evidence import main as ev

ROOT = Path(__file__).resolve().parents[2]
EVID = ROOT / "docs" / "evidence"
FINAL = ROOT / "docs" / "evaluation" / "final"


@pytest.fixture(scope="module")
def data():
    return ev.load_claims()


@pytest.fixture(scope="module")
def claims(data):
    return {c["claim_id"]: c for c in data["claims"]}


def doc(name):
    return (EVID / name).read_text(encoding="utf-8")


def test_claim_schema(data):
    assert [c["claim_id"] for c in data["claims"]] == [f"C{i:03d}" for i in range(1, 16)]
    for c in data["claims"]:
        for f in ev.REQUIRED_FIELDS:
            assert c.get(f) not in (None, "", []), (c["claim_id"], f)
        assert c["status"] in ev.STATUSES
        assert isinstance(c["evidence_source"], list)


def test_status_assignments(claims):
    assert claims["C009"]["status"] == "LIMITATION"
    assert claims["C015"]["status"] == "NOT_SUPPORTED"
    assert claims["C011"]["status"] == "DEMONSTRATED"


def test_metric_consistency_with_archive():
    results = ev.run_checks()
    failed = [r for r in results if not r[1]]
    assert not failed, failed


def test_headline_numbers_against_raw_archive():
    rows = {r["system_id"]: r for r in csv.DictReader((FINAL / "system_comparison.csv").open())}
    full = rows["full_dual_channel"]
    assert float(full["exact_set_accuracy"]) == 0.95
    assert round(float(full["macro_f1"]), 3) == 0.981
    assert round(float(full["micro_f1"]), 3) == 0.973
    assert (int(full["violated_missed_entirely"]), int(full["violated_cases"])) == (0, 812)
    summ = json.loads((FINAL / "summary.json").read_text())
    ci = summ["bootstrap"]["intervals"]["full_dual_channel"]["macro_f1"]
    assert (round(ci["ci_low"], 3), round(ci["ci_high"], 3)) == (0.976, 0.986)


def test_tampered_value_is_detected():
    bad = {"kind": "csv", "file": "system_comparison.csv", "where": {"system_id": "full_dual_channel"},
           "field": "exact_set_accuracy", "expected": 0.96, "tol": 1e-9}
    assert ev.check_numeric(bad) is not None


def test_prohibited_phrase_detection():
    text = "The system is 98.1% accuracy proven.".lower()
    idx = text.find("98.1% accuracy")
    assert not ev.is_negated(text, idx)
    neg = "do not say: the system has 98.1% accuracy".lower()
    assert ev.is_negated(neg, neg.find("98.1% accuracy"))


@pytest.mark.parametrize("name", ev.DOCS)
def test_documents_assert_no_forbidden_phrases(name):
    text = doc(name)
    low = text.lower()
    for ph in ev.FORBIDDEN_ASSERTIONS:
        for m in re.finditer(re.escape(ph), low):
            assert ev.is_negated(low, m.start()) or ev._in_forbidden_line(text, m.start()), (name, ph)


def test_evidence_sources_exist(data):
    for c in data["claims"]:
        for s in c["evidence_source"]:
            assert (ROOT / s.split("#")[0]).exists(), s


def test_numerical_claims_have_sources_and_checks(data):
    for c in data["claims"]:
        if c["numerical"]:
            assert c["evidence_source"] and c["numeric_checks"], c["claim_id"]


def test_evidence_matrix_coverage():
    with (EVID / "EVIDENCE_MATRIX.csv").open(newline="") as fh:
        r = csv.DictReader(fh)
        assert tuple(r.fieldnames) == ev.MATRIX_COLUMNS
        rows = list(r)
    assert {x["claim_id"] for x in rows} == {f"C{i:03d}" for i in range(1, 16)}
    for x in rows:
        assert (ROOT / x["source_file"]).exists()
        assert x["safe_for_poster"] in ("yes", "no")


def test_benchmark_checksum_reference(data):
    manifest = json.loads((FINAL / "manifest.json").read_text())
    assert data["benchmark_sha256"] == manifest["dataset_sha256"]


def test_limitation_present(claims):
    c = claims["C009"]
    assert "60" in c["claim"] and "low-confidence" in c["claim"]
    assert "not been validated as an operationally optimal policy" in c["limitations"] + " ".join(c["allowed_wording"])
    assert "Primary limitation" in doc("POSTER_METRICS.md")
    assert "60 low-confidence" in doc("PRESENTATION_RESULTS.md")


def test_simulated_channel_disclosure(claims):
    assert "SIMULATED DIGITAL CHANNEL" in claims["C011"]["claim"]
    for name in ("JUDGE_QA.md", "FINALIST_CLAIMS_CHEATSHEET.md"):
        assert "SIMULATED DIGITAL CHANNEL" in doc(name)


def test_synthetic_benchmark_disclosure(claims):
    for cid in ("C001", "C002", "C003", "C005", "C006", "C007", "C008"):
        c = claims[cid]
        assert "synthetic" in (c["claim"] + c["evidence_scope"]).lower(), cid
    assert "not a measure of live-camera or field accuracy" in doc("POSTER_METRICS.md")
    assert "same procedural distribution" in claims["C014"]["evidence_scope"]


def test_engine_latency_labelled(claims):
    assert "ENGINE EVALUATION ONLY" in claims["C013"]["claim"]


def test_no_unsupported_production_readiness(claims):
    assert claims["C015"]["status"] == "NOT_SUPPORTED"
    for c in claims.values():
        if c["claim_id"] == "C015":
            continue
        txt = " ".join([c["claim"], c["evidence"], *c["allowed_wording"]]).lower()
        for ph in ("production ready", "production-ready", "field validated", "deployment ready"):
            assert ph not in txt


def test_poster_has_at_most_four_metrics():
    rows = [l for l in doc("POSTER_METRICS.md").splitlines() if l.startswith("| **")]
    assert len(rows) == 4


def test_judge_qa_has_20_questions():
    qs = re.findall(r"^\d+\. \*\*", doc("JUDGE_QA.md"), re.M)
    assert len(qs) >= 20


def test_checker_cli_is_read_only(tmp_path, capsys):
    before = {p: p.read_bytes() for p in list(EVID.iterdir()) + list(FINAL.iterdir())}
    assert ev.main(["check"]) == 0
    after = {p: p.read_bytes() for p in before}
    assert before == after
    assert "checks passed" in capsys.readouterr().out
