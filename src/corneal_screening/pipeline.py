"""Week 1 pipeline orchestration.

Image loading, calibration validation and the outcome policy remain separate
so later processing stages can be added without changing the API contract.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from . import SOFTWARE_VERSION
from .audit.hashing import hash_device_configuration
from .calibration.validation import validate_calibration_package
from .contracts import (
    AnalysisRequest,
    AnalysisResult,
    CalibrationStatus,
    CalibrationValidation,
    CentreInformation,
    DeviceConfiguration,
    FeatureMeasurements,
    QualityMeasurements,
    ReasonCode,
    ResultStatus,
    RingTrackingInformation,
    StageExecution,
    StageName,
    StageState,
)
from .image_processing import ImageLoadError, ImageLoadLimits, LoadedImage, load_image
from .referral.policy import decide_mock_outcome


def _now() -> datetime:
    return datetime.now(timezone.utc)  # noqa: UP017


def _stage(
    stage_name: StageName,
    state: StageState,
    message: str,
    reason_codes: list[ReasonCode] | None = None,
) -> StageExecution:
    if state == StageState.NOT_RUN:
        started_at = finished_at = None
    else:
        started_at = _now()
        finished_at = _now()
    return StageExecution(
        stage_name=stage_name,
        state=state,
        started_at=started_at,
        finished_at=finished_at,
        reason_codes=reason_codes or [],
        message=message,
    )


def _unimplemented_stages() -> list[StageExecution]:
    message = "Not implemented in Week 1; no analysis was performed."
    return [
        _stage(
            stage_name,
            StageState.NOT_RUN,
            message,
            [ReasonCode.STAGE_NOT_IMPLEMENTED],
        )
        for stage_name in (
            StageName.QUALITY_ASSESSMENT,
            StageName.CENTRE_DETECTION,
            StageName.SEGMENTATION,
            StageName.RING_TRACKING,
            StageName.FEATURE_EXTRACTION,
        )
    ]


def _blocked_processing_stages(message: str) -> list[StageExecution]:
    return [
        _stage(stage_name, StageState.BLOCKED, message)
        for stage_name in (
            StageName.QUALITY_ASSESSMENT,
            StageName.CENTRE_DETECTION,
            StageName.SEGMENTATION,
            StageName.RING_TRACKING,
            StageName.FEATURE_EXTRACTION,
        )
    ]


def _base_result_kwargs(
    metadata: AnalysisRequest,
    *,
    software_version: str,
    device_configuration_hash: str | None,
    calibration_status: CalibrationStatus,
    calibration_identifier: str | None,
    original_image_sha256: str | None,
    quality_measurements: QualityMeasurements,
    status: ResultStatus,
    reason_codes: list[ReasonCode],
    message: str,
    stages: list[StageExecution],
) -> dict:
    return {
        "schema_version": metadata.schema_version,
        "software_version": software_version,
        "analysis_id": uuid4(),
        "analysis_mode": metadata.analysis_mode,
        "timestamp": _now(),
        "anonymous_patient_id": metadata.anonymous_patient_id,
        "eye": metadata.eye,
        "capture_session_id": metadata.capture_session_id,
        "operator_id": metadata.operator_id,
        "capture_timestamp": metadata.capture_timestamp,
        "status": status,
        "reason_codes": reason_codes,
        "message": message,
        "stage_execution": stages,
        "device_version": metadata.device_version,
        "device_configuration_hash": device_configuration_hash,
        "calibration_status": calibration_status,
        "calibration_identifier": calibration_identifier,
        "original_image_sha256": original_image_sha256,
        "quality_measurements": quality_measurements,
        "centre_information": CentreInformation(),
        "ring_tracking": RingTrackingInformation(),
        "features": FeatureMeasurements(),
        "artifact_references": [],
    }


def _image_limits(device_config: DeviceConfiguration) -> ImageLoadLimits:
    limits = device_config.runtime_limits
    return ImageLoadLimits(
        max_upload_bytes=limits.max_upload_bytes,
        max_decoded_width_px=limits.max_decoded_width_px,
        max_decoded_height_px=limits.max_decoded_height_px,
        max_decoded_pixels=limits.max_decoded_pixels,
        supported_extensions=tuple(limits.supported_extensions),
    )


def _quality_from_image(image: LoadedImage) -> QualityMeasurements:
    return QualityMeasurements(
        image_width_px=image.width_px,
        image_height_px=image.height_px,
        channel_count=image.channel_count,
        source_format=image.image_format,
        orientation_transformation=image.orientation_transformation,
    )


def _calibration_stage(calibration: CalibrationValidation) -> StageExecution:
    if calibration.status == CalibrationStatus.VALIDATED and calibration.compatible:
        return _stage(
            StageName.CALIBRATION_VALIDATION,
            StageState.PASSED,
            calibration.message,
        )
    return _stage(
        StageName.CALIBRATION_VALIDATION,
        StageState.FAILED,
        calibration.message,
        calibration.reason_codes,
    )


def _result_for_image_error(
    metadata: AnalysisRequest,
    *,
    software_version: str,
    device_configuration_hash: str,
    calibration: CalibrationValidation,
    error: ImageLoadError,
) -> AnalysisResult:
    stages = [
        _stage(
            StageName.INPUT_VALIDATION,
            StageState.PASSED,
            "Metadata validated before image loading.",
        ),
        _stage(
            StageName.DEVICE_CONFIGURATION_VALIDATION,
            StageState.PASSED,
            "Device configuration matches the request.",
        ),
        _stage(
            StageName.IMAGE_LOADING,
            StageState.FAILED,
            error.message,
            [error.code],
        ),
        _calibration_stage(calibration),
        *_blocked_processing_stages("Blocked because image loading failed."),
        _stage(
            StageName.OUTCOME_POLICY,
            StageState.PASSED,
            "Recapture is required; no clinical decision was generated.",
        ),
    ]
    reasons = [error.code, ReasonCode.CLINICAL_OUTPUT_BLOCKED]
    if calibration.status != CalibrationStatus.VALIDATED:
        reasons.extend(calibration.reason_codes)
    message = f"{error.message} {error.instruction}"
    return AnalysisResult(
        **_base_result_kwargs(
            metadata,
            software_version=software_version,
            device_configuration_hash=device_configuration_hash,
            calibration_status=calibration.status,
            calibration_identifier=calibration.calibration_identifier,
            original_image_sha256=error.original_sha256,
            quality_measurements=QualityMeasurements(),
            status=ResultStatus.RECAPTURE_REQUIRED,
            reason_codes=list(dict.fromkeys(reasons)),
            message=message,
            stages=stages,
        )
    )


def build_unknown_device_result(
    metadata: AnalysisRequest,
    *,
    software_version: str = SOFTWARE_VERSION,
) -> AnalysisResult:
    """Build a schema-valid blocked response without loading an unknown device."""

    stages = [
        _stage(
            StageName.INPUT_VALIDATION,
            StageState.PASSED,
            "Metadata validated before device lookup.",
        ),
        _stage(
            StageName.DEVICE_CONFIGURATION_VALIDATION,
            StageState.FAILED,
            "The requested device version is not configured.",
            [ReasonCode.DEVICE_UNKNOWN],
        ),
        _stage(
            StageName.IMAGE_LOADING,
            StageState.BLOCKED,
            "Blocked because the device configuration is unknown.",
        ),
        _stage(
            StageName.CALIBRATION_VALIDATION,
            StageState.BLOCKED,
            "Blocked because the device configuration is unknown.",
        ),
        *_blocked_processing_stages(
            "Blocked because the device configuration is unknown."
        ),
        _stage(
            StageName.OUTCOME_POLICY,
            StageState.PASSED,
            "Unknown device blocked before any clinical decision.",
        ),
    ]
    return AnalysisResult(
        **_base_result_kwargs(
            metadata,
            software_version=software_version,
            device_configuration_hash=None,
            calibration_status=CalibrationStatus.MISSING,
            calibration_identifier=None,
            original_image_sha256=None,
            quality_measurements=QualityMeasurements(),
            status=ResultStatus.BLOCKED,
            reason_codes=[
                ReasonCode.DEVICE_UNKNOWN,
                ReasonCode.CLINICAL_OUTPUT_BLOCKED,
            ],
            message="The requested device is not configured; analysis is blocked.",
            stages=stages,
        )
    )


def analyze_capture(
    image_path: str | Path,
    metadata: AnalysisRequest,
    device_config: DeviceConfiguration,
    *,
    software_version: str = SOFTWARE_VERSION,
) -> AnalysisResult:
    """Run the Week 1 flow and return a schema-valid mock result."""

    if not isinstance(metadata, AnalysisRequest):
        metadata = AnalysisRequest.model_validate(metadata)

    device_hash = hash_device_configuration(device_config)
    if metadata.device_version != device_config.device_version:
        calibration = CalibrationValidation(
            status=CalibrationStatus.INVALID,
            calibration_identifier=None,
            device_configuration_hash=device_hash,
            compatible=False,
            reason_codes=[ReasonCode.DEVICE_CONFIGURATION_MISMATCH],
            message=(
                "Request device version does not match the supplied device "
                "configuration."
            ),
        )
        stages = [
            _stage(
                StageName.INPUT_VALIDATION,
                StageState.PASSED,
                "Metadata validated before device configuration validation.",
            ),
            _stage(
                StageName.DEVICE_CONFIGURATION_VALIDATION,
                StageState.FAILED,
                calibration.message,
                calibration.reason_codes,
            ),
            _stage(
                StageName.IMAGE_LOADING,
                StageState.BLOCKED,
                "Blocked because device configuration validation failed.",
            ),
            _stage(
                StageName.CALIBRATION_VALIDATION,
                StageState.BLOCKED,
                "Blocked because device configuration validation failed.",
            ),
            *_blocked_processing_stages(
                "Blocked because device configuration validation failed."
            ),
            _stage(
                StageName.OUTCOME_POLICY,
                StageState.PASSED,
                "Configuration mismatch blocked before any clinical decision.",
            ),
        ]
        return AnalysisResult(
            **_base_result_kwargs(
                metadata,
                software_version=software_version,
                device_configuration_hash=device_hash,
                calibration_status=CalibrationStatus.INVALID,
                calibration_identifier=None,
                original_image_sha256=None,
                quality_measurements=QualityMeasurements(),
                status=ResultStatus.BLOCKED,
                reason_codes=[
                    ReasonCode.DEVICE_CONFIGURATION_MISMATCH,
                    ReasonCode.CLINICAL_OUTPUT_BLOCKED,
                ],
                message=(
                    "Request device version is incompatible with the supplied "
                    "configuration; analysis is blocked."
                ),
                stages=stages,
            )
        )

    calibration = validate_calibration_package(device_config)
    try:
        loaded = load_image(image_path, _image_limits(device_config))
    except ImageLoadError as exc:
        return _result_for_image_error(
            metadata,
            software_version=software_version,
            device_configuration_hash=device_hash,
            calibration=calibration,
            error=exc,
        )

    decision = decide_mock_outcome(calibration)
    stages = [
        _stage(
            StageName.INPUT_VALIDATION,
            StageState.PASSED,
            "Metadata validated before analysis.",
        ),
        _stage(
            StageName.DEVICE_CONFIGURATION_VALIDATION,
            StageState.PASSED,
            "Device configuration matches the request.",
        ),
        _stage(
            StageName.IMAGE_LOADING,
            StageState.PASSED,
            "Original image bytes decoded successfully and were not modified.",
        ),
        _calibration_stage(calibration),
        *_unimplemented_stages(),
        _stage(
            StageName.OUTCOME_POLICY,
            StageState.PASSED,
            "Week 1 policy selected manual review for mock mode.",
            list(decision.reason_codes),
        ),
    ]
    return AnalysisResult(
        **_base_result_kwargs(
            metadata,
            software_version=software_version,
            device_configuration_hash=device_hash,
            calibration_status=calibration.status,
            calibration_identifier=calibration.calibration_identifier,
            original_image_sha256=loaded.original_sha256,
            quality_measurements=_quality_from_image(loaded),
            status=decision.status,
            reason_codes=list(decision.reason_codes),
            message=decision.message,
            stages=stages,
        )
    )
