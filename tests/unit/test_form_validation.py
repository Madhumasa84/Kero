import pytest

from corneal_screening.application.form_validation import validate_form


def valid_metadata() -> dict[str, str]:
    return {
        "anonymous_patient_id": "P001",
        "eye": "OD",
        "capture_session_id": "S01",
        "device_version": "device_v1",
        "operator_id": "OP001",
        "capture_timestamp": "2026-09-20T19:30:00+05:30",
    }


def test_valid_metadata_is_accepted() -> None:
    errors = validate_form(valid_metadata(), "capture.jpg", b"image-data")
    assert errors == []


def test_missing_patient_id_is_rejected() -> None:
    metadata = valid_metadata()
    metadata["anonymous_patient_id"] = ""

    errors = validate_form(metadata, "capture.jpg", b"image-data")

    assert "Please enter an anonymous patient ID." in errors


def test_missing_image_is_rejected() -> None:
    errors = validate_form(valid_metadata(), None, None)
    assert "Please upload a JPG or PNG image." in errors


def test_invalid_eye_is_rejected() -> None:
    metadata = valid_metadata()
    metadata["eye"] = "LEFT"

    errors = validate_form(metadata, "capture.jpg", b"image-data")

    assert "Eye must be OD or OS." in errors


def test_missing_device_version_is_rejected() -> None:
    metadata = valid_metadata()
    metadata["device_version"] = ""

    errors = validate_form(metadata, "capture.jpg", b"image-data")

    assert "Please select a device version." in errors


def test_unsupported_file_type_is_rejected() -> None:
    errors = validate_form(valid_metadata(), "capture.gif", b"image-data")
    assert "Please upload a JPG or PNG image." in errors


@pytest.mark.parametrize("filename", ["capture.jpg", "capture.jpeg", "capture.png"])
def test_valid_jpg_and_png_types_are_accepted(filename: str) -> None:
    errors = validate_form(valid_metadata(), filename, b"image-data")
    assert errors == []


def test_validation_does_not_generate_clinical_status() -> None:
    errors = validate_form(valid_metadata(), "capture.png", b"image-data")

    assert errors == []
    assert isinstance(errors, list)
