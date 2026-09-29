import base64
import json
from datetime import datetime

import httpx
import streamlit as st

from corneal_screening.application.form_validation import validate_form

API_BASE_URL = "http://127.0.0.1:8000"
DISCLAIMER = (
    "Engineering prototype only; not a diagnosis or a normal screening result. "
    "Experimental results require manual review; clinical confirmation requires "
    "Pentacam and clinician review."
)


@st.cache_data(ttl=30)
def get_devices() -> list[dict]:
    response = httpx.get(f"{API_BASE_URL}/devices", timeout=5.0)
    response.raise_for_status()
    return response.json().get("devices", [])


def submit_analysis(
    metadata: dict,
    filename: str,
    image_bytes: bytes,
    content_type: str,
    include_overlays: bool = False,
) -> dict:
    response = httpx.post(
        f"{API_BASE_URL}/analyze",
        params={"include_overlays": "true"} if include_overlays else None,
        data={"metadata": json.dumps(metadata)},
        files={"image": (filename, image_bytes, content_type)},
        timeout=30.0,
    )

    if response.status_code == 422:
        detail = response.json()
        message = detail.get("message", "The submitted metadata is invalid.")
        errors = detail.get("errors", [])
        raise ValueError(f"{message}: {errors}")

    response.raise_for_status()
    return response.json()


def display_status(status: str) -> None:
    if status == "RECAPTURE_REQUIRED":
        st.warning(f"Status: {status}", icon="🟠")
    elif status == "MANUAL_REVIEW":
        st.warning(f"Status: {status}", icon="🟡")
    elif status == "BLOCKED":
        st.error(f"Status: {status}")
    else:
        st.info(f"Status: {status or 'Unavailable'}")


def display_result(result: dict) -> None:
    st.subheader(f"{result.get('analysis_mode', 'Analysis')} result")

    display_status(result.get("status", "Unavailable"))

    st.write("**Analysis mode:**", result.get("analysis_mode", "Unavailable"))
    st.write("**Message:**", result.get("message", "Unavailable"))
    st.write("**Device version:**", result.get("device_version", "Unavailable"))
    st.write(
        "**Calibration status:**",
        result.get("calibration_status", "Unavailable"),
    )
    st.write(
        "**Original-image SHA-256:**",
        result.get("original_image_sha256") or "Unavailable",
    )

    reason_codes = result.get("reason_codes") or []
    st.write("**Reason codes:**")
    if reason_codes:
        for code in reason_codes:
            st.write(f"- {code}")
    else:
        st.write("Unavailable")

    quality = result.get("quality_measurements") or {}
    st.write(
        "**Quality status:**",
        quality.get("status") or "Unavailable",
    )

    centre = result.get("centre_information") or {}
    st.write(
        "**Centre information:**",
        centre.get("status") or "Unavailable",
    )

    ring_tracking = result.get("ring_tracking") or {}
    st.write(
        "**Ring tracking:**",
        ring_tracking.get("status") or "Unavailable",
    )

    features = result.get("features") or {}
    st.write(
        "**Feature extraction:**",
        features.get("status") or "Unavailable",
    )
    if quality.get("experimental"):
        st.caption(
            "Quality values are experimental image statistics. They have no "
            "validated capture-quality thresholds."
        )
        st.json(
            {
                key: quality.get(key)
                for key in (
                    "blur_laplacian_variance",
                    "brightness_mean",
                    "contrast_stddev",
                    "underexposed_pixel_fraction",
                    "saturated_pixel_fraction",
                    "visible_ring_coverage_fraction",
                    "missing_sector_count",
                    "sector_count",
                )
            }
        )
    if centre.get("diagnostics"):
        st.write("**Centre diagnostics:**")
        st.json(centre["diagnostics"])
    if ring_tracking.get("rings"):
        st.write("**Ordered ring tracks:**")
        st.json(ring_tracking["rings"])
    if features.get("experimental"):
        st.caption("Geometric features are experimental and measured in image pixels.")
        st.json(features)
    for artifact in result.get("artifact_references") or []:
        encoded = artifact.get("data_base64")
        if not encoded:
            continue
        st.image(
            base64.b64decode(encoded),
            caption=artifact.get("artifact_type", "Review overlay"),
            use_container_width=True,
        )


