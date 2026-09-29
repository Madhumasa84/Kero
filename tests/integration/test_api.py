from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from pathlib import Path

import cv2
import httpx
import numpy as np

from corneal_screening.application.api import create_app
from corneal_screening.contracts import AnalysisMode


def _app(application_config, registry, tmp_path: Path, max_request_bytes=None):
    storage = application_config.storage.model_copy(
        update={"temporary_directory": str(tmp_path / "temporary")}
    )
    updates = {"storage": storage}
    if max_request_bytes is not None:
        updates["max_request_bytes"] = max_request_bytes
    application = application_config.model_copy(update=updates)
    return create_app(application=application, registry=registry)


def _metadata_json(metadata):
    return json.dumps(metadata.model_dump(mode="json"))


def _request(app, method, path, **kwargs):
    async def send():
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_health_and_device_listing(application_config, registry, tmp_path):
    app = _app(application_config, registry, tmp_path)

    health = _request(app, "GET", "/health")
    devices = _request(app, "GET", "/devices")

    assert health.status_code == 200
    assert health.json()["analysis_mode"] == "MOCK"
    assert devices.status_code == 200
    assert devices.json()["devices"][0]["device_version"] == "device_v1"
    assert devices.json()["devices"][0]["calibration_status"] == "UNVALIDATED"


def test_upload_returns_shared_mock_result(
    application_config, registry, tmp_path, metadata, jpeg_bytes
):
    app = _app(application_config, registry, tmp_path)

    response = _request(
        app,
        "POST",
        "/analyze",
        files={"image": ("capture.jpg", jpeg_bytes, "image/jpeg")},
        data={"metadata": _metadata_json(metadata)},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "MANUAL_REVIEW"
    assert body["analysis_mode"] == "MOCK"
    assert "Mock result: image analysis has not been performed." in body["message"]


def test_experimental_api_returns_shared_result_and_opt_in_inline_overlays(
    application_config, registry, tmp_path, metadata
):
    app = _app(application_config, registry, tmp_path)
    image = np.zeros((384, 384, 3), dtype=np.uint8)
    for radius in (35, 55, 75, 95, 115, 135):
        cv2.circle(image, (173, 204), radius, (220, 220, 220), 2, cv2.LINE_AA)
    success, encoded = cv2.imencode(".png", image)
    assert success
    image_bytes = encoded.tobytes()
    experimental = metadata.model_copy(
        update={"analysis_mode": AnalysisMode.EXPERIMENTAL}
    )
    fields = {"image": ("synthetic.png", image_bytes, "image/png")}
    data = {"metadata": _metadata_json(experimental)}

    default_response = _request(app, "POST", "/analyze", files=fields, data=data)
    overlay_response = _request(
        app,
        "POST",
        "/analyze?include_overlays=true",
        files=fields,
        data=data,
    )

    assert default_response.status_code == 200, default_response.text
    default_body = default_response.json()
    assert default_body["analysis_mode"] == "EXPERIMENTAL"
    assert default_body["status"] == "MANUAL_REVIEW"
    assert (
        default_body["original_image_sha256"] == hashlib.sha256(image_bytes).hexdigest()
    )
    assert default_body["artifact_references"] == []
    assert overlay_response.status_code == 200
    references = overlay_response.json()["artifact_references"]
    assert {reference["artifact_type"] for reference in references} == {
        "centre_overlay",
        "ring_candidate_overlay",
        "polar_view",
    }
    for reference in references:
        decoded = base64.b64decode(reference["data_base64"])
        assert reference["retained"] is False
        assert hashlib.sha256(decoded).hexdigest() == reference["sha256"]


def test_invalid_metadata_returns_structured_validation_error(
    application_config, registry, tmp_path, metadata, jpeg_bytes
):
    app = _app(application_config, registry, tmp_path)
    invalid = metadata.model_dump(mode="json")
    invalid["eye"] = "LEFT"

    response = _request(
        app,
        "POST",
        "/analyze",
        files={"image": ("capture.jpg", jpeg_bytes, "image/jpeg")},
        data={"metadata": json.dumps(invalid)},
    )

    assert response.status_code == 422
    assert response.json()["code"] == "INVALID_METADATA"
    assert response.json()["errors"][0]["location"] == ["eye"]


def test_unknown_device_is_blocked(
    application_config, registry, tmp_path, metadata, jpeg_bytes
):
    app = _app(application_config, registry, tmp_path)
    unknown = metadata.model_dump(mode="json")
    unknown["device_version"] = "device_missing"

    response = _request(
        app,
        "POST",
        "/analyze",
        files={"image": ("capture.jpg", jpeg_bytes, "image/jpeg")},
        data={"metadata": json.dumps(unknown)},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "BLOCKED"
    assert "DEVICE_UNKNOWN" in response.json()["reason_codes"]


def test_temporary_upload_directory_is_cleaned_after_success_and_failure(
    application_config, registry, tmp_path, metadata, jpeg_bytes
):
    app = _app(application_config, registry, tmp_path)
    temporary_parent = tmp_path / "temporary"

    success = _request(
        app,
        "POST",
        "/analyze",
        files={"image": ("capture.jpg", jpeg_bytes, "image/jpeg")},
        data={"metadata": _metadata_json(metadata)},
    )
    failure = _request(
        app,
        "POST",
        "/analyze",
        files={"image": ("capture.jpg", b"corrupt", "image/jpeg")},
        data={"metadata": _metadata_json(metadata)},
    )

    assert success.status_code == 200
    assert failure.status_code == 200
    assert failure.json()["status"] == "RECAPTURE_REQUIRED"
    assert temporary_parent.is_dir()
    assert list(temporary_parent.iterdir()) == []


def test_upload_limit_returns_error_and_cleans_temp(
    application_config, registry, tmp_path, metadata, jpeg_bytes
):
    app = _app(application_config, registry, tmp_path, max_request_bytes=10)
    temporary_parent = tmp_path / "temporary"

    response = _request(
        app,
        "POST",
        "/analyze",
        files={"image": ("capture.jpg", jpeg_bytes, "image/jpeg")},
        data={"metadata": _metadata_json(metadata)},
    )

    assert response.status_code == 413
    assert response.json()["code"] == "IMAGE_TOO_LARGE"
    assert temporary_parent.is_dir()
    assert list(temporary_parent.iterdir()) == []
