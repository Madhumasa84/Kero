"""Shared MOCK and experimental pipeline orchestration."""

from __future__ import annotations

import base64
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import cv2

from . import SOFTWARE_VERSION
from .audit.hashing import hash_device_configuration
from .calibration.validation import validate_calibration_package
from .contracts import (
    AnalysisMode,
    AnalysisRequest,
    AnalysisResult,
    ArtifactReference,
    CalibrationStatus,
    CalibrationValidation,
    CentreInformation,
    CentreStatus,
    DeviceConfiguration,
    ExperimentalConfiguration,
    FeatureMeasurements,
    QualityMeasurements,
    ReasonCode,
    ResultStatus,
    RingTrackingInformation,
    RingTrackingStatus,
    StageExecution,
    StageName,
    StageState,
)
from .image_processing import (
    ExperimentalArtifacts,
    ImageLoadError,
    ImageLoadLimits,
    LoadedImage,
    assess_quality,
    detect_ring_candidates,
    estimate_centre,
    extract_geometric_features,
    load_image,
    render_experimental_artifacts,
    sample_polar,
    track_ring_candidates,
)
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
            StageName.POLAR_SAMPLING,
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
            StageName.POLAR_SAMPLING,
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
    processing_configuration_version: str | None = None,
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
        "processing_configuration_version": processing_configuration_version,
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
    experimental_configuration: ExperimentalConfiguration | None = None,
    include_overlays: bool = False,
) -> AnalysisResult:
    """Run MOCK or explicitly requested experimental image-space analysis."""

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

    if metadata.analysis_mode is AnalysisMode.EXPERIMENTAL:
        return _analyze_experimental_image(
            loaded,
            metadata,
            calibration,
            device_hash,
            software_version=software_version,
            configuration=experimental_configuration or ExperimentalConfiguration(),
            include_overlays=include_overlays,
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


def _artifact_reference(artifact_type: str, content: bytes) -> ArtifactReference:
    return ArtifactReference(
        artifact_type=artifact_type,
        media_type="image/png",
        data_base64=base64.b64encode(content).decode("ascii"),
        sha256=hashlib.sha256(content).hexdigest(),
        retained=False,
    )


def _experimental_stages(
    *,
    quality_state: StageState,
    quality_message: str,
    centre: CentreInformation,
    polar_state: StageState,
    polar_message: str,
    tracking: RingTrackingInformation,
    calibration_status: CalibrationStatus,
    feature_state: StageState,
    feature_message: str,
    outcome_reasons: list[ReasonCode],
) -> list[StageExecution]:
    if centre.status is CentreStatus.DETECTED:
        centre_stage = _stage(
            StageName.CENTRE_DETECTION,
            StageState.PASSED,
            "A candidate centre is supported by multiple circular edge bands; "
            "diagnostics are experimental.",
        )
    else:
        centre_stage = _stage(
            StageName.CENTRE_DETECTION,
            StageState.FAILED,
            "No reliable Placido-ring centre was found.",
            [centre.failure_reason or ReasonCode.CENTRE_NOT_FOUND],
        )
    tracking_state = (
        StageState.PASSED
        if tracking.status is RingTrackingStatus.TRACKED
        else (
            StageState.FAILED
            if tracking.status is RingTrackingStatus.FAILED
            else StageState.BLOCKED
        )
    )
    if calibration_status is CalibrationStatus.VALIDATED:
        calibration_state = StageState.PASSED
        calibration_message = (
            "Calibration status is recorded; image-space measurements "
            "remain experimental."
        )
    else:
        calibration_state = StageState.FAILED
        calibration_message = (
            "Physical calibration remains unvalidated; this does not calibrate "
            "pixel-space measurements."
        )
    if tracking_state is StageState.PASSED:
        tracking_message = (
            "Ordered radial candidates were tracked with missing angles "
            "preserved as null."
        )
    elif tracking_state is StageState.FAILED:
        tracking_message = (
            "Ring tracking did not meet the configured experimental "
            "progression criteria."
        )
    else:
        tracking_message = (
            "Blocked because a reliable centre or polar sample was unavailable."
        )
    return [
        _stage(StageName.INPUT_VALIDATION, StageState.PASSED, "Metadata validated."),
        _stage(
            StageName.DEVICE_CONFIGURATION_VALIDATION,
            StageState.PASSED,
            "Device configuration matches the request.",
        ),
        _stage(
            StageName.IMAGE_LOADING,
            StageState.PASSED,
            "Original image bytes were hashed and decoded without modification.",
        ),
        _stage(
            StageName.CALIBRATION_VALIDATION,
            calibration_state,
            calibration_message,
            [
                reason
                for reason in outcome_reasons
                if reason
                in {
                    ReasonCode.CALIBRATION_UNVALIDATED,
                    ReasonCode.CALIBRATION_MISSING,
                    ReasonCode.CALIBRATION_INVALID,
                }
            ],
        ),
        _stage(
            StageName.QUALITY_ASSESSMENT,
            quality_state,
            quality_message,
        ),
        centre_stage,
        _stage(
            StageName.SEGMENTATION,
            StageState.NOT_RUN,
            "The experimental path samples radial intensity profiles directly; "
            "a separate segmentation stage was not run.",
            [ReasonCode.STAGE_NOT_IMPLEMENTED],
        ),
        _stage(StageName.POLAR_SAMPLING, polar_state, polar_message),
        _stage(
            StageName.RING_TRACKING,
            tracking_state,
            tracking_message,
            tracking.failure_reasons,
        ),
        _stage(StageName.FEATURE_EXTRACTION, feature_state, feature_message),
        _stage(
            StageName.OUTCOME_POLICY,
            StageState.PASSED,
            "Automatic screening and referral recommendations are disabled; "
            "manual review is required.",
            [ReasonCode.CLINICAL_OUTPUT_BLOCKED],
        ),
    ]


def _analyze_experimental_image(
    loaded: LoadedImage,
    metadata: AnalysisRequest,
    calibration: CalibrationValidation,
    device_hash: str,
    *,
    software_version: str,
    configuration: ExperimentalConfiguration,
    include_overlays: bool,
) -> AnalysisResult:
    image = loaded.working_array
    quality = assess_quality(image, configuration).model_copy(
        update={
            "source_format": loaded.image_format,
            "orientation_transformation": loaded.orientation_transformation,
        }
    )
    centre = estimate_centre(image, configuration)
    polar = None
    candidates = None
    tracking = RingTrackingInformation()
    features = FeatureMeasurements()
    artifacts = ExperimentalArtifacts(b"", b"", b"")
    outcome_reasons = list(calibration.reason_codes)

    if centre.status is not CentreStatus.DETECTED:
        quality_stage_state = StageState.PASSED
        quality_message = (
            "Experimental blur, exposure and saturation statistics were "
            "calculated; they have no validated pass/fail thresholds."
        )
        polar_state = StageState.BLOCKED
        polar_message = "Blocked because reliable centre detection failed."
        feature_state = StageState.BLOCKED
        feature_message = (
            "Blocked because ring tracking depends on centre and polar sampling."
        )
        outcome_reasons.append(centre.failure_reason or ReasonCode.CENTRE_NOT_FOUND)
        message = (
            "Experimental analysis stopped because no reliable Placido-ring centre "
            "was found. Manual review is required."
        )
    else:
        quality_stage_state = StageState.PASSED
        quality_message = (
            "Experimental blur, exposure and saturation statistics were "
            "calculated; they have no validated pass/fail thresholds."
        )
        try:
            polar = sample_polar(image, centre, configuration)
            polar_state = StageState.PASSED
        except (ValueError, cv2.error) as exc:
            polar_state = StageState.FAILED
            polar_message = f"Polar sampling failed in a controlled way: {exc}"
            tracking = RingTrackingInformation(
                experimental=True,
                failure_reasons=[ReasonCode.POLAR_SAMPLING_FAILED],
            )
            feature_state = StageState.BLOCKED
            feature_message = "Blocked because polar sampling failed."
            outcome_reasons.append(ReasonCode.POLAR_SAMPLING_FAILED)
            message = (
                "Experimental image analysis failed at polar sampling. "
                "Manual review is required."
            )
        else:
            polar_message = (
                "Image intensities were sampled around the estimated centre."
            )
            try:
                candidates = detect_ring_candidates(polar, configuration)
                tracking = track_ring_candidates(candidates, configuration)
            except (ValueError, cv2.error):
                tracking = RingTrackingInformation(
                    status=RingTrackingStatus.FAILED,
                    experimental=True,
                    failure_reasons=[ReasonCode.RING_CANDIDATES_NOT_FOUND],
                )
                feature_state = StageState.BLOCKED
                feature_message = "Blocked because ring candidate processing failed."
                outcome_reasons.append(ReasonCode.RING_CANDIDATES_NOT_FOUND)
                message = (
                    "Experimental ring candidate processing failed. "
                    "Manual review is required."
                )
            if candidates is None:
                polar_state = StageState.PASSED
                polar_message = (
                    "Image intensities were sampled around the estimated centre."
                )
            else:
                quality = quality.model_copy(
                    update={
                        "visible_ring_coverage_fraction": (
                            tracking.angular_coverage_fraction
                        ),
                        "missing_sector_count": tracking.missing_sector_count,
                        "sector_count": tracking.sector_count,
                    }
                )
                if tracking.status is RingTrackingStatus.TRACKED:
                    features = extract_geometric_features(tracking)
                    feature_state = StageState.PASSED
                    feature_message = (
                        "Descriptive image-space geometry was calculated in pixels; "
                        "no physical calibration or disease score was applied."
                    )
                    message = (
                        "Experimental image-space analysis completed. Results require "
                        "manual review and are not calibrated or diagnostic."
                    )
                else:
                    feature_state = StageState.BLOCKED
                    feature_message = (
                        "Blocked because ordered ring tracking did not meet the "
                        "configured experimental progression criteria."
                    )
                    outcome_reasons.extend(tracking.failure_reasons)
                    message = (
                        "Centre and ring candidates were measured, but ordered "
                        "tracking did not meet configured experimental progression "
                        "criteria. "
                        "Manual review is required."
                    )

    if include_overlays and centre.status is CentreStatus.DETECTED:
        artifacts = render_experimental_artifacts(
            image, centre, polar, candidates, tracking
        )
    stages = _experimental_stages(
        quality_state=quality_stage_state,
        quality_message=quality_message,
        centre=centre,
        polar_state=polar_state,
        polar_message=polar_message,
        tracking=tracking,
        calibration_status=calibration.status,
        feature_state=feature_state,
        feature_message=feature_message,
        outcome_reasons=outcome_reasons,
    )
    artifact_references: list[ArtifactReference] = []
    if include_overlays and centre.status is CentreStatus.DETECTED:
        artifact_references.append(
            _artifact_reference("centre_overlay", artifacts.centre_overlay_png)
        )
        if candidates is not None:
            artifact_references.append(
                _artifact_reference(
                    "ring_candidate_overlay", artifacts.ring_candidate_overlay_png
                )
            )
        if polar is not None:
            artifact_references.append(
                _artifact_reference("polar_view", artifacts.polar_view_png)
            )
    unique_reasons = list(
        dict.fromkeys([*outcome_reasons, ReasonCode.CLINICAL_OUTPUT_BLOCKED])
    )
    result_kwargs = _base_result_kwargs(
        metadata,
        software_version=software_version,
        device_configuration_hash=device_hash,
        calibration_status=calibration.status,
        calibration_identifier=calibration.calibration_identifier,
        original_image_sha256=loaded.original_sha256,
        quality_measurements=quality,
        status=ResultStatus.MANUAL_REVIEW,
        reason_codes=unique_reasons,
        message=message,
        stages=stages,
        processing_configuration_version=configuration.configuration_version,
    )
    result_kwargs.update(
        centre_information=centre,
        ring_tracking=tracking,
        features=features,
        artifact_references=artifact_references,
    )
    return AnalysisResult(**result_kwargs)
