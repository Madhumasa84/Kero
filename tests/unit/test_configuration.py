from __future__ import annotations

from corneal_screening.audit.hashing import hash_device_configuration
from corneal_screening.calibration.validation import validate_calibration_package
from corneal_screening.contracts import (
    CalibrationStatus,
    GeometrySpecification,
    ReasonCode,
)


def test_device_configuration_hash_is_stable(device_config):
    assert hash_device_configuration(device_config) == hash_device_configuration(
        device_config
    )
    assert (
        hash_device_configuration(device_config)
        == "3c3a05da3516075e902ad60e0798a0c40e6ce211b696d7580f6b5c052157ac4e"
    )


def test_application_ui_change_does_not_change_device_hash(
    device_config, application_config
):
    changed_application = application_config.model_copy(
        update={
            "ui_preferences": application_config.ui_preferences.model_copy(
                update={"theme": "high-contrast"}
            )
        }
    )

    assert changed_application.ui_preferences.theme == "high-contrast"
    assert hash_device_configuration(device_config) == hash_device_configuration(
        device_config
    )


def test_calibration_package_is_unvalidated(device_config):
    summary = validate_calibration_package(device_config)

    assert summary.status is CalibrationStatus.UNVALIDATED
    assert summary.compatible is False
    assert ReasonCode.CALIBRATION_UNVALIDATED in summary.reason_codes


def test_calibration_relevant_device_change_invalidates_old_package(device_config):
    changed_physical = device_config.physical.model_copy(
        update={
            "geometry": GeometrySpecification(
                phone_to_device_geometry=device_config.physical.geometry.phone_to_device_geometry,
                camera_to_attachment_offset_mm=1.0,
                working_distance_mm=device_config.physical.geometry.working_distance_mm,
                orientation_convention=device_config.physical.geometry.orientation_convention,
            )
        }
    )
    changed_config = device_config.model_copy(update={"physical": changed_physical})
    summary = validate_calibration_package(changed_config)

    assert hash_device_configuration(changed_config) != hash_device_configuration(
        device_config
    )
    assert summary.status is CalibrationStatus.INVALID
    assert summary.compatible is False
    assert ReasonCode.DEVICE_CONFIGURATION_MISMATCH in summary.reason_codes


def test_missing_calibration_is_reported(device_config, tmp_path):
    missing = device_config.model_copy(
        update={"calibration_package_path": str(tmp_path / "missing")}
    )

    summary = validate_calibration_package(missing)

    assert summary.status is CalibrationStatus.MISSING
    assert ReasonCode.CALIBRATION_MISSING in summary.reason_codes
