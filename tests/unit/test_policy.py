from __future__ import annotations

from corneal_screening.contracts import (
    AnalysisMode,
    CalibrationStatus,
    CalibrationValidation,
    ReasonCode,
    ResultStatus,
    StageExecution,
    StageName,
    StageState,
)
from corneal_screening.referral.policy import (
    MOCK_RESULT_MESSAGE,
    clinical_decision_allowed,
    decide_mock_outcome,
)


def test_mock_policy_always_requires_manual_review(device_config):
    from corneal_screening.calibration.validation import validate_calibration_package

    decision = decide_mock_outcome(validate_calibration_package(device_config))

    assert decision.status is ResultStatus.MANUAL_REVIEW
    assert MOCK_RESULT_MESSAGE in decision.message
    assert ReasonCode.ANALYSIS_NOT_PERFORMED in decision.reason_codes


def test_allow_screen_negative_cannot_bypass_mock_or_calibration():
    calibration = CalibrationValidation(
        status=CalibrationStatus.MISSING,
        calibration_identifier=None,
        device_configuration_hash="0" * 64,
        compatible=False,
        reason_codes=[ReasonCode.CALIBRATION_MISSING],
        message="missing",
    )
    stages = [
        StageExecution(
            stage_name=stage_name,
            state=StageState.PASSED,
            message="test",
        )
        for stage_name in (
            StageName.QUALITY_ASSESSMENT,
            StageName.CENTRE_DETECTION,
            StageName.SEGMENTATION,
            StageName.RING_TRACKING,
            StageName.FEATURE_EXTRACTION,
        )
    ]

    assert (
        clinical_decision_allowed(
            analysis_mode=AnalysisMode.MOCK,
            calibration=calibration,
            stages=stages,
            allow_screen_negative=True,
        )
        is False
    )
