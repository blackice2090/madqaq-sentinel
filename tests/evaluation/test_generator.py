"""Benchmark generation: determinism, composition, and ground truth checked against the EVIDENCE."""
import ast
import pathlib

import pytest

from sentinel.conformance.engine import ConformanceEngine
from sentinel.evaluation import generator as gen
from sentinel.evaluation.generator import generate_split
from sentinel.evaluation.oracle import audit_case
from sentinel.evaluation.schema import CONFIDENCE_CUT, FINAL_SEED, DEV_SEED, SPLITS, VIOLATION_TYPES
from tests.evaluation.conftest import cases_of


def _signature(case):
    return (tuple((e.step_id, e.t_ms, e.confidence, e.event_type) for e in case.physical_events),
            tuple((e.step_id, e.t_ms, e.confidence, e.event_type) for e in case.digital_events))


def test_dev_generation_is_deterministic(dev_split):
    again = generate_split("dev")
    assert again.jsonl == dev_split.jsonl
    assert again.manifest == dev_split.manifest


def test_final_generation_is_deterministic(final_split):
    again = generate_split("final")
    assert again.jsonl == final_split.jsonl
    assert again.manifest["dataset_sha256"] == final_split.manifest["dataset_sha256"]


def test_dev_and_final_differ_in_seed_ids_and_content(dev_split, final_split):
    assert SPLITS["dev"].seed == DEV_SEED == 20261017 and SPLITS["final"].seed == FINAL_SEED == 20261123
    assert {c.seed for c in dev_split.cases} == {DEV_SEED}
    assert {c.seed for c in final_split.cases} == {FINAL_SEED}
    dev_ids, final_ids = {c.case_id for c in dev_split.cases}, {c.case_id for c in final_split.cases}
    assert not dev_ids & final_ids
    assert all(i.startswith("DEV-") for i in dev_ids) and all(i.startswith("FIN-") for i in final_ids)
    assert not {_signature(c) for c in dev_split.cases} & {_signature(c) for c in final_split.cases}
    assert dev_split.manifest["dataset_sha256"] != final_split.manifest["dataset_sha256"]


def test_sizes_and_composition(dev_split, final_split):
    assert len(dev_split.cases) == 300 and len(final_split.cases) == 1200
    assert dev_split.manifest["subsets"] == {"boundary": 45, "core": 195, "robustness": 60}
    assert final_split.manifest["subsets"] == {"boundary": 180, "core": 780, "robustness": 240}
    types = dev_split.manifest["class_distribution"]["violation_types"]
    assert set(types) == set(VIOLATION_TYPES) and all(n > 0 for n in types.values())
    status = dev_split.manifest["class_distribution"]["ground_truth_status"]
    assert set(status) == {"COMPLETED", "VIOLATED", "UNCERTAIN"}
    assert dev_split.manifest["class_distribution"]["violations_per_case"].get("2", 0) > 0   # multi-label present


def test_manifest_carries_version_seed_and_hash(dev_split):
    m = dev_split.manifest
    assert m["benchmark_version"] and m["generator_version"] and m["seed"] == DEV_SEED and m["split"] == "dev"
    assert len(m["dataset_sha256"]) == 64 and m["contains_images"] is False and m["contains_personal_data"] is False


def test_labels_include_step_ids(dev_split):
    for c in dev_split.cases:
        for label in c.ground_truth_labels:
            vtype, step = label.split(":")
            assert vtype in VIOLATION_TYPES and step in "ABCD"
        for v in c.ground_truth_violations:
            assert v.step_id in "ABCD"
            if v.type == "ORDER_INVERSION":
                assert v.related_step_id in "ABCD"


def test_conformant_cases_have_no_violations(dev_split):
    clean = cases_of(dev_split, "conformant_clean")
    assert len(clean) == 52
    for c in clean:
        assert c.ground_truth_status == "COMPLETED" and c.ground_truth_violations == [] and c.ground_truth_labels == []


def _conf_phys(c):
    return [e for e in c.physical_events if e.confidence >= CONFIDENCE_CUT]


def test_phantom_cases_have_the_cross_channel_mismatch(dev_split):
    seen = 0
    for c in dev_split.cases:
        for v in c.ground_truth_violations:
            if v.type != "PHANTOM_COMPLETION":
                continue
            seen += 1
            assert any(e.step_id == v.step_id and e.event_type == "STEP_COMPLETED" for e in c.digital_events)
            assert not any(e.step_id == v.step_id for e in c.physical_events)          # no physical trace at all
            order = "ABCD".index
            assert any(order(e.step_id) > order(v.step_id) for e in _conf_phys(c))     # physically progressed beyond
    assert seen == dev_split.manifest["class_distribution"]["violation_types"]["PHANTOM_COMPLETION"]


