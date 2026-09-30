import pytest
from sentinel.domain.models import ProcedureDefinition, ProcedureStep


def test_reject_duplicate_order():
    with pytest.raises(ValueError):
        ProcedureDefinition(
            procedure_id="p", name="bad", steps=[
                ProcedureStep(step_id="A", name="A", order=1),
                ProcedureStep(step_id="B", name="B", order=1),
            ]
        )


def test_reject_noncontiguous_order():
    with pytest.raises(ValueError):
        ProcedureDefinition(
            procedure_id="p", name="bad", steps=[
                ProcedureStep(step_id="A", name="A", order=1),
                ProcedureStep(step_id="B", name="B", order=3),
            ]
        )
