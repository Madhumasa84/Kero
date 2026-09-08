from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import cv2
import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from corneal_screening.config import (  # noqa: E402
    DeviceRegistry,
    load_application_configuration,
    load_device_configuration,
)
from corneal_screening.contracts import AnalysisRequest, Eye  # noqa: E402


@pytest.fixture
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture
def device_config():
    return load_device_configuration(
        PROJECT_ROOT / "configs" / "devices" / "device_v1.yaml",
        project_root=PROJECT_ROOT,
    )


@pytest.fixture
def registry() -> DeviceRegistry:
    return DeviceRegistry.from_directory(
        PROJECT_ROOT / "configs" / "devices",
        project_root=PROJECT_ROOT,
    )


@pytest.fixture
def application_config():
    return load_application_configuration(PROJECT_ROOT / "configs" / "application.yaml")


@pytest.fixture
def metadata() -> AnalysisRequest:
    return AnalysisRequest(
        anonymous_patient_id="synthetic-subject-001",
        eye=Eye.OD,
        capture_session_id="synthetic-session-001",
        device_version="device_v1",
        operator_id="operator-test",
        capture_timestamp=datetime(
            2026,
            9,
            8,
            12,
            0,
            tzinfo=timezone(timedelta(hours=5, minutes=30)),
        ),
    )


@pytest.fixture
def jpeg_bytes() -> bytes:
    image = np.zeros((12, 16, 3), dtype=np.uint8)
    image[:, :, 0] = 80
    image[:, :, 1] = 120
    image[:, :, 2] = 200
    success, encoded = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 95])
    assert success
    return encoded.tobytes()


@pytest.fixture
def png_bytes() -> bytes:
    image = np.zeros((8, 10, 3), dtype=np.uint8)
    image[2:6, 3:8] = (40, 100, 180)
    success, encoded = cv2.imencode(".png", image)
    assert success
    return encoded.tobytes()


@pytest.fixture
def valid_jpeg_path(tmp_path: Path, jpeg_bytes: bytes) -> Path:
    path = tmp_path / "synthetic_capture.jpg"
    path.write_bytes(jpeg_bytes)
    return path


@pytest.fixture
def valid_png_path(tmp_path: Path, png_bytes: bytes) -> Path:
    path = tmp_path / "synthetic_capture.png"
    path.write_bytes(png_bytes)
    return path
