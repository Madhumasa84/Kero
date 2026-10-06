from pathlib import Path

import cv2
import numpy as np

from fixtures.generate_synthetic import CASES, generate_fixtures


def test_all_required_synthetic_cases_are_defined():
    case_ids = {case.case_id for case in CASES}

    assert case_ids == {
        "clear_centre",
        "shifted_centre",
        "different_size",
        "different_spacing",
        "partially_hidden",
        "blurred",
        "glare",
        "blank",
        "non_ring",
    }


def test_synthetic_fixture_generation_is_complete(tmp_path: Path):
    generate_fixtures(tmp_path, seed=42)

    for case in CASES:
        image_path = tmp_path / f"{case.case_id}_synthetic_test.png"
        metadata_path = tmp_path / f"{case.case_id}_synthetic_test.json"

        assert image_path.exists()
        assert metadata_path.exists()

        image = cv2.imread(str(image_path), cv2.IMREAD_GRAYSCALE)
        assert image is not None
        assert image.shape == case.image_size

        metadata = metadata_path.read_text(encoding="utf-8")
        assert '"synthetic_test_image": true' in metadata


def test_synthetic_fixture_generation_is_deterministic(tmp_path: Path):
    first = tmp_path / "first"
    second = tmp_path / "second"

    generate_fixtures(first, seed=42)
    generate_fixtures(second, seed=42)

    for case in CASES:
        first_image = cv2.imread(
            str(first / f"{case.case_id}_synthetic_test.png"),
            cv2.IMREAD_UNCHANGED,
        )
        second_image = cv2.imread(
            str(second / f"{case.case_id}_synthetic_test.png"),
            cv2.IMREAD_UNCHANGED,
        )

        assert np.array_equal(first_image, second_image)

        first_metadata = (first / f"{case.case_id}_synthetic_test.json").read_bytes()
        second_metadata = (second / f"{case.case_id}_synthetic_test.json").read_bytes()

        assert first_metadata == second_metadata
