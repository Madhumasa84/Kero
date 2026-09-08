# Member 3 handoff: local interface, validation and manifest

Member 3 can build the Streamlit interface against the existing API and typed
contracts. The core does not import Streamlit.

The API startup command is:

```bash
uvicorn corneal_screening.application.api:app --host 127.0.0.1 --port 8000
```

First obtain configured device choices:

```bash
curl http://127.0.0.1:8000/devices
```

Example response:

```json
{
  "devices": [
    {
      "device_version": "device_v1",
      "display_name": "KERASCAN Week 1 reference device",
      "device_configuration_hash": "3c3a05da3516075e902ad60e0798a0c40e6ce211b696d7580f6b5c052157ac4e",
      "calibration_status": "UNVALIDATED",
      "calibration_identifier": "device_v1-week1-placeholder"
    }
  ]
}
```

`POST /analyze` accepts `multipart/form-data` with exactly these fields:

- `image`: the original JPEG or PNG upload;
- `metadata`: a JSON string containing `anonymous_patient_id`, `eye`,
  `capture_session_id`, `device_version`, `operator_id`,
  `capture_timestamp`, and optional `schema_version`/`analysis_mode`.

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -F 'image=@./capture.png;type=image/png' \
  -F 'metadata={"anonymous_patient_id":"demo-001","eye":"OD","capture_session_id":"session-001","device_version":"device_v1","operator_id":"operator-001","capture_timestamp":"2026-09-08T12:00:00+05:30","analysis_mode":"MOCK"}'
```

A successful mock response has this shape:

```json
{
  "schema_version": "1.0.0",
  "software_version": "0.1.0",
  "analysis_id": "00000000-0000-4000-8000-000000000001",
  "analysis_mode": "MOCK",
  "timestamp": "2026-09-08T06:30:00+00:00",
  "anonymous_patient_id": "demo-001",
  "eye": "OD",
  "capture_session_id": "session-001",
  "operator_id": "operator-001",
  "capture_timestamp": "2026-09-08T12:00:00+05:30",
  "status": "MANUAL_REVIEW",
  "reason_codes": ["MOCK_MODE", "ANALYSIS_NOT_PERFORMED", "CALIBRATION_UNVALIDATED", "CLINICAL_OUTPUT_BLOCKED"],
  "message": "Mock result: image analysis has not been performed.",
  "stage_execution": [
    {"stage_name": "QUALITY_ASSESSMENT", "state": "NOT_RUN", "started_at": null, "finished_at": null, "reason_codes": ["STAGE_NOT_IMPLEMENTED"], "message": "Not implemented in Week 1; no analysis was performed."}
  ],
  "device_version": "device_v1",
  "device_configuration_hash": "3c3a05da3516075e902ad60e0798a0c40e6ce211b696d7580f6b5c052157ac4e",
  "calibration_status": "UNVALIDATED",
  "calibration_identifier": "device_v1-week1-placeholder",
  "original_image_sha256": "431ced6916a2a21a156e38701afe55bbd7f88969fbbfc56d7fe099d47f265460",
  "quality_measurements": {"status": "NOT_ASSESSED", "image_width_px": 1, "image_height_px": 1, "channel_count": 4, "source_format": "PNG", "orientation_transformation": "none", "brightness_mean": null, "contrast_stddev": null, "validity": "UNAVAILABLE"},
  "centre_information": {"status": "NOT_DETECTED", "x_px": null, "y_px": null, "coordinate_system": "image_pixels_xy", "source": null},
  "ring_tracking": {"status": "NOT_RUN", "ring_count": null, "tracked_ring_count": null, "tracked_points": null, "validity": "UNAVAILABLE"},
  "features": {"status": "NOT_RUN", "sim_k1_diopters": null, "sim_k2_diopters": null, "mean_k_diopters": null, "astigmatism_diopters": null, "validity": "UNAVAILABLE"},
  "artifact_references": [],
  "screening_disclaimer": "Screening/referral support only; not a diagnosis. Pentacam and clinician review are required for confirmation."
}
```

The example uses the known 1x1 synthetic PNG fixture. The real response contains all stage records, including input/device/image and
outcome stages. Values such as centre coordinates, ring counts, curvature
features and probabilities are unavailable in Week 1. Display them as
`Unavailable` from their `null` value and status/validity; never convert them
to zero or infer a clinical result.

Invalid metadata returns HTTP 422 with a structured body, for example:

```json
{
  "code": "INVALID_METADATA",
  "message": "metadata failed contract validation",
  "errors": [{"location": ["eye"], "message": "Input should be 'OD' or 'OS'", "type": "enum"}],
  "instruction": "Provide valid JSON metadata with timezone-aware capture_timestamp and eye OD or OS."
}
```

The interface must show a persistent `Demo/mock mode` banner. Form validation
may prevent malformed requests, but it must never decide a referral, a negative
screen or a diagnosis. Use the shared API result and
`src/corneal_screening/referral/policy.py`; do not create a second mock or
duplicate policy in the UI.

The authoritative manifest model is generated into
`schemas/dataset_manifest.schema.json`. An example row is:

```json
{
  "schema_version": "1.0.0",
  "row_id": "row-0001",
  "anonymous_patient_id": "demo-001",
  "eye": "OD",
  "capture_session_id": "session-001",
  "device_version": "device_v1",
  "operator_id": "operator-001",
  "capture_timestamp": "2026-09-08T12:00:00+05:30",
  "image_path": "captures/session-001/od.jpg",
  "original_image_sha256": "431ced6916a2a21a156e38701afe55bbd7f88969fbbfc56d7fe099d47f265460",
  "analysis_id": "00000000-0000-4000-8000-000000000001"
}
```

Use relative image paths and anonymous identifiers only. Do not add patient
names or commit patient images. A preview can be resized for display by
Streamlit, but the original bytes held by the upload object must be the bytes
sent to `/analyze`; preview resizing must never replace the analysis payload.