st.set_page_config(
    page_title="KERASCAN Experimental Image Review",
    page_icon="👁️",
    layout="centered",
)

st.title("KERASCAN Placido Image Review")
st.info(
    "Prototype only. Every result requires manual review. Experimental outputs "
    "are uncalibrated image-space measurements and are not diagnostic."
)
try:
    devices = get_devices()
except (httpx.HTTPError, ValueError):
    devices = []
    st.error(
        "The local analysis API is unavailable. Start the API on "
        "http://127.0.0.1:8000 and refresh this page."
    )

device_names = {
    device["device_version"]: device.get(
        "display_name",
        device["device_version"],
    )
    for device in devices
}

with st.form("screening_form"):
    analysis_mode = st.radio(
        "Processing mode",
        options=["MOCK", "EXPERIMENTAL"],
        horizontal=True,
        help=(
            "MOCK preserves the Week 1 behavior. EXPERIMENTAL computes uncalibrated "
            "image-space measurements and still requires manual review."
        ),
    )
    include_overlays = st.checkbox(
        "Return review overlays with this response",
        value=False,
        help=(
            "Overlays are returned inline for this request and are not "
            "retained by the service."
        ),
    )
    anonymous_patient_id = st.text_input(
        "Anonymous patient ID",
        placeholder="P001",
        help="Use an anonymous identifier only. Never enter a real patient name.",
    )

    eye = st.selectbox(
        "Eye captured",
        options=[None, "OD", "OS"],
        format_func=lambda value: {
            None: "Select eye",
            "OD": "OD – Right eye",
            "OS": "OS – Left eye",
        }[value],
    )

    capture_session_id = st.text_input(
        "Capture session ID",
        placeholder="S01",
    )

    device_version = st.selectbox(
        "Device version",
        options=[None, *device_names.keys()],
        format_func=lambda value: (
            "Select device" if value is None else f"{value} – {device_names[value]}"
        ),
    )

    operator_id = st.text_input(
        "Operator ID",
        placeholder="OP001",
    )

    current_local = datetime.now().astimezone()
    capture_date = st.date_input(
        "Capture date",
        value=current_local.date(),
    )
    capture_time = st.time_input(
        "Capture time",
        value=current_local.time().replace(microsecond=0),
    )

    uploaded_image = st.file_uploader(
        "Upload Placido image",
        type=["jpg", "jpeg", "png"],
        help="The original image will be sent without modification.",
    )

    if uploaded_image is not None:
        st.image(
            uploaded_image,
            caption="Preview only — original upload is not modified",
            use_container_width=True,
        )

    analyze_clicked = st.form_submit_button(
        "Run pipeline",
        disabled=not devices,
    )

if analyze_clicked:
    image_bytes = uploaded_image.getvalue() if uploaded_image is not None else None

    local_timezone = datetime.now().astimezone().tzinfo
    capture_timestamp = datetime.combine(
        capture_date,
        capture_time,
        tzinfo=local_timezone,
    ).isoformat()

    metadata = {
        "schema_version": "1.1.0",
        "anonymous_patient_id": anonymous_patient_id,
        "eye": eye,
        "capture_session_id": capture_session_id,
        "device_version": device_version,
        "operator_id": operator_id,
        "capture_timestamp": capture_timestamp,
        "analysis_mode": analysis_mode,
    }

    errors = validate_form(
        metadata=metadata,
        image_filename=(uploaded_image.name if uploaded_image is not None else None),
        image_bytes=image_bytes,
    )

    if errors:
        for error in errors:
            st.error(error)
    else:
        try:
            result = submit_analysis(
                metadata=metadata,
                filename=uploaded_image.name,
                image_bytes=image_bytes,
                content_type=uploaded_image.type or "application/octet-stream",
                include_overlays=include_overlays,
            )
            display_result(result)
        except ValueError as exc:
            st.error(str(exc))
        except httpx.HTTPError:
            st.error(
                "The local analysis request failed. Confirm that the API "
                "is running and try again."
            )

st.divider()
st.caption(DISCLAIMER)
