"""FastAPI application for the offline local analysis service."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from ..config import DeviceRegistry, load_default_runtime
from ..contracts import (
    AnalysisRequest,
    AnalysisResult,
    DeviceListing,
    DeviceListResponse,
)
from .service import AnalysisService


class UploadTooLargeError(ValueError):
    """Raised while streaming an upload beyond the application hard limit."""


class ApiRuntime:
    def __init__(
        self,
        application,
        registry: DeviceRegistry,
    ) -> None:
        self.application = application
        self.registry = registry
        self.service = AnalysisService(
            registry,
            software_version=application.software_version,
        )


def _validation_details(error: ValidationError) -> list[dict[str, object]]:
    return [
        {
            "location": [str(part) for part in item.get("loc", ())],
            "message": item.get("msg", "invalid value"),
            "type": item.get("type", "value_error"),
        }
        for item in error.errors()
    ]


def _metadata_error(
    message: str, errors: list[dict[str, object]] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "code": "INVALID_METADATA",
            "message": message,
            "errors": errors or [],
            "instruction": (
                "Provide valid JSON metadata with timezone-aware "
                "capture_timestamp and eye OD or OS."
            ),
        },
    )


def _parse_metadata(metadata_json: str) -> AnalysisRequest | JSONResponse:
    try:
        value = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        return _metadata_error(f"metadata is not valid JSON: {exc.msg}")
    if not isinstance(value, dict):
        return _metadata_error("metadata must be a JSON object")
    try:
        return AnalysisRequest.model_validate(value)
    except ValidationError as exc:
        return _metadata_error(
            "metadata failed contract validation", _validation_details(exc)
        )


def _upload_suffix(upload: UploadFile) -> str:
    content_type_suffix = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
    }
    if upload.content_type in content_type_suffix:
        return content_type_suffix[upload.content_type]
    filename_suffix = Path(upload.filename or "").suffix.lower()
    return filename_suffix if filename_suffix in {".jpg", ".jpeg", ".png"} else ".bin"


async def _write_upload(upload: UploadFile, destination: Path, max_bytes: int) -> None:
    written = 0
    with destination.open("wb") as target:
        while chunk := await upload.read(1024 * 1024):
            written += len(chunk)
            if written > max_bytes:
                raise UploadTooLargeError
            target.write(chunk)


def create_app(
    *,
    application=None,
    registry: DeviceRegistry | None = None,
    project_root: str | Path | None = None,
) -> FastAPI:
    """Create an app with injectable runtime dependencies for integration tests."""

    if application is None or registry is None:
        loaded_application, loaded_registry = load_default_runtime(project_root)
        application = application or loaded_application
        registry = registry or loaded_registry
    runtime = ApiRuntime(application, registry)

    app = FastAPI(
        title="KERASCAN local analysis API",
        version=application.software_version,
        description="Offline Week 1 mock analysis service.",
    )
    app.state.runtime = runtime

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {
            "status": "ok",
            "service": "kerascan",
            "software_version": application.software_version,
            "analysis_mode": "MOCK",
        }

    @app.get("/devices", response_model=DeviceListResponse)
    async def devices() -> DeviceListResponse:
        return DeviceListResponse(
            devices=[
                DeviceListing(
                    device_version=record.configuration.device_version,
                    display_name=record.configuration.display_name,
                    device_configuration_hash=record.calibration.device_configuration_hash,
                    calibration_status=record.calibration.status,
                    calibration_identifier=record.calibration.calibration_identifier,
                )
                for record in registry.records()
            ]
        )

    @app.post("/analyze", response_model=AnalysisResult)
    async def analyze(
        image: UploadFile = File(  # noqa: B008
            ..., description="JPEG or PNG capture"
        ),
        metadata: str = Form(..., description="JSON-encoded AnalysisRequest"),
    ) -> AnalysisResult | JSONResponse:
        parsed_metadata = _parse_metadata(metadata)
        if isinstance(parsed_metadata, JSONResponse):
            await image.close()
            return parsed_metadata

        temporary_root = application.storage.temporary_directory
        temporary_parent: Path | None = None

        try:
            if temporary_root is not None:
                temporary_parent = Path(temporary_root)
                temporary_parent.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(
                prefix="kerascan-upload-",
                dir=str(temporary_parent) if temporary_parent else None,
            ) as temporary_directory:
                with tempfile.NamedTemporaryFile(
                    mode="wb",
                    prefix="image-",
                    suffix=_upload_suffix(image),
                    dir=temporary_directory,
                    delete=False,
                ) as temporary_file:
                    temporary_path = Path(temporary_file.name)
                try:
                    await _write_upload(
                        image,
                        temporary_path,
                        application.max_request_bytes,
                    )
                    return runtime.service.analyze(temporary_path, parsed_metadata)
                finally:
                    temporary_path.unlink(missing_ok=True)
        except UploadTooLargeError:
            return JSONResponse(
                status_code=413,
                content={
                    "code": "IMAGE_TOO_LARGE",
                    "message": "uploaded image exceeds the application upload limit",
                    "instruction": "Choose a smaller JPEG or PNG image.",
                },
            )
        finally:
            await image.close()

    return app


app = create_app()

__all__ = ["app", "create_app"]
