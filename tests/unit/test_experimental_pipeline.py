from __future__ import annotations

import hashlib

import cv2
import numpy as np

from corneal_screening.contracts import (
    AnalysisMode,
    CentreStatus,
    ExperimentalConfiguration,
    FeatureStatus,
    ReasonCode,
    ResultStatus,
    RingTrackingStatus,
    StageName,
    StageState,
)
from corneal_screening.image_processing import (
    RingCandidates,
    assess_quality,
    detect_ring_candidates,
    estimate_centre,
    extract_geometric_features,
    sample_polar,
    track_ring_candidates,
)
from corneal_screening.pipeline import analyze_capture

GROUND_TRUTH_CENTRE = (173, 204)
SYNTHETIC_RING_RADII = (35, 55, 75, 95, 115, 135)


def make_ring_image(
    centre: tuple[int, int] = GROUND_TRUTH_CENTRE,
    *,
    obstructed_sector: tuple[float, float] | None = None,
) -> np.ndarray:
    image = np.zeros((384, 384, 3), dtype=np.uint8)
    for radius in SYNTHETIC_RING_RADII:
        cv2.circle(image, centre, radius, (220, 220, 220), 2, cv2.LINE_AA)
    if obstructed_sector is not None:
        start, end = obstructed_sector
        angles = np.linspace(np.deg2rad(start), np.deg2rad(end), 24)
        points = [centre]
        points.extend(
            (
                round(centre[0] + 190 * np.cos(angle)),
                round(centre[1] + 190 * np.sin(angle)),
            )
            for angle in angles
        )
        cv2.fillPoly(image, [np.asarray(points, dtype=np.int32)], (0, 0, 0))
    return image


def test_centre_error_is_within_synthetic_tolerance():
    image = make_ring_image()

    centre = estimate_centre(image)

    assert centre.status is CentreStatus.DETECTED
    assert centre.x_px is not None and centre.y_px is not None
    error_px = float(
        np.hypot(
            centre.x_px - GROUND_TRUTH_CENTRE[0],
            centre.y_px - GROUND_TRUTH_CENTRE[1],
        )
    )
    assert error_px <= 2.0
    assert centre.diagnostics is not None
    assert centre.diagnostics.supporting_edge_band_count >= 2


def test_uniform_image_does_not_fall_back_to_image_midpoint():
    image = np.full((384, 384, 3), 90, dtype=np.uint8)

    centre = estimate_centre(image)

    assert centre.status is CentreStatus.NOT_DETECTED
    assert centre.x_px is None
    assert centre.y_px is None
    assert centre.failure_reason is ReasonCode.CENTRE_NOT_FOUND


def test_quality_values_are_experimental_statistics_without_decision():
    image = make_ring_image()

    quality = assess_quality(image)

    assert quality.experimental is True
    assert quality.blur_laplacian_variance is not None
    assert 0.0 <= quality.underexposed_pixel_fraction <= 1.0
    assert 0.0 <= quality.saturated_pixel_fraction <= 1.0
    assert quality.visible_ring_coverage_fraction is None


def test_polar_candidates_keep_missing_angles_and_ring_tracks_keep_nulls():
    image = make_ring_image(obstructed_sector=(25, 70))
    centre = estimate_centre(image)
    assert centre.status is CentreStatus.DETECTED

    polar = sample_polar(image, centre)
    candidates = detect_ring_candidates(polar)
    tracking = track_ring_candidates(candidates)

    assert len(candidates.radii_by_angle_px) == 360
    assert any(
        not angle_candidates for angle_candidates in candidates.radii_by_angle_px
    )
    assert tracking.missing_sector_count is not None
    assert tracking.missing_sector_count > 0
    assert tracking.status is RingTrackingStatus.TRACKED
    assert tracking.rings
    assert all(len(ring.radii_px) == 360 for ring in tracking.rings)
    assert any(radius is None for ring in tracking.rings for radius in ring.radii_px)
    assert all(
        valid == (radius is not None)
        for ring in tracking.rings
        for valid, radius in zip(ring.validity_mask, ring.radii_px, strict=True)
    )


def test_ordered_ring_tracking_extracts_only_pixel_features():
    image = make_ring_image()
    centre = estimate_centre(image)
    polar = sample_polar(image, centre)
    candidates = detect_ring_candidates(polar)
    tracking = track_ring_candidates(candidates)

    features = extract_geometric_features(tracking)

    assert tracking.status is RingTrackingStatus.TRACKED
    assert [ring.mean_radius_px for ring in tracking.rings] == sorted(
        ring.mean_radius_px for ring in tracking.rings
    )
    assert features.status is FeatureStatus.EXTRACTED
    assert features.measurement_unit == "px"
    assert features.mean_ring_spacing_px == 20.0
    assert features.sim_k1_diopters is None
    assert features.sim_k2_diopters is None


