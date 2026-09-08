"""Outcome policy kept separate from image processing and the UI."""

from __future__ import annotations

from dataclasses import dataclass

from ..contracts import (
    AnalysisMode,
    CalibrationStatus,
    CalibrationValidation,
    ReasonCode,
    ResultStatus,
    StageExecution,
    StageName,
    StageState,
)

MOCK_RESULT_MESSAGE = "Mock result: image analysis has not been performed."


@dataclass(frozen=True)
class OutcomeDecision:
    status: ResultStatus
    reason_codes: tuple[ReasonCode, ...]
    message: str


def _calibration_reason(status: CalibrationStatus) -> ReasonCode:
    return {
        CalibrationStatus.MISSING: ReasonCode.CALIBRATION_MISSING,
        CalibrationStatus.INVALID: ReasonCode.CALIBRATION_INVALID,
        CalibrationStatus.UNVALIDATED: ReasonCode.CALIBRATION_UNVALIDATED,
        CalibrationStatus.VALIDATED: ReasonCode.CLINICAL_OUTPUT_BLOCKED,
    }[status]


def decide_mock_outcome(
    calibration: CalibrationValidation,
    *,
    allow_screen_negative: bool = False,
) -> OutcomeDecision:
    """Return the only Week 1 outcome: manual review.

    ``allow_screen_negative`` is accepted to make the safety boundary
    explicit, but it can never change a mock result. Future clinical policy
    must independently prove calibration compatibility and stage success.
    """

    del allow_screen_negative
    reasons = [ReasonCode.MOCK_MODE, ReasonCode.ANALYSIS_NOT_PERFORMED]
    if calibration.status != CalibrationStatus.VALIDATED or not calibration.compatible:
        reasons.append(_calibration_reason(calibration.status))
    reasons.append(ReasonCode.CLINICAL_OUTPUT_BLOCKED)
    return OutcomeDecision(
        status=ResultStatus.MANUAL_REVIEW,
        reason_codes=tuple(dict.fromkeys(reasons)),
        message=MOCK_RESULT_MESSAGE,
    )


def clinical_decision_allowed(
    *,
    analysis_mode: AnalysisMode,
    calibration: CalibrationValidation,
    stages: list[StageExecution],
    allow_screen_negative: bool,
) -> bool:
    """Guard future clinical statuses behind every required prerequisite."""

    required_stages = {
        StageName.QUALITY_ASSESSMENT,
        StageName.CENTRE_DETECTION,
        StageName.SEGMENTATION,
        StageName.RING_TRACKING,
        StageName.FEATURE_EXTRACTION,
    }
    stage_states = {stage.stage_name: stage.state for stage in stages}
    return (
        allow_screen_negative
        and analysis_mode != AnalysisMode.MOCK
        and calibration.status == CalibrationStatus.VALIDATED
        and calibration.compatible
        and all(
            stage_states.get(stage) == StageState.PASSED for stage in required_stages
        )
    )
