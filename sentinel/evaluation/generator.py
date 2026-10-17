"""Deterministic synthetic benchmark generator (M4.1).

Ground truth comes from the generator's OWN knowledge of the faults it injected (each
family states its labels by construction) and is cross-checked against the independent
oracle (``oracle.derive_ground_truth``). The ConformanceEngine is never imported here.

Reproducibility: every random draw comes from ``StableRandom`` keyed by
(split seed, generator version, family, subset, slot index, attempt), so the same
generator version + seed + configuration yields byte-identical JSONL.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from sentinel.evaluation import oracle
from sentinel.evaluation.rng import StableRandom
from sentinel.evaluation.schema import (
    BENCHMARK_VERSION, CONFIDENT_BAND, CONFIDENCE_CUT, GENERATOR_VERSION, SPLITS, VIOLATION_TYPES, WEAK_BAND,
    BenchmarkCase, DigitalRecord, EventRecord, GroundTruthViolation, LatentWorld, case_from_json_line,
    case_to_json_line, reference_procedure_spec,
)

BASE_N = 300
GAP_MIN, GAP_MAX = 5000, 15000   # ms between consecutive steps within a channel
T0 = 10_000                      # first physical event (ms); keeps jittered times positive
MAX_ATTEMPTS = 50


class GenerationError(RuntimeError):
    pass


class GeneratorInvariantError(RuntimeError):
    """The family template and the independent oracle disagree: a bug, never a rejection."""


class BenchmarkIntegrityError(RuntimeError):
    pass


# ---- plans (latent world + by-construction truth) -------------------------------------
@dataclass(frozen=True)
class Plan:
    world: LatentWorld
    status: str
    truth: tuple[GroundTruthViolation, ...]


def V(vtype: str, step: str, related: str | None = None) -> GroundTruthViolation:
    return GroundTruthViolation(type=vtype, step_id=step, related_step_id=related)  # type: ignore[arg-type]


def _rec(steps, failed=()):
    return [DigitalRecord(step_id=s, outcome="FAILED" if s in failed else "COMPLETED") for s in steps]


def _plan(performed, digital, truth, *, status=None, weak=(), physical_online=True, digital_online=True) -> Plan:
    world = LatentWorld(
        performed=list(performed), weak_physical=list(weak), physical_online=physical_online,
        digital_online=digital_online, digital_record=digital if digital_online else [],
    )
    return Plan(world, status or ("VIOLATED" if truth else "UNCERTAIN"), tuple(truth))


def f_conformant_clean(rng):
    return _plan("ABCD", _rec("ABCD"), (), status="COMPLETED")


def f_omission_single(rng):
    x = rng.choice("BC")
    seq = [s for s in "ABCD" if s != x]
    return _plan(seq, _rec(seq), (V("OMISSION", x),))


def f_omission_double(rng):
    return _plan("AD", _rec("AD"), (V("OMISSION", "B"), V("OMISSION", "C")))


def f_inversion_single(rng):
    seq, late, before = rng.choice([("ACBD", "B", "C"), ("ABDC", "C", "D"), ("ACDB", "B", "D")])
    return _plan(seq, _rec(seq), (V("ORDER_INVERSION", late, before),))


def f_phantom_single(rng):
    x = rng.choice("BC")
    return _plan([s for s in "ABCD" if s != x], _rec("ABCD"), (V("PHANTOM_COMPLETION", x),))


def f_phantom_double(rng):
    return _plan("AD", _rec("ABCD"), (V("PHANTOM_COMPLETION", "B"), V("PHANTOM_COMPLETION", "C")))


def f_contradiction_single(rng):
    x = rng.choice("BCD")
    return _plan("ABCD", _rec("ABCD", failed=(x,)), (V("CHANNEL_CONTRADICTION", x),))


def f_compound_phantom_omission(rng):
    if rng.chance(0.5):
        return _plan("AD", _rec("ABD"), (V("PHANTOM_COMPLETION", "B"), V("OMISSION", "C")))
    return _plan("AD", _rec("ACD"), (V("OMISSION", "B"), V("PHANTOM_COMPLETION", "C")))


def f_compound_contradiction_omission(rng):
    if rng.chance(0.5):
        return _plan("ABD", _rec("ABD", failed=("B",)), (V("CHANNEL_CONTRADICTION", "B"), V("OMISSION", "C")))
    return _plan("ACD", _rec("ACD", failed=("C",)), (V("OMISSION", "B"), V("CHANNEL_CONTRADICTION", "C")))


def f_compound_phantom_contradiction(rng):
    if rng.chance(0.5):
        return _plan("ACD", _rec("ABCD", failed=("C",)), (V("PHANTOM_COMPLETION", "B"), V("CHANNEL_CONTRADICTION", "C")))
    return _plan("ABD", _rec("ABCD", failed=("B",)), (V("CHANNEL_CONTRADICTION", "B"), V("PHANTOM_COMPLETION", "C")))


def f_compound_phantom_inversion(rng):
    if rng.chance(0.5):
        return _plan("ADC", _rec("ABDC"), (V("PHANTOM_COMPLETION", "B"), V("ORDER_INVERSION", "C", "D")))
    return _plan("ADB", _rec("ACDB"), (V("PHANTOM_COMPLETION", "C"), V("ORDER_INVERSION", "B", "D")))


def f_uncertain_physical_only(rng):
    return _plan("ABCD", [], (), status="UNCERTAIN", digital_online=False)


def f_uncertain_digital_only(rng):
    return _plan("ABCD", _rec("ABCD"), (), status="UNCERTAIN", physical_online=False)


def f_weak_midjourney(rng):
    return _plan("ABCD", _rec("ABCD"), (), status="UNCERTAIN", weak=(rng.choice("BC"),))


def f_weak_tail(rng):
    return _plan("ABCD", _rec("ABCD"), (), status="UNCERTAIN", weak=("D",))


FAMILIES: dict[str, Callable[[StableRandom], Plan]] = {
    "conformant_clean": f_conformant_clean,
    "omission_single": f_omission_single,
    "omission_double": f_omission_double,
    "inversion_single": f_inversion_single,
    "phantom_single": f_phantom_single,
    "phantom_double": f_phantom_double,
    "contradiction_single": f_contradiction_single,
    "compound_phantom_omission": f_compound_phantom_omission,
    "compound_contradiction_omission": f_compound_contradiction_omission,
    "compound_phantom_contradiction": f_compound_phantom_contradiction,
    "compound_phantom_inversion": f_compound_phantom_inversion,
    "uncertain_physical_only": f_uncertain_physical_only,
    "uncertain_digital_only": f_uncertain_digital_only,
    "weak_physical_midjourney": f_weak_midjourney,
    "weak_physical_tail": f_weak_tail,
}


# ---- composition ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Slot:
    family: str
    subset: str      # core | boundary | robustness
    count: int       # per 300 cases
    noisy: bool = False


COMPOSITION: tuple[Slot, ...] = (
    Slot("conformant_clean", "core", 40),
    Slot("omission_single", "core", 20),
    Slot("omission_double", "core", 10),
    Slot("inversion_single", "core", 25),
    Slot("phantom_single", "core", 25),
    Slot("phantom_double", "core", 10),
    Slot("contradiction_single", "core", 25),
    Slot("compound_phantom_omission", "core", 10),
    Slot("compound_contradiction_omission", "core", 10),
    Slot("compound_phantom_contradiction", "core", 10),
    Slot("compound_phantom_inversion", "core", 10),
    Slot("uncertain_physical_only", "boundary", 10),
    Slot("uncertain_digital_only", "boundary", 10),
    Slot("weak_physical_midjourney", "boundary", 15),
    Slot("weak_physical_tail", "boundary", 10),
    Slot("conformant_clean", "robustness", 12, True),
    Slot("omission_single", "robustness", 8, True),
    Slot("inversion_single", "robustness", 10, True),
    Slot("phantom_single", "robustness", 10, True),
    Slot("contradiction_single", "robustness", 10, True),
    Slot("compound_phantom_omission", "robustness", 3, True),
    Slot("compound_contradiction_omission", "robustness", 3, True),
    Slot("compound_phantom_contradiction", "robustness", 2, True),
    Slot("compound_phantom_inversion", "robustness", 2, True),
)
assert sum(s.count for s in COMPOSITION) == BASE_N


# ---- realisation: latent world -> event streams -------------------------------------------
def _conf(rng: StableRandom, band: tuple[int, int]) -> float:
    return rng.randint(*band) / 100.0


class _Ids:
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.n = {"P": 0, "D": 0}

    def next(self, channel: str) -> str:
        self.n[channel] += 1
        return f"{self.case_id}-{channel}{self.n[channel]:02d}"


def _realize(world: LatentWorld, ids: _Ids, rng: StableRandom) -> tuple[list[EventRecord], list[EventRecord]]:
    phys: list[EventRecord] = []
    if world.physical_online:
        t = T0 + rng.randint(0, 2000)
        weak = set(world.weak_physical)
        for k, step in enumerate(world.performed):
            if k:
                t += rng.randint(GAP_MIN, GAP_MAX)
            phys.append(EventRecord(
                event_id=ids.next("P"), source="PHYSICAL", event_type="STEP_OBSERVED", step_id=step, t_ms=t,
                confidence=_conf(rng, WEAK_BAND if step in weak else CONFIDENT_BAND)))
    dig: list[EventRecord] = []
    if world.digital_online:
        t = T0 + rng.randint(200, 2000)
        for k, rec in enumerate(world.digital_record):
            if k:
                t += rng.randint(GAP_MIN, GAP_MAX)
            dig.append(EventRecord(
                event_id=ids.next("D"), source="DIGITAL", step_id=rec.step_id, t_ms=t, confidence=1.0,
                event_type="STEP_COMPLETED" if rec.outcome == "COMPLETED" else "STEP_FAILED"))
    return phys, dig


# ---- noise: ground-truth-preserving by design, verified by the audit ----------------------
def _op_jitter(phys, dig, rng, ids):
    for e in phys + dig:
        e.t_ms += rng.randint(-3000, 3000)


def _op_digital_delay(phys, dig, rng, ids):
    delay = rng.randint(3000, 30000)
    for e in dig:
        e.t_ms += delay


def _op_physical_repeated(phys, dig, rng, ids):
    e = rng.choice([x for x in phys if x.confidence >= CONFIDENCE_CUT])
    t = e.t_ms
    for _ in range(rng.randint(1, 2)):
        t += rng.randint(300, 1500)
        phys.append(EventRecord(event_id=ids.next("P"), source="PHYSICAL", event_type="STEP_OBSERVED",
                                step_id=e.step_id, t_ms=t, confidence=_conf(rng, CONFIDENT_BAND)))


def _op_digital_repeated(phys, dig, rng, ids):
    e = rng.choice(dig)
    dig.append(EventRecord(event_id=ids.next("D"), source="DIGITAL", event_type=e.event_type, step_id=e.step_id,
                           t_ms=e.t_ms + rng.randint(200, 1200), confidence=1.0))


def _op_low_conf_duplicate(phys, dig, rng, ids):
    e = rng.choice([x for x in phys if x.confidence >= CONFIDENCE_CUT])
    phys.append(EventRecord(event_id=ids.next("P"), source="PHYSICAL", event_type="STEP_OBSERVED",
                            step_id=e.step_id, t_ms=e.t_ms + rng.randint(200, 1000), confidence=_conf(rng, WEAK_BAND)))


def _op_physical_duplicate_delivery(phys, dig, rng, ids):
    phys.append(rng.choice(phys).model_copy())


def _op_digital_duplicate_delivery(phys, dig, rng, ids):
    dig.append(rng.choice(dig).model_copy())


# Application order matters: time-shifting ops first, so duplicate deliveries stay exact copies.
NOISE_OPS: dict[str, Callable] = {
    "timestamp_jitter": _op_jitter,
    "digital_delay": _op_digital_delay,
    "physical_repeated_observation": _op_physical_repeated,
    "digital_repeated_record": _op_digital_repeated,
    "physical_low_conf_duplicate": _op_low_conf_duplicate,
    "physical_duplicate_delivery": _op_physical_duplicate_delivery,
    "digital_duplicate_delivery": _op_digital_duplicate_delivery,
}
NOISE_NAMES: tuple[str, ...] = tuple(NOISE_OPS)


def _choose_noise(ordinal: int, rng: StableRandom) -> list[str]:
    chosen = {NOISE_NAMES[ordinal % len(NOISE_NAMES)]}
    if rng.chance(0.4):
        chosen.add(rng.choice([n for n in NOISE_NAMES if n not in chosen]))
    return [n for n in NOISE_NAMES if n in chosen]   # canonical application order


# ---- case construction ----------------------------------------------------------------------
def _check_plan(plan: Plan, procedure) -> None:
    status, derived = oracle.derive_ground_truth(plan.world, procedure)
    truth = sorted(plan.truth, key=lambda v: (VIOLATION_TYPES.index(v.type), v.step_id))
    if status != plan.status or [v.model_dump() for v in truth] != [v.model_dump() for v in derived]:
        raise GeneratorInvariantError(f"family template disagrees with the oracle: {plan} vs {status} {derived}")


def _build_case(spec, procedure, family, subset, noisy, slot_k, ordinal, index) -> tuple[BenchmarkCase, int]:
    case_id = f"{spec.id_prefix}-{index + 1:04d}"
    rejected = 0
    for attempt in range(MAX_ATTEMPTS):
        rng = StableRandom(spec.seed, GENERATOR_VERSION, family, subset, slot_k, attempt)
        plan = FAMILIES[family](rng)
        _check_plan(plan, procedure)
        ids = _Ids(case_id)
        phys, dig = _realize(plan.world, ids, rng)
        noise: list[str] = []
        if noisy:
            noise = _choose_noise(ordinal, rng)
            for name in noise:
                NOISE_OPS[name](phys, dig, rng, ids)
        phys.sort(key=lambda e: (e.t_ms, e.event_id))
        dig.sort(key=lambda e: (e.t_ms, e.event_id))
        _, violations = oracle.derive_ground_truth(plan.world, procedure)
        case = BenchmarkCase(
            case_id=case_id, benchmark_version=BENCHMARK_VERSION, generator_version=GENERATOR_VERSION,
            split=spec.name, seed=spec.seed, index=index, subset=subset, scenario_family=family,
            noise_conditions=noise, procedure=procedure, world=plan.world,
            physical_events=phys, digital_events=dig,
            ground_truth_status=plan.status,
            ground_truth_violations=violations,
            ground_truth_labels=sorted({v.label for v in violations}),
        )
        if not oracle.audit_case(case):
            return case, rejected
        rejected += 1   # ambiguous / inconsistent candidate: rejected and regenerated
    raise GenerationError(f"could not build an unambiguous {family} case after {MAX_ATTEMPTS} attempts")


@dataclass
class GeneratedSplit:
    split: str
    cases: list[BenchmarkCase]
    manifest: dict
    jsonl: str


def generate_split(split: str, *, n_cases: int | None = None, seed: int | None = None) -> GeneratedSplit:
    base = SPLITS[split]
    spec = type(base)(base.name, base.seed if seed is None else seed, base.n_cases if n_cases is None else n_cases, base.id_prefix)
    if spec.n_cases % BASE_N or spec.n_cases <= 0:
        raise ValueError(f"n_cases must be a positive multiple of {BASE_N}")
    scale = spec.n_cases // BASE_N
    procedure = reference_procedure_spec()

    items: list[tuple[str, str, bool, int, int]] = []   # family, subset, noisy, slot_k, ordinal
    ordinal = 0
    for slot in COMPOSITION:
        for k in range(slot.count * scale):
            items.append((slot.family, slot.subset, slot.noisy, k, ordinal if slot.noisy else -1))
            if slot.noisy:
                ordinal += 1
    StableRandom(spec.seed, GENERATOR_VERSION, "order").shuffle(items)

    cases: list[BenchmarkCase] = []
    rejected = 0
    for index, (family, subset, noisy, k, ordn) in enumerate(items):
        case, rej = _build_case(spec, procedure, family, subset, noisy, k, ordn, index)
        cases.append(case)
        rejected += rej

    jsonl = "".join(case_to_json_line(c) + "\n" for c in cases)
    return GeneratedSplit(split, cases, _manifest(spec, scale, cases, rejected, jsonl), jsonl)


def _count(items) -> dict:
    out: dict = {}
    for i in items:
        out[str(i)] = out.get(str(i), 0) + 1
    return dict(sorted(out.items()))


def _manifest(spec, scale: int, cases: list[BenchmarkCase], rejected: int, jsonl: str) -> dict:
    return {
        "benchmark_version": BENCHMARK_VERSION,
        "generator_version": GENERATOR_VERSION,
        "split": spec.name,
        "seed": spec.seed,
        "n_cases": len(cases),
        "case_id_prefix": spec.id_prefix,
        "procedure_id": cases[0].procedure.procedure_id,
        "composition_per_300": {f"{s.subset}/{s.family}": s.count for s in COMPOSITION},
        "composition_scale": scale,
        "class_distribution": {
            "ground_truth_status": _count(c.ground_truth_status for c in cases),
            "violation_types": _count(v.type for c in cases for v in c.ground_truth_violations),
            "violation_labels": _count(l for c in cases for l in c.ground_truth_labels),
            "violations_per_case": _count(len(c.ground_truth_violations) for c in cases),
        },
        "subsets": _count(c.subset for c in cases),
        "scenario_families": _count(c.scenario_family for c in cases),
        "noise_conditions": _count(n for c in cases for n in c.noise_conditions),
        "rejected_candidates": rejected,
        "ground_truth_method": "family-by-construction labels cross-checked against sentinel.evaluation.oracle (BDEF-1); "
                               "ConformanceEngine is never used to produce labels",
        "contains_images": False,
        "contains_personal_data": False,
        "dataset_file": "benchmark.jsonl",
        "dataset_sha256": hashlib.sha256(jsonl.encode("utf-8")).hexdigest(),
    }


# ---- persistence ------------------------------------------------------------------------------
def write_split(generated: GeneratedSplit, out_root: str | Path) -> Path:
    directory = Path(out_root) / generated.split
    directory.mkdir(parents=True, exist_ok=True)
    manifest = dict(generated.manifest)
    manifest["evaluation_status"] = (
        "DEVELOPMENT_BENCHMARK" if generated.split == "dev" else "FROZEN_FINAL_NOT_EVALUATED"
    )
    with open(directory / "benchmark.jsonl", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(generated.jsonl)
    with open(directory / "manifest.json", "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return directory


def load_split(out_root: str | Path, split: str) -> tuple[list[BenchmarkCase], dict]:
    directory = Path(out_root) / split
    data_path, manifest_path = directory / "benchmark.jsonl", directory / "manifest.json"
    if not data_path.exists() or not manifest_path.exists():
        raise FileNotFoundError(
            f"{data_path} not found; run: python -m apps.evaluation.main generate --split {split}")
    raw = data_path.read_bytes()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if hashlib.sha256(raw).hexdigest() != manifest["dataset_sha256"]:
        raise BenchmarkIntegrityError(f"{data_path} does not match its manifest hash; regenerate the split")
    cases = [case_from_json_line(line) for line in raw.decode("utf-8").splitlines() if line.strip()]
    if len(cases) != manifest["n_cases"]:
        raise BenchmarkIntegrityError("case count does not match the manifest")
    return cases, manifest
