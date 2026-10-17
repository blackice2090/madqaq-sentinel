"""CLI end to end, the generated report's mandatory wording, and the docs."""
import json
import pathlib

import pytest

from apps.evaluation.main import main
from sentinel.evaluation.statements import (
    ABLATION_SCOPE, CI_SCOPE, FORBIDDEN_PHRASES, LATENCY_SCOPE, SYNTHETIC_SCOPE,
)

ROOT = pathlib.Path(__file__).resolve().parents[2]
FAST = ["--resamples", "20", "--latency-repeats", "1"]


@pytest.fixture(scope="module")
def dev_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("eval")
    assert main(["run", "--split", "dev", "--out-dir", str(out), *FAST]) == 0
    return out / "dev"


def test_cli_runs_the_development_benchmark_end_to_end(dev_run):
    for name in ("benchmark.jsonl", "manifest.json", "summary.json", "per_class_metrics.csv",
                 "system_comparison.csv", "case_results.jsonl", "report.md", "latency.json"):
        assert (dev_run / name).exists(), name
    summary = json.loads((dev_run / "summary.json").read_text())
    assert summary["benchmark"]["split"] == "dev" and summary["benchmark"]["n_cases"] == 300


def test_report_contains_the_mandatory_scope_wording(dev_run):
    text = (dev_run / "report.md").read_text(encoding="utf-8")
    for required in (SYNTHETIC_SCOPE, ABLATION_SCOPE, CI_SCOPE, LATENCY_SCOPE):
        assert required in text
    assert "not live-camera accuracy or field performance" in text
    assert "not external commercial baselines" in text
    assert "Physical-only ablation" in text and "Digital-only ablation" in text
    assert "FINAL split has been generated but no system has been evaluated" in text


def test_report_and_docs_state_the_known_limitation(dev_run):
    from sentinel.evaluation.statements import KNOWN_LIMITATION, KNOWN_LIMITATION_NOTE
    report = (dev_run / "report.md").read_text(encoding="utf-8")
    doc = (ROOT / "docs" / "M4_COMPARATIVE_EVALUATION.md").read_text(encoding="utf-8")
    for text in (report, doc):
        assert KNOWN_LIMITATION in text and KNOWN_LIMITATION_NOTE in text


def test_report_avoids_overclaiming_language(dev_run):
    text = (dev_run / "report.md").read_text(encoding="utf-8").lower()
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in text


def test_report_answers_the_research_questions_and_lists_latency(dev_run):
    text = (dev_run / "report.md").read_text(encoding="utf-8")
    for heading in ("### Q1.", "### Q2.", "### Q3.", "### Q4.", "### Q5."):
        assert heading in text
    assert "Median (µs)" in text and "P95" in text and "P99" in text


def test_final_split_can_be_generated_but_never_evaluated(tmp_path, capsys):
    assert main(["generate", "--split", "final", "--out-dir", str(tmp_path)]) == 0
    final = tmp_path / "final"
    assert sorted(p.name for p in final.iterdir()) == ["benchmark.jsonl", "manifest.json"]
    manifest = json.loads((final / "manifest.json").read_text())
    assert manifest["n_cases"] == 1200 and manifest["evaluation_status"] == "FROZEN_FINAL_NOT_EVALUATED"
    assert "NOT evaluated" in capsys.readouterr().out


@pytest.mark.parametrize("command", ["evaluate", "run", "report"])
@pytest.mark.parametrize("extra", [[], ["--unlock-final-evaluation"]])
def test_final_evaluation_commands_are_blocked(tmp_path, capsys, command, extra):
    assert main(["generate", "--split", "final", "--out-dir", str(tmp_path)]) == 0
    before = sorted(p.name for p in (tmp_path / "final").iterdir())
    assert main([command, "--split", "final", "--out-dir", str(tmp_path), *extra]) == 2
    assert "locked" in capsys.readouterr().err
    assert sorted(p.name for p in (tmp_path / "final").iterdir()) == before       # nothing was produced


def test_evaluate_before_generate_explains_what_to_do(tmp_path, capsys):
    assert main(["evaluate", "--split", "dev", "--out-dir", str(tmp_path)]) == 1
    assert "generate --split dev" in capsys.readouterr().err


def test_split_is_required():
    with pytest.raises(SystemExit):
        main(["generate"])


def test_artifacts_are_git_ignored():
    assert "artifacts/" in (ROOT / ".gitignore").read_text().splitlines()


def test_documentation_exists_with_required_content():
    doc = (ROOT / "docs" / "M4_COMPARATIVE_EVALUATION.md").read_text(encoding="utf-8")
    for required in (SYNTHETIC_SCOPE, ABLATION_SCOPE, "--unlock-final-evaluation", "BDEF-1", "development", "final",
                     "python -m apps.evaluation.main run --split dev", "Limitations"):
        assert required in doc
    for phrase in FORBIDDEN_PHRASES:
        assert phrase not in doc.lower()
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "M4" in readme and "apps.evaluation.main" in readme
