# Dataset Manifest Guide

The dataset manifest records anonymous capture information and links each image
to its analysis result. It must not contain directly identifying patient data.

The CSV template is located at:

`data/templates/dataset_manifest_template.csv`

The authoritative machine-readable definition is:

`schemas/dataset_manifest.schema.json`

## Columns

| Column | Required | Description |
|---|---:|---|
| `analysis_id` | No | Identifier returned by the analysis API. Leave empty if analysis has not been performed. |
| `anonymous_patient_id` | Yes | Anonymous patient identifier such as `P001`. Never use a real patient name, phone number, email address or hospital ID. |
| `capture_session_id` | Yes | Identifier for the image-capture session, such as `S01`. |
| `capture_timestamp` | Yes | Time of capture in timezone-aware ISO-8601 format. |
| `device_version` | Yes | Configured capture-device version, such as `device_v1`. |
| `eye` | Yes | Eye being captured. Allowed values are `OD` and `OS`. |
| `image_path` | Yes | Relative path to the original image. Do not use a computer-specific absolute path. |
| `operator_id` | Yes | Anonymous identifier for the capture operator, such as `OP001`. |
| `original_image_sha256` | No | SHA-256 hash calculated from the unchanged original image bytes. Leave empty when unavailable. |
| `row_id` | Yes | Unique identifier for the manifest row, such as `row-0001`. |
| `schema_version` | No | Manifest schema version. Use the version defined by the repository contract. |

## Eye values

- `OD` means right eye.
- `OS` means left eye.
- Do not silently replace or reinterpret invalid eye values.

## Data-entry rules

- Missing optional values must remain empty.
- Required values must not be left empty.
- Real patient names and other direct identifiers must never be entered.
- Multiple images belonging to the same patient must retain the same anonymous
  patient ID.
- Image paths must be relative to the dataset location.
- The original image must not be cropped, resized, sharpened or replaced.
- Do not commit patient images to the source-code repository.
- Reference labels must not be invented when Pentacam or clinician results are
  unavailable.
- Pentacam and clinician reference-label columns are not part of the current
  Week 1 authoritative schema. Do not add them without an approved schema
  change.