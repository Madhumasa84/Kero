"""Validate calibration package provenance without claiming calibration success."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from ..audit.hashing import hash_device_configuration
from ..contracts import (
    CalibrationManifest,
    CalibrationResults,
    CalibrationStatus,
    CalibrationValidation,
    CameraIntrinsicsPackage,
    DeviceConfiguration,
    PlacidoGeometryPackage,
    ReasonCode,
)

_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _read_model(path: Path, model_type: type[_ModelT]) -> _ModelT | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return model_type.model_validate(value)
    except (OSError, json.JSONDecodeError, ValidationError, TypeError):
        return None


def _validation(
    *,
    status: CalibrationStatus,
    identifier: str | None,
    config_hash: str,
    compatible: bool,
    reason_codes: list[ReasonCode],
    message: str,
) -> CalibrationValidation:
    return CalibrationValidation(
        status=status,
        calibration_identifier=identifier,
        device_configuration_hash=config_hash,
        compatible=compatible,
        reason_codes=reason_codes,
        message=message,
    )


def validate_calibration_package(
    device_config: DeviceConfiguration,
    package_path: str | Path | None = None,
) -> CalibrationValidation:
    """Check package files, status and device fingerprint compatibility.

    A package marked ``UNVALIDATED`` is intentionally reported as such even if
    all of its JSON files are structurally valid. Only a package explicitly
    marked ``VALIDATED`` and matching the current physical configuration is
    compatible with future clinical processing.
    """

    config_hash = hash_device_configuration(device_config)
    configured_path = package_path or device_config.calibration_package_path
    if configured_path is None:
        return _validation(
            status=CalibrationStatus.MISSING,
            identifier=None,
            config_hash=config_hash,
            compatible=False,
            reason_codes=[ReasonCode.CALIBRATION_MISSING],
            message="No calibration package is configured for this device.",
        )

    package_dir = Path(configured_path)
    if not package_dir.is_dir():
        return _validation(
            status=CalibrationStatus.MISSING,
            identifier=None,
            config_hash=config_hash,
            compatible=False,
            reason_codes=[ReasonCode.CALIBRATION_MISSING],
            message="The configured calibration package directory is missing.",
        )

    manifest = _read_model(package_dir / "device_manifest.json", CalibrationManifest)
    if manifest is None:
        return _validation(
            status=CalibrationStatus.INVALID,
            identifier=None,
            config_hash=config_hash,
            compatible=False,
            reason_codes=[ReasonCode.CALIBRATION_INVALID],
            message="The calibration manifest is missing or invalid.",
        )

    if manifest.device_version != device_config.device_version:
        return _validation(
            status=CalibrationStatus.INVALID,
            identifier=manifest.calibration_identifier,
            config_hash=config_hash,
            compatible=False,
            reason_codes=[ReasonCode.DEVICE_CONFIGURATION_MISMATCH],
            message="Calibration manifest belongs to a different device version.",
        )
    if manifest.device_configuration_hash != config_hash:
        return _validation(
            status=CalibrationStatus.INVALID,
            identifier=manifest.calibration_identifier,
            config_hash=config_hash,
            compatible=False,
            reason_codes=[ReasonCode.DEVICE_CONFIGURATION_MISMATCH],
            message=(
                "Calibration package fingerprint does not match the device "
                "configuration."
            ),
        )

    intrinsics = _read_model(
        package_dir / "camera_intrinsics.json", CameraIntrinsicsPackage
    )
    geometry = _read_model(
        package_dir / "placido_geometry.json", PlacidoGeometryPackage
    )
    results = _read_model(package_dir / "calibration_results.json", CalibrationResults)
    if intrinsics is None or geometry is None or results is None:
        return _validation(
            status=CalibrationStatus.INVALID,
            identifier=manifest.calibration_identifier,
            config_hash=config_hash,
            compatible=False,
            reason_codes=[ReasonCode.CALIBRATION_INVALID],
            message="One or more calibration package files are missing or invalid.",
        )

    package_models = (intrinsics, geometry, results)
    if any(
        model.calibration_identifier != manifest.calibration_identifier
        or model.device_configuration_hash != config_hash
        for model in package_models
    ):
        return _validation(
            status=CalibrationStatus.INVALID,
            identifier=manifest.calibration_identifier,
            config_hash=config_hash,
            compatible=False,
            reason_codes=[ReasonCode.CALIBRATION_INVALID],
            message=(
                "Calibration package files do not share the manifest identity "
                "or fingerprint."
            ),
        )

    if (
        manifest.status == CalibrationStatus.INVALID
        or results.status == CalibrationStatus.INVALID
    ):
        return _validation(
            status=CalibrationStatus.INVALID,
            identifier=manifest.calibration_identifier,
            config_hash=config_hash,
            compatible=False,
            reason_codes=[ReasonCode.CALIBRATION_INVALID],
            message="Calibration package is explicitly marked invalid.",
        )

    if (
        manifest.status != CalibrationStatus.VALIDATED
        or results.status != CalibrationStatus.VALIDATED
    ):
        return _validation(
            status=CalibrationStatus.UNVALIDATED,
            identifier=manifest.calibration_identifier,
            config_hash=config_hash,
            compatible=False,
            reason_codes=[ReasonCode.CALIBRATION_UNVALIDATED],
            message=(
                "Calibration files are present but device calibration is not validated."
            ),
        )

    return _validation(
        status=CalibrationStatus.VALIDATED,
        identifier=manifest.calibration_identifier,
        config_hash=config_hash,
        compatible=True,
        reason_codes=[],
        message=(
            "Calibration package is validated and compatible with this device "
            "configuration."
        ),
    )