def test_experimental_pipeline_returns_reviewable_result_and_opt_in_overlays(
    tmp_path, metadata, device_config
):
    image = make_ring_image()
    path = tmp_path / "synthetic_placido.png"
    success, encoded = cv2.imencode(".png", image)
    assert success
    original_bytes = encoded.tobytes()
    path.write_bytes(original_bytes)
    experimental_metadata = metadata.model_copy(
        update={"analysis_mode": AnalysisMode.EXPERIMENTAL}
    )

    result = analyze_capture(path, experimental_metadata, device_config)
    result_with_overlays = analyze_capture(
        path,
        experimental_metadata,
        device_config,
        include_overlays=True,
    )

    assert result.status is ResultStatus.MANUAL_REVIEW
    assert result.analysis_mode is AnalysisMode.EXPERIMENTAL
    assert result.calibration_status.value == "UNVALIDATED"
    assert result.processing_configuration_version == "experimental-v1.1.0"
    assert result.original_image_sha256 == hashlib.sha256(original_bytes).hexdigest()
    assert path.read_bytes() == original_bytes
    assert result.artifact_references == []
    stages = {stage.stage_name: stage for stage in result.stage_execution}
    assert stages[StageName.CENTRE_DETECTION].state is StageState.PASSED
    assert stages[StageName.POLAR_SAMPLING].state is StageState.PASSED
    assert stages[StageName.RING_TRACKING].state is StageState.PASSED
    assert stages[StageName.FEATURE_EXTRACTION].state is StageState.PASSED
    assert result_with_overlays.status is ResultStatus.MANUAL_REVIEW
    assert {
        item.artifact_type for item in result_with_overlays.artifact_references
    } == {
        "centre_overlay",
        "ring_candidate_overlay",
        "polar_view",
    }
    assert all(
        item.data_base64 and item.retained is False
        for item in result_with_overlays.artifact_references
    )


def test_experimental_pipeline_reports_centre_failure_and_blocks_dependents(
    tmp_path, metadata, device_config
):
    image = np.full((384, 384, 3), 90, dtype=np.uint8)
    path = tmp_path / "synthetic_no_rings.png"
    success, encoded = cv2.imencode(".png", image)
    assert success
    path.write_bytes(encoded.tobytes())
    experimental_metadata = metadata.model_copy(
        update={"analysis_mode": AnalysisMode.EXPERIMENTAL}
    )

    result = analyze_capture(path, experimental_metadata, device_config)

    stages = {stage.stage_name: stage for stage in result.stage_execution}
    assert result.status is ResultStatus.MANUAL_REVIEW
    assert ReasonCode.CENTRE_NOT_FOUND in result.reason_codes
    assert stages[StageName.CENTRE_DETECTION].state is StageState.FAILED
    assert stages[StageName.POLAR_SAMPLING].state is StageState.BLOCKED
    assert stages[StageName.RING_TRACKING].state is StageState.BLOCKED
    assert stages[StageName.FEATURE_EXTRACTION].state is StageState.BLOCKED
    assert result.centre_information.x_px is None
    assert result.features.status is FeatureStatus.NOT_RUN


def test_polar_sampling_error_is_controlled_and_blocks_tracking(
    tmp_path, metadata, device_config, monkeypatch
):
    image = make_ring_image()
    path = tmp_path / "synthetic_polar_failure.png"
    success, encoded = cv2.imencode(".png", image)
    assert success
    path.write_bytes(encoded.tobytes())
    experimental_metadata = metadata.model_copy(
        update={"analysis_mode": AnalysisMode.EXPERIMENTAL}
    )

    def fail_sampling(*_args, **_kwargs):
        raise ValueError("synthetic sampler failure")

    monkeypatch.setattr("corneal_screening.pipeline.sample_polar", fail_sampling)

    result = analyze_capture(path, experimental_metadata, device_config)

    stages = {stage.stage_name: stage for stage in result.stage_execution}
    assert result.status is ResultStatus.MANUAL_REVIEW
    assert ReasonCode.POLAR_SAMPLING_FAILED in result.reason_codes
    assert stages[StageName.POLAR_SAMPLING].state is StageState.FAILED
    assert stages[StageName.RING_TRACKING].state is StageState.BLOCKED
    assert stages[StageName.FEATURE_EXTRACTION].state is StageState.BLOCKED


def test_no_ring_candidates_report_tracking_failure_and_missing_sectors():
    candidates = RingCandidates(
        angles_deg=[float(index) for index in range(36)],
        radii_by_angle_px=[[] for _ in range(36)],
    )

    tracking = track_ring_candidates(candidates)

    assert tracking.status is RingTrackingStatus.FAILED
    assert tracking.angular_coverage_fraction == 0.0
    assert tracking.missing_sector_count == 36
    assert tracking.validity.value == "MEASURED"
    assert ReasonCode.RING_CANDIDATES_NOT_FOUND in tracking.failure_reasons
    assert ReasonCode.RING_TRACKING_INSUFFICIENT in tracking.failure_reasons


def test_missing_candidate_rows_can_be_serialized_as_json_nulls():
    candidates = RingCandidates(
        angles_deg=[0.0, 90.0, 180.0, 270.0],
        radii_by_angle_px=[[20.0, 40.0], [], [20.0, 40.0], []],
    )
    configuration = ExperimentalConfiguration(
        polar_angle_samples=36,
        tracking_min_observations=1,
        tracking_min_coverage_fraction=0.4,
        tracking_min_ring_count_for_features=2,
    )

    tracking = track_ring_candidates(candidates, configuration)
    encoded = __import__("json").dumps(
        tracking.model_dump(mode="json"), allow_nan=False
    )

    assert tracking.rings
    assert "null" in encoded
    assert any(value is None for ring in tracking.rings for value in ring.radii_px)
