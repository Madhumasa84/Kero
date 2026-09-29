"""Uncalibrated, image-space measurements for the experimental pipeline.

Every numeric setting is an engineering parameter. Nothing in this module is
a validated capture rule or a clinical measurement.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from ..contracts import (
    CentreDiagnostics,
    CentreInformation,
    CentreStatus,
    ExperimentalConfiguration,
    FeatureMeasurements,
    FeatureStatus,
    MeasurementValidity,
    QualityMeasurements,
    QualityStatus,
    ReasonCode,
    RingTrack,
    RingTrackingInformation,
    RingTrackingStatus,
)


@dataclass(frozen=True)
class PolarSamples:
    """Grayscale polar samples and the matching image-space coordinates."""

    values: np.ndarray
    angles_deg: np.ndarray
    radii_px: np.ndarray
    valid: np.ndarray


@dataclass(frozen=True)
class RingCandidates:
    """Bright radial peaks, with an empty list retained for every missing angle."""

    angles_deg: list[float]
    radii_by_angle_px: list[list[float]]


@dataclass(frozen=True)
class ExperimentalArtifacts:
    """Rendered overlays, kept outside all analytical image inputs."""

    centre_overlay_png: bytes
    ring_candidate_overlay_png: bytes
    polar_view_png: bytes


def grayscale_u8(image: np.ndarray) -> np.ndarray:
    """Convert grayscale/BGR/BGRA input to an 8-bit analytical view."""

    if image.ndim == 2:
        gray = image
    elif image.ndim == 3 and image.shape[2] in {3, 4}:
        gray = cv2.cvtColor(image[:, :, :3], cv2.COLOR_BGR2GRAY)
    else:
        raise ValueError("image must have one, three or four channels")
    if gray.dtype == np.uint8:
        return gray
    if gray.dtype == np.uint16:
        return (gray / 257.0).round().astype(np.uint8)
    converted = np.nan_to_num(gray, nan=0.0, posinf=255.0, neginf=0.0)
    if converted.max(initial=0) <= 1.0:
        converted = converted * 255.0
    return np.clip(converted, 0, 255).astype(np.uint8)


def _ring_evidence(
    gray: np.ndarray, configuration: ExperimentalConfiguration
) -> np.ndarray:
    """Local bright ridges; suppress broad skin/sclera without a skin-colour rule."""
    width = configuration.ring_background_window_px | 1
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (width, width))
    return cv2.morphologyEx(gray, cv2.MORPH_TOPHAT, kernel)


def _analysis_scale(gray: np.ndarray, maximum_side: int) -> tuple[np.ndarray, float]:
    height, width = gray.shape
    scale = min(1.0, maximum_side / max(height, width))
    if scale == 1.0:
        return gray, 1.0
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    return cv2.resize(gray, size, interpolation=cv2.INTER_AREA), scale


def _circle_support(
    gradient: np.ndarray,
    centre_x: float,
    centre_y: float,
    radii: np.ndarray,
    configuration: ExperimentalConfiguration,
    threshold_value: float | None = None,
) -> tuple[list[float], list[float]]:
    angles = np.linspace(
        0.0,
        2.0 * np.pi,
        max(180, configuration.polar_angle_samples // 2),
        endpoint=False,
    )
    xx = centre_x + radii[:, None] * np.cos(angles)[None, :]
    yy = centre_y + radii[:, None] * np.sin(angles)[None, :]
    sampled = cv2.remap(
        gradient,
        xx.astype(np.float32),
        yy.astype(np.float32),
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    coverage = np.mean(
        sampled
        >= (
            configuration.edge_gradient_floor
            if threshold_value is None
            else threshold_value
        ),
        axis=1,
    )
    threshold = configuration.centre_min_ring_angular_coverage
    peaks = [
        index
        for index in range(1, len(radii) - 1)
        if coverage[index] >= threshold
        and coverage[index] >= coverage[index - 1]
        and coverage[index] >= coverage[index + 1]
    ]
    ranked = sorted(peaks, key=lambda index: coverage[index], reverse=True)
    selected: list[int] = []
    minimum_separation = max(4.0, configuration.polar_radial_step_px * 3.0)
    for index in ranked:
        if all(
            abs(radii[index] - radii[other]) >= minimum_separation for other in selected
        ):
            selected.append(index)
    selected.sort()
    return (
        [float(radii[index]) for index in selected],
        [float(coverage[index]) for index in selected],
    )


def estimate_centre(
    image: np.ndarray,
    configuration: ExperimentalConfiguration | None = None,
) -> CentreInformation:
    """Estimate a Placido-ring centre from radial gradient symmetry.

    A centre is returned only when multiple separated circular edge bands
    support the same candidate. The image midpoint is never used as fallback.
    """

    configuration = configuration or ExperimentalConfiguration()
    original_gray = grayscale_u8(image)
    gray, scale = _analysis_scale(original_gray, configuration.max_analysis_side_px)
    height, width = gray.shape
    minimum_dimension = float(min(height, width))
    min_radius = max(4.0, minimum_dimension * configuration.centre_radius_min_fraction)
    max_radius = minimum_dimension * configuration.centre_radius_max_fraction
    radius_step = max(
        1.5, minimum_dimension * configuration.centre_radius_step_fraction
    )
    radii = np.arange(min_radius, max_radius + radius_step, radius_step)
    evidence = _ring_evidence(gray, configuration)
    blurred = cv2.GaussianBlur(evidence, (5, 5), 1.0)
    dx = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
    dy = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)
    gradient = cv2.magnitude(dx, dy)
    edge_mask = gradient >= configuration.edge_gradient_floor
    ys, xs = np.nonzero(edge_mask)
    if len(xs) > 30_000:
        stride = int(np.ceil(len(xs) / 30_000))
        xs, ys = xs[::stride], ys[::stride]
    if len(xs) == 0 or len(radii) == 0:
        return CentreInformation(
            experimental=True,
            failure_reason=ReasonCode.CENTRE_NOT_FOUND,
            diagnostics=CentreDiagnostics(
                candidate_x_px=None,
                candidate_y_px=None,
                edge_point_count=0,
                peak_vote_count=0.0,
                supporting_edge_band_count=0,
                supporting_edge_radii_px=[],
                ring_angular_coverage=[],
                search_region_xyxy_px=[
                    0.0,
                    0.0,
                    float(image.shape[1]),
                    float(image.shape[0]),
                ],
            ),
        )

    magnitudes = gradient[ys, xs]
    unit_x = dx[ys, xs] / np.maximum(magnitudes, 1e-6)
    unit_y = dy[ys, xs] / np.maximum(magnitudes, 1e-6)
    weights = np.minimum(magnitudes, 1020.0) / 1020.0
    accumulator = np.zeros((height, width), dtype=np.float32)
    for radius in radii:
        for direction in (-1.0, 1.0):
            candidate_x = np.rint(xs + direction * unit_x * radius).astype(np.int32)
            candidate_y = np.rint(ys + direction * unit_y * radius).astype(np.int32)
            in_frame = (
                (candidate_x >= 0)
                & (candidate_x < width)
                & (candidate_y >= 0)
                & (candidate_y < height)
            )
            np.add.at(
                accumulator,
                (candidate_y[in_frame], candidate_x[in_frame]),
                weights[in_frame],
            )
    accumulator = cv2.GaussianBlur(accumulator, (0, 0), 2.0)

    candidate_indices: list[tuple[float, int, int]] = []
    search = accumulator.copy()
    suppression_radius = max(5, round(minimum_dimension * 0.025))
    for _ in range(configuration.centre_candidate_count):
        _, peak, _, location = cv2.minMaxLoc(search)
        peak_value = float(peak)
        x, y = map(int, location)
        if peak_value <= 0.0:
            break
        candidate_indices.append((peak_value, x, y))
        cv2.circle(search, (x, y), suppression_radius, 0.0, thickness=-1)

    best: tuple[float, int, float, int, int, list[float], list[float]] | None = None
    for votes, x, y in candidate_indices:
        supported_radii, coverages = _circle_support(
            gradient, x, y, radii, configuration
        )
        rank = (
            float(sum(value**2 for value in coverages)),
            len(supported_radii),
            votes,
        )
        if best is None or rank > (best[0], best[1], best[2]):
            best = (
                rank[0],
                rank[1],
                rank[2],
                x,
                y,
                supported_radii,
                coverages,
            )

    assert best is not None
    _, support_count, peak_votes, candidate_x, candidate_y, supported, coverages = best
    bright_radii, _ = _circle_support(
        evidence,
        candidate_x,
        candidate_y,
        np.arange(4.0, max_radius, 1.0),
        configuration,
        configuration.candidate_min_intensity,
    )
    original_x = candidate_x / scale
    original_y = candidate_y / scale
    search_radius = max_radius / scale
    diagnostics = CentreDiagnostics(
        candidate_x_px=float(original_x),
        candidate_y_px=float(original_y),
        edge_point_count=int(len(xs)),
        peak_vote_count=float(peak_votes),
        supporting_bright_ring_radii_px=[
            float(radius / scale) for radius in bright_radii
        ],
        supporting_edge_band_count=support_count,
        supporting_edge_radii_px=[float(radius / scale) for radius in supported],
        ring_angular_coverage=coverages,
        search_region_xyxy_px=[
            max(0.0, original_x - search_radius),
            max(0.0, original_y - search_radius),
            min(float(image.shape[1]), original_x + search_radius),
            min(float(image.shape[0]), original_y + search_radius),
        ],
    )
    if (
        support_count < configuration.centre_min_supporting_rings
        or len(bright_radii) < configuration.centre_min_supporting_rings
    ):
        return CentreInformation(
            experimental=True,
            diagnostics=diagnostics,
            failure_reason=ReasonCode.CENTRE_UNRELIABLE,
        )
    return CentreInformation(
        status=CentreStatus.DETECTED,
        x_px=float(original_x),
        y_px=float(original_y),
        source="gradient_radial_symmetry_v1",
        experimental=True,
        diagnostics=diagnostics,
    )


def assess_quality(
    image: np.ndarray,
    configuration: ExperimentalConfiguration | None = None,
) -> QualityMeasurements:
    """Calculate descriptive image statistics without pass/fail thresholds."""

    configuration = configuration or ExperimentalConfiguration()
    gray = grayscale_u8(image)
    measured, _ = _analysis_scale(gray, configuration.max_analysis_side_px)
    laplacian_variance = float(cv2.Laplacian(measured, cv2.CV_64F).var())
    heights, widths = image.shape[:2]
    channel_count = 1 if image.ndim == 2 else int(image.shape[2])
    sector_count = configuration.quality_sector_count
    return QualityMeasurements(
        status=QualityStatus.MEASURED,
        experimental=True,
        image_width_px=int(widths),
        image_height_px=int(heights),
        channel_count=channel_count,
        brightness_mean=float(np.mean(measured)),
        contrast_stddev=float(np.std(measured)),
        blur_laplacian_variance=laplacian_variance,
        underexposed_pixel_fraction=float(
            np.mean(measured <= configuration.quality_dark_pixel_threshold)
        ),
        saturated_pixel_fraction=float(
            np.mean(measured >= configuration.quality_saturated_pixel_threshold)
        ),
        sector_count=sector_count,
        validity=MeasurementValidity.MEASURED,
    )


def sample_polar(
    image: np.ndarray,
    centre: CentreInformation,
    configuration: ExperimentalConfiguration | None = None,
) -> PolarSamples:
    """Sample image intensities along rays around a detected centre."""

    configuration = configuration or ExperimentalConfiguration()
    if (
        centre.status is not CentreStatus.DETECTED
        or centre.x_px is None
        or centre.y_px is None
    ):
        raise ValueError("polar sampling requires a detected centre")
    gray = _ring_evidence(grayscale_u8(image), configuration)
    maximum_radius = min(gray.shape) * configuration.polar_max_radius_fraction
    if centre.diagnostics and centre.diagnostics.supporting_bright_ring_radii_px:
        maximum_radius = min(
            maximum_radius,
            max(centre.diagnostics.supporting_bright_ring_radii_px)
            + configuration.candidate_min_spacing_px,
        )
    radii = np.arange(
        configuration.polar_min_radius_px,
        maximum_radius + configuration.polar_radial_step_px,
        configuration.polar_radial_step_px,
        dtype=np.float32,
    )
    angles = np.linspace(
        0.0,
        360.0,
        configuration.polar_angle_samples,
        endpoint=False,
        dtype=np.float32,
    )
    radians = np.deg2rad(angles)
    map_x = centre.x_px + np.cos(radians)[:, None] * radii[None, :]
    map_y = centre.y_px + np.sin(radians)[:, None] * radii[None, :]
    valid = (
        (map_x >= 0)
        & (map_x <= gray.shape[1] - 1)
        & (map_y >= 0)
        & (map_y <= gray.shape[0] - 1)
    )
    values = cv2.remap(
        gray,
        map_x.astype(np.float32),
        map_y.astype(np.float32),
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=0,
    )
    return PolarSamples(values=values, angles_deg=angles, radii_px=radii, valid=valid)


def detect_ring_candidates(
    polar: PolarSamples,
    configuration: ExperimentalConfiguration | None = None,
) -> RingCandidates:
    """Find local bright radial peaks and preserve empty/missing angular rows."""

    configuration = configuration or ExperimentalConfiguration()
    smoothing_width = max(3, round(configuration.candidate_min_spacing_px))
    if smoothing_width % 2 == 0:
        smoothing_width += 1
    prominence_window = configuration.candidate_prominence_window_px
    candidates: list[list[float]] = []
    for angle_index, profile in enumerate(polar.values):
        smoothed = cv2.GaussianBlur(
            profile.reshape(1, -1).astype(np.float32),
            (smoothing_width, 1),
            0,
        )[0]
        valid = polar.valid[angle_index]
        peaks: list[tuple[float, float]] = []
        for index in range(1, len(smoothed) - 1):
            value = float(smoothed[index])
            if (
                not valid[index]
                or value < configuration.candidate_min_intensity
                or value < smoothed[index - 1]
                or value < smoothed[index + 1]
            ):
                continue
            left_start = max(0, index - prominence_window)
            right_end = min(len(smoothed), index + prominence_window + 1)
            left_min = float(np.min(smoothed[left_start:index]))
            right_min = float(np.min(smoothed[index + 1 : right_end]))
            prominence = value - max(left_min, right_min)
            if prominence >= configuration.candidate_min_prominence:
                peaks.append((float(polar.radii_px[index]), value))
        selected: list[tuple[float, float]] = []
        for radius, value in sorted(peaks, key=lambda item: item[1], reverse=True):
            if all(
                abs(radius - other_radius) >= configuration.candidate_min_spacing_px
                for other_radius, _ in selected
            ):
                selected.append((radius, value))
        candidates.append(sorted(radius for radius, _ in selected))
    return RingCandidates(
        angles_deg=[float(angle) for angle in polar.angles_deg],
        radii_by_angle_px=candidates,
    )


@dataclass
class _MutableTrack:
    radii: list[float | None]
    last_index: int
    last_radius: float


def _monotone_matches(
    track_radii: list[float], candidate_radii: list[float], max_step: float
) -> list[tuple[int, int]]:
    """Minimum-cost order-preserving partial match between two radial rows."""

    rows, columns = len(track_radii), len(candidate_radii)
    skip_cost = 0.8
    costs = np.full((rows + 1, columns + 1), np.inf, dtype=np.float64)
    previous: dict[tuple[int, int], tuple[int, int]] = {}
    costs[0, 0] = 0.0
    for row in range(rows + 1):
        for column in range(columns + 1):
            current = costs[row, column]
            if not np.isfinite(current):
                continue
            options: list[tuple[int, int, float]] = []
            if row < rows:
                options.append((row + 1, column, skip_cost))
            if column < columns:
                options.append((row, column + 1, skip_cost))
            if row < rows and column < columns:
                difference = abs(track_radii[row] - candidate_radii[column])
                if difference <= max_step:
                    options.append((row + 1, column + 1, 0.5 * difference / max_step))
            for next_row, next_column, step_cost in options:
                new_cost = current + step_cost
                if new_cost < costs[next_row, next_column]:
                    costs[next_row, next_column] = new_cost
                    previous[(next_row, next_column)] = (row, column)
    matches: list[tuple[int, int]] = []
    cursor = (rows, columns)
    while cursor != (0, 0):
        prior = previous.get(cursor)
        if prior is None:
            break
        row, column = prior
        if row < rows and column < columns and cursor == (row + 1, column + 1):
            if abs(track_radii[row] - candidate_radii[column]) <= max_step:
                matches.append((row, column))
        cursor = prior
    return list(reversed(matches))


def _ring_track_model(radii: list[float | None], index: int) -> RingTrack:
    observed = [radius for radius in radii if radius is not None]
    valid = [radius is not None for radius in radii]
    if not observed:
        raise ValueError("a ring track must contain at least one observation")
    centre_asymmetries: list[float] = []
    sample_count = len(radii)
    half = sample_count // 2
    for angle_index in range(half):
        opposite_index = angle_index + half
        first, opposite = radii[angle_index], radii[opposite_index]
        if first is not None and opposite is not None:
            centre_asymmetries.append(abs(first - opposite))
    return RingTrack(
        ordered_index=index,
        mean_radius_px=float(np.mean(observed)),
        radius_range_px=float(max(observed) - min(observed)),
        radius_asymmetry_px=float(
            np.mean(centre_asymmetries) if centre_asymmetries else 0.0
        ),
        coverage_fraction=float(np.mean(valid)),
        radii_px=radii,
        validity_mask=valid,
    )


def _missing_sector_count(
    candidates: RingCandidates,
    sector_count: int,
    minimum_detection_fraction: float,
) -> int:
    sample_count = len(candidates.radii_by_angle_px)
    missing = 0
    for sector in range(sector_count):
        start = round(sector * sample_count / sector_count)
        end = round((sector + 1) * sample_count / sector_count)
        rows = candidates.radii_by_angle_px[start:end]
        fraction = sum(bool(row) for row in rows) / max(1, len(rows))
        if fraction < minimum_detection_fraction:
            missing += 1
    return missing


def track_ring_candidates(
    candidates: RingCandidates,
    configuration: ExperimentalConfiguration | None = None,
) -> RingTrackingInformation:
    """Match peaks in radial order while leaving every missed angle as null."""

    configuration = configuration or ExperimentalConfiguration()
    sample_count = len(candidates.angles_deg)
    if sample_count == 0 or len(candidates.radii_by_angle_px) != sample_count:
        return RingTrackingInformation(
            status=RingTrackingStatus.FAILED,
            experimental=True,
            failure_reasons=[ReasonCode.RING_CANDIDATES_NOT_FOUND],
        )
    mutable_tracks: list[_MutableTrack] = []
    for angle_index, row in enumerate(candidates.radii_by_angle_px):
        active = [
            index
            for index, track in enumerate(mutable_tracks)
            if angle_index - track.last_index <= configuration.tracking_max_gap_samples
        ]
        active.sort(key=lambda index: mutable_tracks[index].last_radius)
        active_radii = [mutable_tracks[index].last_radius for index in active]
        candidate_radii = sorted(row)
        matches = _monotone_matches(
            active_radii,
            candidate_radii,
            configuration.tracking_max_radius_step_px,
        )
        matched_candidates: set[int] = set()
        for track_position, candidate_position in matches:
            track = mutable_tracks[active[track_position]]
            radius = candidate_radii[candidate_position]
            track.radii[angle_index] = radius
            track.last_index = angle_index
            track.last_radius = radius
            matched_candidates.add(candidate_position)
        for candidate_position, radius in enumerate(candidate_radii):
            if candidate_position in matched_candidates:
                continue
            radii: list[float | None] = [None] * sample_count
            radii[angle_index] = radius
            mutable_tracks.append(
                _MutableTrack(radii=radii, last_index=angle_index, last_radius=radius)
            )

    tracks = [
        track.radii
        for track in mutable_tracks
        if sum(radius is not None for radius in track.radii)
        >= max(
            configuration.tracking_min_observations,
            int(np.ceil(sample_count * configuration.tracking_min_coverage_fraction)),
        )
    ]
    ring_models = sorted(
        (_ring_track_model(radii, 1) for radii in tracks),
        key=lambda ring: ring.mean_radius_px,
    )
    ring_models = [
        ring.model_copy(update={"ordered_index": index})
        for index, ring in enumerate(ring_models, start=1)
    ]
    angle_coverage = float(
        sum(bool(row) for row in candidates.radii_by_angle_px) / sample_count
    )
    sector_count = configuration.quality_sector_count
    missing_sectors = _missing_sector_count(
        candidates,
        sector_count,
        configuration.sector_min_detection_fraction,
    )
    enough_rings = (
        len(ring_models) >= configuration.tracking_min_ring_count_for_features
    )
    enough_coverage = angle_coverage >= configuration.tracking_min_coverage_fraction
    failure_reasons: list[ReasonCode] = []
    if not any(candidates.radii_by_angle_px):
        failure_reasons.append(ReasonCode.RING_CANDIDATES_NOT_FOUND)
    if not enough_rings or not enough_coverage:
        failure_reasons.append(ReasonCode.RING_TRACKING_INSUFFICIENT)
    return RingTrackingInformation(
        status=(
            RingTrackingStatus.TRACKED
            if not failure_reasons
            else RingTrackingStatus.FAILED
        ),
        experimental=True,
        tracked_ring_count=len(ring_models) or None,
        angle_samples_deg=candidates.angles_deg,
        candidate_radii_by_angle_px=candidates.radii_by_angle_px,
        rings=ring_models,
        angular_coverage_fraction=angle_coverage,
        missing_sector_count=missing_sectors,
        sector_count=sector_count,
        failure_reasons=failure_reasons,
        validity=MeasurementValidity.MEASURED,
    )


def extract_geometric_features(
    tracking: RingTrackingInformation,
) -> FeatureMeasurements:
    """Return descriptive pixel-space geometry; no physical units are inferred."""

    if tracking.status is not RingTrackingStatus.TRACKED or not tracking.rings:
        return FeatureMeasurements()
    spacings = [
        right.mean_radius_px - left.mean_radius_px
        for left, right in zip(tracking.rings, tracking.rings[1:], strict=False)
    ]
    asymmetries = [ring.radius_asymmetry_px for ring in tracking.rings]
    return FeatureMeasurements(
        status=FeatureStatus.EXTRACTED,
        experimental=True,
        measurement_unit="px",
        mean_ring_spacing_px=float(np.mean(spacings)) if spacings else None,
        ring_spacing_stddev_px=float(np.std(spacings)) if spacings else None,
        mean_radial_asymmetry_px=float(np.mean(asymmetries)) if asymmetries else None,
        angular_coverage_fraction=tracking.angular_coverage_fraction,
        missing_sector_count=tracking.missing_sector_count,
        validity=MeasurementValidity.MEASURED,
    )


def _encode_png(image: np.ndarray) -> bytes:
    success, encoded = cv2.imencode(".png", image)
    if not success:
        raise ValueError("could not encode experimental overlay")
    return encoded.tobytes()


def render_experimental_artifacts(
    image: np.ndarray,
    centre: CentreInformation,
    polar: PolarSamples | None,
    candidates: RingCandidates | None,
    tracking: RingTrackingInformation,
) -> ExperimentalArtifacts:
    """Render display-only overlays from analysis outputs and the source image."""

    if image.ndim == 2:
        base = cv2.cvtColor(grayscale_u8(image), cv2.COLOR_GRAY2BGR)
    else:
        base = np.ascontiguousarray(image[:, :, :3]).copy()
    centre_view = base.copy()
    ring_view = base.copy()
    if (
        centre.status is CentreStatus.DETECTED
        and centre.x_px is not None
        and centre.y_px is not None
    ):
        point = (round(centre.x_px), round(centre.y_px))
        cv2.drawMarker(
            centre_view,
            point,
            (0, 255, 255),
            markerType=cv2.MARKER_CROSS,
            markerSize=22,
            thickness=2,
        )
        cv2.circle(centre_view, point, 8, (0, 255, 255), 2, cv2.LINE_AA)
        cv2.drawMarker(
            ring_view,
            point,
            (0, 255, 255),
            markerType=cv2.MARKER_CROSS,
            markerSize=18,
            thickness=2,
        )
    if candidates is not None and centre.x_px is not None and centre.y_px is not None:
        for angle, radii in zip(
            candidates.angles_deg, candidates.radii_by_angle_px, strict=True
        ):
            radians = np.deg2rad(angle)
            for radius in radii:
                x = round(centre.x_px + radius * np.cos(radians))
                y = round(centre.y_px + radius * np.sin(radians))
                if 0 <= x < ring_view.shape[1] and 0 <= y < ring_view.shape[0]:
                    cv2.circle(ring_view, (x, y), 1, (255, 100, 0), -1)
    for ring_number, ring in enumerate(tracking.rings):
        color = (
            int((53 * (ring_number + 1)) % 255),
            int((137 * (ring_number + 2)) % 255),
            int((211 * (ring_number + 3)) % 255),
        )
        coordinates: list[tuple[int, int] | None] = []
        if centre.x_px is not None and centre.y_px is not None:
            for angle, radius in zip(
                tracking.angle_samples_deg or [], ring.radii_px, strict=True
            ):
                if radius is None:
                    coordinates.append(None)
                    continue
                radians = np.deg2rad(angle)
                coordinates.append(
                    (
                        round(centre.x_px + radius * np.cos(radians)),
                        round(centre.y_px + radius * np.sin(radians)),
                    )
                )
        for index, point in enumerate(coordinates):
            next_index = (index + 1) % len(coordinates) if coordinates else 0
            next_point = coordinates[next_index] if coordinates else None
            if point is not None and next_point is not None:
                cv2.line(ring_view, point, next_point, color, 1, cv2.LINE_AA)
    polar_view = (
        np.zeros((64, 64), dtype=np.uint8)
        if polar is None
        else cv2.normalize(polar.values, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
    )
    if polar is not None and tracking.rings:
        polar_view = cv2.cvtColor(polar_view, cv2.COLOR_GRAY2BGR)
        for ring in tracking.rings:
            for angle_index, radius in enumerate(ring.radii_px):
                if radius is None:
                    continue
                radial_step = float(polar.radii_px[1] - polar.radii_px[0])
                radial_index = round((radius - float(polar.radii_px[0])) / radial_step)
                if 0 <= radial_index < polar_view.shape[1]:
                    cv2.circle(
                        polar_view, (radial_index, angle_index), 1, (0, 255, 0), -1
                    )
    elif polar is not None:
        polar_view = cv2.cvtColor(polar_view, cv2.COLOR_GRAY2BGR)
    return ExperimentalArtifacts(
        centre_overlay_png=_encode_png(centre_view),
        ring_candidate_overlay_png=_encode_png(ring_view),
        polar_view_png=_encode_png(polar_view),
    )
