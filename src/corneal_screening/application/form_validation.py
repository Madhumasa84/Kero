from pathlib import Path
from typing import Any

ALLOWED_EYES = {"OD", "OS"}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def validate_form(
    metadata: dict[str, Any],
    image_filename: str | None,
    image_bytes: bytes | None,
) -> list[str]:
    """Validate UI input without making any clinical decision."""
    errors: list[str] = []

    if not str(metadata.get("anonymous_patient_id", "")).strip():
        errors.append("Please enter an anonymous patient ID.")

    eye = str(metadata.get("eye", "")).strip()
    if not eye:
        errors.append("Please select the captured eye.")
    elif eye not in ALLOWED_EYES:
        errors.append("Eye must be OD or OS.")

    if not str(metadata.get("capture_session_id", "")).strip():
        errors.append("Please enter a capture session ID.")

    if not str(metadata.get("device_version", "")).strip():
        errors.append("Please select a device version.")

    if not str(metadata.get("operator_id", "")).strip():
        errors.append("Please enter an operator ID.")

    if not str(metadata.get("capture_timestamp", "")).strip():
        errors.append("Please enter a capture timestamp.")

    if not image_filename or image_bytes is None:
        errors.append("Please upload a JPG or PNG image.")
        return errors

    extension = Path(image_filename).suffix.lower()
    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        errors.append("Please upload a JPG or PNG image.")

    if not image_bytes:
        errors.append("The uploaded file is empty or unreadable.")

    return errors
