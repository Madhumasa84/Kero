# Fixture policy

This directory contains only fixture structure, metadata templates and documentation.
Do not commit patient images, patient names or other personal information.

## Categories

- `acceptable/`: approved or synthetic captures intended to meet the capture protocol.
- `blurred/`: synthetic or approved test captures with blur.
- `glare/`: synthetic or approved test captures with strong glare or saturation.
- `obstructed/`: synthetic or approved test captures with eyelid, eyelash or other obstruction.
- `off_centre/`: synthetic or approved test captures with severe decentration.
- `wrong_orientation/`: synthetic or approved test captures with incorrect orientation.
- `non_eye/`: non-medical dummy images used to test invalid input handling.
- `corrupted/`: intentionally invalid files used to test controlled loading errors.

These categories describe input-test expectations only. They are not clinical labels and must not be used to infer a diagnosis.

## Image and metadata rules

- Keep approved de-identified clinical captures in approved local storage outside Git.
- Every stored fixture image requires a matching JSON metadata file.
- Use the same base filename for the image and metadata file.
- Synthetic images must include `_synthetic_test` in their filename and set `synthetic_test_image` to `true`.
- Record every fixture in `test_image_inventory.csv`.
- Never crop, enhance, sharpen, replace or overwrite an original capture.
- Tests may generate temporary synthetic images at runtime; those files are not committed.

## Metadata template

`capture_metadata_template.json` is a template only. Copy it for an approved fixture, replace its values, and retain the agreed field names.
