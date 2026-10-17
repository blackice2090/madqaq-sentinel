"""Byte-level reproducibility of the benchmark and of the deterministic result files."""
import hashlib
import os
import pathlib
import subprocess
import sys

from sentinel.evaluation.generator import generate_split, write_split
from sentinel.evaluation.report import write_results
from sentinel.evaluation.runner import evaluate_cases

ROOT = pathlib.Path(__file__).resolve().parents[2]
DETERMINISTIC = ("summary.json", "system_comparison.csv", "per_class_metrics.csv", "family_breakdown.csv",
                 "case_results.jsonl")


def test_written_benchmark_files_are_byte_identical(tmp_path):
    for sub in ("one", "two"):
        write_split(generate_split("dev"), tmp_path / sub)
    for name in ("benchmark.jsonl", "manifest.json"):
        assert (tmp_path / "one" / "dev" / name).read_bytes() == (tmp_path / "two" / "dev" / name).read_bytes()


def test_deterministic_result_files_are_byte_identical(tmp_path, dev_split):
    for sub in ("one", "two"):
        result = evaluate_cases(dev_split.cases, dev_split.manifest, resamples=40, measure_latency_=False)
        write_results(result, tmp_path / sub)
    for name in DETERMINISTIC:
        assert (tmp_path / "one" / name).read_bytes() == (tmp_path / "two" / name).read_bytes(), name


def test_case_ids_are_sequential_unique_and_deterministic(dev_split, final_split):
    assert [c.case_id for c in dev_split.cases] == [f"DEV-{i:04d}" for i in range(1, 301)]
    assert [c.case_id for c in final_split.cases][:3] == ["FIN-0001", "FIN-0002", "FIN-0003"]
    assert len({c.case_id for c in final_split.cases}) == 1200


def test_generation_does_not_depend_on_hash_randomisation_or_process():
    code = ("from sentinel.evaluation.generator import generate_split;"
            "print(generate_split('dev').manifest['dataset_sha256'], generate_split('final').manifest['dataset_sha256'])")
    outputs = set()
    for seed in ("1", "98765"):
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONPATH": str(ROOT)}
        outputs.add(subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, env=env, cwd=ROOT,
                                   check=True).stdout.strip())
    assert len(outputs) == 1
    dev_hash, final_hash = outputs.pop().split()
    assert dev_hash == generate_split("dev").manifest["dataset_sha256"]
    assert final_hash == generate_split("final").manifest["dataset_sha256"]


# Golden hashes: they pin the FROZEN benchmark. Any generator change that alters either dataset must bump
# GENERATOR_VERSION / BENCHMARK_VERSION and update these on purpose, with review.
GOLDEN_SHA256 = {
    "dev": "9424922f9b9d0bd571b40f4b910173be6dc832d586edb9a765c0541999f0523e",
    "final": "28a3979e7e690cb0957502237f9145a24d816182196179788eaeae8738d48697",
}


def test_benchmark_content_is_pinned_by_golden_hashes(dev_split, final_split):
    assert dev_split.manifest["dataset_sha256"] == GOLDEN_SHA256["dev"]
    assert final_split.manifest["dataset_sha256"] == GOLDEN_SHA256["final"]
