import pytest

from sentinel.conformance.engine import ConformanceEngine
from sentinel.domain.models import JourneyStatus, ViolationType
from simulator.scenarios import scenario


@pytest.mark.parametrize(
    "name, expected_type, expected_step",
    [
        ("omission_b", ViolationType.OMISSION, "B"),
        ("order_inversion_bc", ViolationType.ORDER_INVERSION, "B"),
        ("phantom_completion_b", ViolationType.PHANTOM_COMPLETION, "B"),
        ("channel_contradiction_b", ViolationType.CHANNEL_CONTRADICTION, "B"),
    ],
)
def test_violation_scenarios(name, expected_type, expected_step):
    proc, journey, physical, digital, _ = scenario(name)
    result = ConformanceEngine().evaluate(proc, journey, physical, digital)
    assert result.overall_status == JourneyStatus.VIOLATED
    assert result.violations[0].type == expected_type
    assert result.violations[0].step_id == expected_step


def test_normal_is_conformant():
    proc, journey, physical, digital, _ = scenario("normal")
    result = ConformanceEngine().evaluate(proc, journey, physical, digital)
    assert result.overall_status == JourneyStatus.COMPLETED
    assert result.violations == []


def test_low_confidence_is_uncertain():
    proc, journey, physical, digital, _ = scenario("uncertain_b")
    result = ConformanceEngine().evaluate(proc, journey, physical, digital)
    assert result.overall_status == JourneyStatus.UNCERTAIN
    assert result.violations == []
