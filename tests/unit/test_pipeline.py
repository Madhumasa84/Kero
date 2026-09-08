from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from pydantic import ValidationError

from corneal_screening.contracts import (
    CalibrationStatus,
    QualityMeasurements,
    ReasonCode,
    ResultStatus,
    StageName,
    StageState,
)
from corneal_screening.pipeline import analyze_capture


def test_valid_capture_returns_explicit_mock_result(
    valid_jpeg_path: Path, metadata, device_config
):
    before = valid_jpeg_path.read_bytes()
    result = analyze_capture(valid_jpeg_path, metadata, device_config)

    assert result.status is ResultStatus.MANUAL_REVIEW
    assert result.analysis_mode.value == "MOCK"
    assert "Mock result: image analysis has not been performed." in result.message
    assert result.calibration_status is CalibrationStatus.UNVALIDATED
    assert result.original_image_sha256
    assert result.quality_measurements.image_width_px == 16
    assert result.quality_measurements.image_height_px == 12
    assert result.centre_information.x_px is None
    assert result.ring_tracking.ring_count is None
    assert result.features.sim_k1_diopters is None
    assert valid_jpeg_path.read_bytes() == before

    stages = {stage.stage_name: stage for stage in result.stage_execution}
    assert stages[StageName.QUALITY_ASSESSMENT].state is StageState.NOT_RUN
    assert stages[StageName.CENTRE_DETECTION].state is StageState.NOT_RUN
    assert stages[StageName.SEGMENTATION].state is StageState.NOT_RUN
    assert stages[StageName.RING_TRACKING].state is StageState.NOT_RUN
    assert stages[StageName.FEATURE_EXTRACTION].state is StageState.NOT_RUN
    assert all(
        stage.state is not StageState.PASSED
        for stage in result.stage_execution
        if stage.stage_name
        in {
            StageName.QUALITY_ASSESSMENT,
            StageName.CENTRE_DETECTION,
            StageName.SEGMENTATION,
            StageName.RING_TRACKING,
            StageName.FEATURE_EXTRACTION,
        }
    )


def test_unreadable_capture_returns_recapture_result(tmp_path, metadata, device_config):
    path = tmp_path / "broken.jpg"
    path.write_bytes(b"broken")

    result = analyze_capture(path, metadata, device_config)

    assert result.status is ResultStatus.RECAPTURE_REQUIRED
    assert ReasonCode.IMAGE_CORRUPT in result.reason_codes
    assert "Recapture" in result.message
    image_stage = next(
        stage
        for stage in result.stage_execution
        if stage.stage_name is StageName.IMAGE_LOADING
    )
    assert image_stage.state is StageState.FAILED


def test_missing_calibration_cannot_produce_negative_screening(
    valid_png_path, metadata, device_config, tmp_path
):
    missing_config = device_config.model_copy(
        update={"calibration_package_path": str(tmp_path / "absent")}
    )

    result = analyze_capture(valid_png_path, metadata, missing_config)

    assert result.status is ResultStatus.MANUAL_REVIEW
    assert result.status is not ResultStatus.SCREEN_NEGATIVE
    assert result.calibration_status is CalibrationStatus.MISSING


def test_configuration_flag_is_not_part_of_pipeline_decision(
    valid_png_path, metadata, device_config
):
    result = analyze_capture(valid_png_path, metadata, device_config)
    assert result.status is ResultStatus.MANUAL_REVIEW


def test_result_serialization_is_strict_json(valid_png_path, metadata, device_config):
    result = analyze_capture(valid_png_path, metadata, device_config)
    encoded = result.to_json()
    decoded = json.loads(encoded)

    json.dumps(decoded, allow_nan=False)
    assert "NaN" not in encoded
    assert "Infinity" not in encoded
    assert decoded["quality_measurements"]["brightness_mean"] is None


def test_numeric_contract_rejects_nan_and_infinity():
    with pytest.raises(ValidationError):
        QualityMeasurements(brightness_mean=math.nan)
    with pytest.raises(ValidationError):
        QualityMeasurements(contrast_stddev=math.inf)
