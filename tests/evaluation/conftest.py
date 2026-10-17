from __future__ import annotations

import pytest

from sentinel.evaluation.generator import generate_split
from sentinel.evaluation.runner import evaluate_cases


@pytest.fixture(scope="session")
def dev_split():
    return generate_split("dev")


@pytest.fixture(scope="session")
def final_split():
    return generate_split("final")


@pytest.fixture(scope="session")
def dev_eval(dev_split):
    """Dev evaluation with a small bootstrap and no latency, for speed."""
    return evaluate_cases(dev_split.cases, dev_split.manifest, resamples=60, measure_latency_=False)


def cases_of(split, family=None, subset=None):
    return [c for c in split.cases if (family is None or c.scenario_family == family)
            and (subset is None or c.subset == subset)]
