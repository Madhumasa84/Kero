"""Safe outcome policy for screening research outputs."""

from .policy import (
    MOCK_RESULT_MESSAGE,
    clinical_decision_allowed,
    decide_mock_outcome,
)

__all__ = [
    "MOCK_RESULT_MESSAGE",
    "clinical_decision_allowed",
    "decide_mock_outcome",
]
