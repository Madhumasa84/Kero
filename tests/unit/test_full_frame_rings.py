"""Synthetic full-frame regression cases, not real-device validation."""

import cv2
import numpy as np
import pytest

from corneal_screening.contracts import CentreStatus, RingTrackingStatus
from corneal_screening.image_processing import (
    detect_ring_candidates,
    estimate_centre,
    sample_polar,
    track_ring_candidates,
)


def make_full_frame(skin=(100, 145, 185), rings=True):
    rng = np.random.default_rng(42)
    im = np.clip(
        np.full((640, 640, 3), skin) + rng.normal(0, 7, (640, 640, 1)), 0, 255
    ).astype("uint8")
    c = (285, 340)
    cv2.ellipse(im, c, (180, 115), 0, 0, 360, (165, 175, 180), -1)
    cv2.circle(im, c, 102, (35, 50, 60), -1)
    cv2.circle(im, c, 23, (8, 8, 8), -1)
    if rings:
        for r in (30, 44, 58, 72, 86):
            cv2.circle(im, c, r, (240, 240, 240), 2, cv2.LINE_AA)
    cv2.rectangle(im, (470, 90), (560, 180), (245, 245, 245), -1)
    return im, c


@pytest.mark.parametrize("skin", [(100, 145, 185), (35, 55, 75), (180, 200, 220)])
@pytest.mark.parametrize("factor", [0.35, 0.5, 0.75, 1.0])
def test_white_rings_in_square_frame_with_surrounding_skin(skin, factor):
    original, centre = make_full_frame(skin)
    small = cv2.resize(original, None, fx=factor, fy=factor)
    image = np.full((900, 900, 3), skin, dtype=np.uint8)
    image[180 : 180 + small.shape[0], 90 : 90 + small.shape[1]] = small
    # OpenCV resize uses pixel-centre coordinates.
    expected = np.array([90, 180]) + (np.array(centre) + 0.5) * factor - 0.5
    before = image.copy()
    detected = estimate_centre(image)
    assert detected.status is CentreStatus.DETECTED
    error = np.linalg.norm(np.array([detected.x_px, detected.y_px]) - expected)
    assert error <= 2.0
    tracking = track_ring_candidates(
        detect_ring_candidates(sample_polar(image, detected))
    )
    assert tracking.status is RingTrackingStatus.TRACKED
    assert len(tracking.rings) == 5
    assert np.allclose(
        [ring.mean_radius_px for ring in tracking.rings],
        np.array([30, 44, 58, 72, 86]) * factor,
        atol=1.5,
    )
    assert all(ring.coverage_fraction >= 0.6 for ring in tracking.rings)
    assert np.array_equal(image, before)


@pytest.mark.parametrize("skin", [(100, 145, 185), (35, 55, 75), (180, 200, 220)])
def test_skin_eye_boundaries_and_bright_rectangle_are_not_rings(skin):
    image, _ = make_full_frame(skin, rings=False)
    detected = estimate_centre(image)
    assert detected.status is CentreStatus.NOT_DETECTED
    assert detected.x_px is None and detected.y_px is None
