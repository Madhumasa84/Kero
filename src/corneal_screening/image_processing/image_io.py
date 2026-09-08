"""Immutable, format-aware image loading for the KERASCAN boundary.

A successful decode proves only that the bytes are a supported image within
the configured limits. It does not prove that the image contains an eye or is
an acceptable clinical capture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import cv2
import numpy as np

from ..audit.hashing import sha256_bytes
from ..contracts import ImageFormat, ReasonCode


@dataclass(frozen=True)
class ImageLoadLimits:
    """Runtime limits for one image input.

    These limits are operational safeguards. They are not claims about the
    physical capture device or clinical suitability.
    """

    max_upload_bytes: int = 16 * 1024 * 1024
    max_decoded_width_px: int = 8_000
    max_decoded_height_px: int = 8_000
    max_decoded_pixels: int = 40_000_000
    supported_extensions: tuple[str, ...] = (".jpg", ".jpeg", ".png")

    def __post_init__(self) -> None:
        if self.max_upload_bytes <= 0:
            raise ValueError("max_upload_bytes must be positive")
        if self.max_decoded_width_px <= 0 or self.max_decoded_height_px <= 0:
            raise ValueError("decoded dimension limits must be positive")
        if self.max_decoded_pixels <= 0:
            raise ValueError("max_decoded_pixels must be positive")
        normalised = tuple(extension.lower() for extension in self.supported_extensions)
        if not normalised or any(
            not extension.startswith(".") for extension in normalised
        ):
            raise ValueError("supported extensions must start with '.'")
        if len(set(normalised)) != len(normalised):
            raise ValueError("supported extensions must be unique")
        object.__setattr__(self, "supported_extensions", normalised)


@dataclass(frozen=True)
class LoadedImage:
    """Decoded working array plus immutable provenance for the source bytes."""

    path: Path
    original_bytes: bytes = field(repr=False)
    original_sha256: str
    original_size_bytes: int
    image_format: ImageFormat
    width_px: int
    height_px: int
    channel_count: int
    orientation_transformation: str
    working_array: np.ndarray = field(repr=False)

    def __post_init__(self) -> None:
        array = self.working_array
        if not isinstance(array, np.ndarray):
            raise TypeError("working_array must be a numpy.ndarray")
        array.setflags(write=False)


class ImageLoadError(ValueError):
    """Typed input error with a user-facing recovery instruction."""

    def __init__(
        self,
        code: ReasonCode,
        message: str,
        instruction: str,
        original_sha256: str | None = None,
    ) -> None:
        self.code = code
        self.message = message
        self.instruction = instruction
        self.original_sha256 = original_sha256
        super().__init__(f"{code.value}: {message}")


def _format_from_extension(extension: str) -> ImageFormat | None:
    extension = extension.lower()
    if extension in {".jpg", ".jpeg"}:
        return ImageFormat.JPEG
    if extension == ".png":
        return ImageFormat.PNG
    return None


def _format_from_bytes(data: bytes) -> ImageFormat | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ImageFormat.PNG
    if data.startswith(b"\xff\xd8\xff"):
        return ImageFormat.JPEG
    return None


def _raise(
    code: ReasonCode,
    message: str,
    instruction: str,
    original_sha256: str | None = None,
) -> None:
    raise ImageLoadError(code, message, instruction, original_sha256)


def load_image(
    image_path: str | Path,
    limits: ImageLoadLimits | None = None,
) -> LoadedImage:
    """Load JPEG or PNG bytes without changing the source file.

    OpenCV decodes an in-memory copy of the original bytes. Week 1 preserves
    the camera pixel orientation and performs no EXIF or geometric rotation;
    ``orientation_transformation`` is therefore always ``"none"`` here.
    An orientation-adjusted array can be added later while retaining the same
    bytes and hash in this return type.
    """

    limits = limits or ImageLoadLimits()
    path = Path(image_path)
    extension = path.suffix.lower()
    expected_format = _format_from_extension(extension)

    if expected_format is None or extension not in limits.supported_extensions:
        _raise(
            ReasonCode.IMAGE_UNSUPPORTED_FORMAT,
            f"unsupported image extension: {extension or '[none]'}",
            "Use a JPEG (.jpg or .jpeg) or PNG (.png) file.",
        )

    if not path.exists():
        _raise(
            ReasonCode.IMAGE_READ_ERROR,
            "image file does not exist",
            "Choose an existing image file and try again.",
        )
    if not path.is_file():
        _raise(
            ReasonCode.IMAGE_READ_ERROR,
            "image path is not a regular file",
            "Choose an image file rather than a directory or device path.",
        )

    try:
        original_bytes = path.read_bytes()
    except OSError as exc:
        _raise(
            ReasonCode.IMAGE_READ_ERROR,
            f"could not read image file: {exc}",
            "Check that the image is readable and try again.",
        )

    original_sha256 = sha256_bytes(original_bytes)
    original_size_bytes = len(original_bytes)
    if original_size_bytes == 0:
        _raise(
            ReasonCode.IMAGE_EMPTY,
            "image file is empty",
            "Recapture the image or select a non-empty JPEG or PNG file.",
            original_sha256,
        )
    if original_size_bytes > limits.max_upload_bytes:
        _raise(
            ReasonCode.IMAGE_TOO_LARGE,
            f"image is {original_size_bytes} bytes; limit is "
            f"{limits.max_upload_bytes} bytes",
            "Choose a smaller image or use the configured upload limit.",
            original_sha256,
        )

    actual_format = _format_from_bytes(original_bytes)
    if actual_format is None:
        _raise(
            ReasonCode.IMAGE_CORRUPT,
            "image bytes do not have a recognised JPEG or PNG signature",
            "Recapture the image or export it again as JPEG or PNG.",
            original_sha256,
        )
    if actual_format != expected_format:
        _raise(
            ReasonCode.IMAGE_EXTENSION_CONTENT_MISMATCH,
            f"extension indicates {expected_format.value} but bytes indicate "
            f"{actual_format.value}",
            "Rename or re-export the file so its extension matches its content.",
            original_sha256,
        )

    encoded = np.frombuffer(original_bytes, dtype=np.uint8)
    try:
        decoded = cv2.imdecode(encoded, cv2.IMREAD_UNCHANGED)
    except cv2.error as exc:
        _raise(
            ReasonCode.IMAGE_CORRUPT,
            f"OpenCV could not decode image: {exc}",
            "Recapture the image or export it again as JPEG or PNG.",
            original_sha256,
        )
    if decoded is None or decoded.size == 0:
        _raise(
            ReasonCode.IMAGE_CORRUPT,
            "image bytes could not be decoded",
            "Recapture the image or export it again as JPEG or PNG.",
            original_sha256,
        )

    if decoded.ndim == 2:
        channel_count = 1
    elif decoded.ndim == 3 and decoded.shape[2] in {3, 4}:
        channel_count = int(decoded.shape[2])
    else:
        _raise(
            ReasonCode.IMAGE_CORRUPT,
            f"decoded image has unsupported shape {decoded.shape}",
            "Use a standard grayscale, RGB/BGR or RGBA/BGRA JPEG or PNG.",
            original_sha256,
        )

    height_px, width_px = map(int, decoded.shape[:2])
    if (
        width_px > limits.max_decoded_width_px
        or height_px > limits.max_decoded_height_px
        or width_px * height_px > limits.max_decoded_pixels
    ):
        _raise(
            ReasonCode.IMAGE_DIMENSIONS_EXCEEDED,
            f"decoded dimensions are {width_px}x{height_px}; configured limits are "
            f"{limits.max_decoded_width_px}x{limits.max_decoded_height_px} and "
            f"{limits.max_decoded_pixels} pixels",
            "Capture or export an image within the configured dimension limits.",
            original_sha256,
        )

    decoded.setflags(write=False)
    return LoadedImage(
        path=path,
        original_bytes=bytes(original_bytes),
        original_sha256=original_sha256,
        original_size_bytes=original_size_bytes,
        image_format=actual_format,
        width_px=width_px,
        height_px=height_px,
        channel_count=channel_count,
        orientation_transformation="none",
        working_array=decoded,
    )