def test_contradiction_cases_have_physical_observation_and_digital_failure(dev_split):
    seen = 0
    for c in dev_split.cases:
        for v in c.ground_truth_violations:
            if v.type != "CHANNEL_CONTRADICTION":
                continue
            seen += 1
            assert any(e.step_id == v.step_id for e in _conf_phys(c))
            assert any(e.step_id == v.step_id and e.event_type == "STEP_FAILED" for e in c.digital_events)
    assert seen > 0


def test_omission_ground_truth_is_correct(dev_split):
    seen = 0
    order = "ABCD".index
    for c in dev_split.cases:
        for v in c.ground_truth_violations:
            if v.type != "OMISSION":
                continue
            seen += 1
            assert not any(e.step_id == v.step_id for e in c.physical_events + c.digital_events)   # absent in BOTH channels
            seen_steps = [e.step_id for e in c.physical_events + c.digital_events]
            assert any(order(s) > order(v.step_id) for s in seen_steps)                          # a later step exists
    assert seen > 0


def test_order_inversion_ground_truth_is_correct(dev_split):
    seen = 0
    order = "ABCD".index
    for c in dev_split.cases:
        for v in c.ground_truth_violations:
            if v.type != "ORDER_INVERSION":
                continue
            seen += 1
            seq = [e.step_id for e in sorted(_conf_phys(c), key=lambda e: (e.t_ms, e.event_id))]
            first_late = seq.index(v.step_id)
            assert any(order(s) > order(v.step_id) for s in seq[:first_late])
            assert seq.index(v.related_step_id) < first_late
    assert seen > 0


def test_boundary_and_noise_families_are_labelled(dev_split):
    robust = cases_of(dev_split, subset="robustness")
    assert len(robust) == 60 and all(c.noise_conditions for c in robust)
    assert all(not c.noise_conditions for c in dev_split.cases if c.subset != "robustness")
    assert set(dev_split.manifest["noise_conditions"]) == set(gen.NOISE_NAMES)    # every robustness operator is exercised
    for c in cases_of(dev_split, subset="boundary"):
        assert c.ground_truth_status == "UNCERTAIN" and c.ground_truth_labels == []


def test_every_dev_case_passes_the_independent_audit(dev_split):
    assert [c.case_id for c in dev_split.cases if audit_case(c)] == []


def test_no_images_or_identity_fields(dev_split):
    keys = set(dev_split.cases[0].model_dump())
    assert not {k for k in keys if "image" in k or "name" in k or "identity" in k or "tracker" in k}


def test_ground_truth_is_made_without_calling_the_conformance_engine(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("ConformanceEngine must not be used to create benchmark labels")
    monkeypatch.setattr(ConformanceEngine, "evaluate", boom)
    assert len(generate_split("dev").cases) == 300


@pytest.mark.parametrize("module", ["generator", "oracle", "schema", "rng"])
def test_label_modules_do_not_import_the_engine_or_systems(module):
    path = pathlib.Path(gen.__file__).with_name(f"{module}.py")
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
    forbidden = {"sentinel.conformance", "sentinel.conformance.engine", "sentinel.evaluation.adapters",
                 "sentinel.evaluation.baselines", "sentinel.evaluation.runner", "sentinel.dual_channel"}
    assert not imported & forbidden


def test_ambiguous_candidates_are_rejected_and_regenerated(monkeypatch):
    # Shrinking the step gaps lets noise reorder events; those candidates must be rejected, never relabelled.
    monkeypatch.setattr(gen, "GAP_MIN", 1000)
    monkeypatch.setattr(gen, "GAP_MAX", 2500)
    result = generate_split("dev")
    assert result.manifest["rejected_candidates"] > 0
    assert [c.case_id for c in result.cases if audit_case(c)] == []


def test_generation_gives_up_loudly_when_a_case_cannot_be_made_unambiguous(monkeypatch):
    monkeypatch.setattr(gen, "GAP_MIN", 1)
    monkeypatch.setattr(gen, "GAP_MAX", 2)
    with pytest.raises(gen.GenerationError):
        generate_split("dev")
