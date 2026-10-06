from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass(frozen=True)
class SyntheticCase:
    case_id: str
    description: str
    image_size: tuple[int, int]
    centre: tuple[int, int]
    ring_radii: tuple[int, ...]
    transformations: tuple[str, ...]


CASES = (
    SyntheticCase(
        "clear_centre",
        "Clear concentric rings centred in the image.",
        (512, 512),
        (256, 256),
        (45, 75, 105, 135),
        (),
    ),
    SyntheticCase(
        "shifted_centre",
        "Concentric rings shifted away from image centre.",
        (512, 512),
        (180, 320),
        (45, 75, 105, 135),
        ("centre_shifted",),
    ),
    SyntheticCase(
        "different_size",
        "Concentric rings in a non-square image.",
        (640, 480),
        (320, 240),
        (40, 70, 100, 130),
        ("image_size_changed",),
    ),
    SyntheticCase(
        "different_spacing",
        "Different ring count and non-uniform ring spacing.",
        (512, 512),
        (256, 256),
        (35, 60, 100, 155, 190),
        ("ring_count_changed", "ring_spacing_changed"),
    ),
    SyntheticCase(
        "partially_hidden",
        "Several ring sectors are occluded.",
        (512, 512),
        (256, 256),
        (45, 75, 105, 135),
        ("partial_occlusion",),
    ),
    SyntheticCase(
        "blurred",
        "Rings blurred with a deterministic Gaussian blur.",
        (512, 512),
        (256, 256),
        (45, 75, 105, 135),
        ("blurred",),
    ),
    SyntheticCase(
        "glare",
        "Bright patch added to simulate glare.",
        (512, 512),
        (256, 256),
        (45, 75, 105, 135),
        ("bright_glare_patch",),
    ),
    SyntheticCase(
        "blank",
        "Blank image with no ring structure.",
        (512, 512),
        (256, 256),
        (),
        ("blank",),
    ),
    SyntheticCase(
        "non_ring",
        "Structured image without concentric rings.",
        (512, 512),
        (256, 256),
        (),
        ("non_ring_pattern",),
    ),
)


def draw_rings(
    size: tuple[int, int],
    centre: tuple[int, int],
    radii: tuple[int, ...],
) -> np.ndarray:
    height, width = size
    image = np.full((height, width), 45, dtype=np.uint8)

    for radius in radii:
        cv2.circle(
            image,
            centre,
            radius,
            220,
            thickness=3,
            lineType=cv2.LINE_AA,
        )

    return image


def apply_transformation(
    image: np.ndarray,
    case: SyntheticCase,
    rng: np.random.Generator,
) -> np.ndarray:
    result = image.copy()

    if case.case_id == "partially_hidden":
        height, width = result.shape
        cv2.rectangle(
            result,
            (0, 0),
            (width // 2, height // 3),
            45,
            thickness=-1,
        )
        cv2.rectangle(
            result,
            (width // 2, height * 2 // 3),
            (width, height),
            45,
            thickness=-1,
        )

    elif case.case_id == "blurred":
        result = cv2.GaussianBlur(result, (15, 15), 4)

    elif case.case_id == "glare":
        height, width = result.shape
        overlay = result.copy()
        cv2.ellipse(
            overlay,
            (width // 3, height // 3),
            (width // 6, height // 10),
            20,
            0,
            360,
            255,
            -1,
        )
        result = cv2.addWeighted(result, 0.45, overlay, 0.55, 0)

    elif case.case_id == "non_ring":
        height, width = result.shape
        result = np.full((height, width), 45, dtype=np.uint8)

        for _ in range(25):
            centre = (
                int(rng.integers(0, width)),
                int(rng.integers(0, height)),
            )
            radius = int(rng.integers(10, 60))
            value = int(rng.integers(100, 230))
            cv2.circle(result, centre, radius, value, 2)

    return result


def generate_case(
    case: SyntheticCase,
    output_dir: Path,
    rng: np.random.Generator,
) -> None:
    image = draw_rings(case.image_size, case.centre, case.ring_radii)
    image = apply_transformation(image, case, rng)

    filename = f"{case.case_id}_synthetic_test.png"
    image_path = output_dir / filename
    metadata_path = output_dir / f"{case.case_id}_synthetic_test.json"

    if not cv2.imwrite(str(image_path), image):
        raise RuntimeError(f"Failed to write {image_path}")

    metadata = {
        "schema_version": "1.0",
        "synthetic_test_image": True,
        "case_id": case.case_id,
        "description": case.description,
        "image_path": filename,
        "image_size": {
            "width": case.image_size[1],
            "height": case.image_size[0],
        },
        "known_centre": {
            "x": case.centre[0],
            "y": case.centre[1],
        },
        "known_ring_radii": list(case.ring_radii),
        "transformations": list(case.transformations),
        "seed": 42,
        "placeholder_values": True,
        "notes": (
            "Synthetic test fixture. No patient or device information "
            "is represented."
        ),
    }

    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )


def generate_fixtures(output_dir: Path, seed: int = 42) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(seed)

    for case in CASES:
        generate_case(case, output_dir, rng)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate deterministic synthetic KeraScan test fixtures."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/fixtures/generated"),
        help="Output directory for generated fixtures.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed.",
    )
    args = parser.parse_args()

    generate_fixtures(args.output, args.seed)
    print(f"Generated {len(CASES)} synthetic fixtures in {args.output}")


if __name__ == "__main__":
    main()
