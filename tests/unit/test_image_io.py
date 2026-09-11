from __future__ import annotations

import base64
import hashlib
from pathlib import Path
import cv2
import numpy as np

import pytest

from corneal_screening.contracts import ReasonCode
from corneal_screening.image_processing import (
    ImageLoadError,
    ImageLoadLimits,
    load_image,
)

KNOWN_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
KNOWN_PNG_SHA256 = "431ced6916a2a21a156e38701afe55bbd7f88969fbbfc56d7fe099d47f265460"


def assert_image_error(path: Path, code: ReasonCode, limits=None) -> ImageLoadError:
    with pytest.raises(ImageLoadError) as raised:
        load_image(path, limits)
    assert raised.value.code == code
    assert raised.value.message
    assert raised.value.instruction
    return raised.value


def test_loads_valid_jpeg_and_preserves_source(valid_jpeg_path: Path):
    before = valid_jpeg_path.read_bytes()
    loaded = load_image(valid_jpeg_path)

    assert loaded.image_format.value == "JPEG"
    assert loaded.width_px == 16
    assert loaded.height_px == 12
    assert loaded.channel_count == 3
    assert loaded.original_bytes == before
    assert loaded.working_array.flags.writeable is False
    assert valid_jpeg_path.read_bytes() == before


def test_loads_valid_png(valid_png_path: Path):
    loaded = load_image(valid_png_path)

    assert loaded.image_format.value == "PNG"
    assert (loaded.width_px, loaded.height_px, loaded.channel_count) == (10, 8, 3)
    assert loaded.orientation_transformation == "none"


def test_known_fixture_hash(tmp_path: Path):
    path = tmp_path / "known.png"
    path.write_bytes(KNOWN_PNG)

    loaded = load_image(path)

    assert hashlib.sha256(KNOWN_PNG).hexdigest() == KNOWN_PNG_SHA256
    assert loaded.original_sha256 == KNOWN_PNG_SHA256


def test_missing_file_has_typed_error(tmp_path: Path):
    error = assert_image_error(tmp_path / "missing.jpg", ReasonCode.IMAGE_READ_ERROR)
    assert "existing" in error.instruction


def test_empty_file_has_typed_error(tmp_path: Path):
    path = tmp_path / "empty.jpg"
    path.write_bytes(b"")

    error = assert_image_error(path, ReasonCode.IMAGE_EMPTY)

    assert error.original_sha256 == hashlib.sha256(b"").hexdigest()


def test_corrupt_file_has_typed_error(tmp_path: Path):
    path = tmp_path / "corrupt.jpg"
    path.write_bytes(b"not an image")

    assert_image_error(path, ReasonCode.IMAGE_CORRUPT)


def test_unsupported_extension_is_rejected(tmp_path: Path, png_bytes: bytes):
    path = tmp_path / "capture.gif"
    path.write_bytes(png_bytes)

    assert_image_error(path, ReasonCode.IMAGE_UNSUPPORTED_FORMAT)


def test_extension_content_mismatch_is_rejected(tmp_path: Path, png_bytes: bytes):
    path = tmp_path / "capture.jpg"
    path.write_bytes(png_bytes)

    assert_image_error(path, ReasonCode.IMAGE_EXTENSION_CONTENT_MISMATCH)


def test_upload_size_limit_is_enforced(valid_jpeg_path: Path):
    size = valid_jpeg_path.stat().st_size
    limits = ImageLoadLimits(max_upload_bytes=size - 1)

    error = assert_image_error(valid_jpeg_path, ReasonCode.IMAGE_TOO_LARGE, limits)

    assert str(size) in error.message


def test_decoded_dimension_limit_is_enforced(valid_png_path: Path):
    limits = ImageLoadLimits(max_decoded_width_px=9)

    assert_image_error(valid_png_path, ReasonCode.IMAGE_DIMENSIONS_EXCEEDED, limits)


def test_upload_size_exactly_at_limit_is_accepted(valid_jpeg_path: Path):
    size = valid_jpeg_path.stat().st_size

    loaded = load_image(
        valid_jpeg_path,
        ImageLoadLimits(max_upload_bytes=size),
    )

    assert loaded.original_size_bytes == size


def test_decoded_height_limit_is_enforced(valid_png_path: Path):
    limits = ImageLoadLimits(max_decoded_height_px=7)

    assert_image_error(
        valid_png_path,
        ReasonCode.IMAGE_DIMENSIONS_EXCEEDED,
        limits,
    )


def test_jpeg_extension_is_accepted(tmp_path: Path, jpeg_bytes: bytes):
    path = tmp_path / "synthetic_capture.jpeg"
    path.write_bytes(jpeg_bytes)

    loaded = load_image(path)

    assert loaded.image_format.value == "JPEG"


def test_decoded_height_limit_is_enforced(valid_png_path: Path):
    limits = ImageLoadLimits(max_decoded_height_px=7)

    assert_image_error(
        valid_png_path,
        ReasonCode.IMAGE_DIMENSIONS_EXCEEDED,
        limits,
    )


def test_decoded_pixel_limit_is_enforced(valid_png_path: Path):
    limits = ImageLoadLimits(max_decoded_pixels=79)

    assert_image_error(
        valid_png_path,
        ReasonCode.IMAGE_DIMENSIONS_EXCEEDED,
        limits,
    )


def test_exact_dimension_and_pixel_limits_are_accepted(valid_png_path: Path):
    limits = ImageLoadLimits(
        max_decoded_width_px=10,
        max_decoded_height_px=8,
        max_decoded_pixels=80,
    )

    loaded = load_image(valid_png_path, limits)

    assert (loaded.width_px, loaded.height_px) == (10, 8)


def test_grayscale_png_reports_one_channel(tmp_path: Path):
    image = np.full((6, 7), 128, dtype=np.uint8)
    success, encoded = cv2.imencode(".png", image)
    assert success

    path = tmp_path / "synthetic_grayscale.png"
    path.write_bytes(encoded.tobytes())

    loaded = load_image(path)

    assert loaded.channel_count == 1
    assert loaded.working_array.flags.writeable is False


def test_alpha_png_reports_four_channels(tmp_path: Path):
    image = np.zeros((6, 7, 4), dtype=np.uint8)
    image[:, :, 3] = 255
    success, encoded = cv2.imencode(".png", image)
    assert success

    path = tmp_path / "synthetic_alpha.png"
    path.write_bytes(encoded.tobytes())

    loaded = load_image(path)

    assert loaded.channel_count == 4
    assert loaded.working_array.flags.writeable is False
