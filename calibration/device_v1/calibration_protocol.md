# Device calibration protocol placeholder

This package is deliberately marked `UNVALIDATED`. The presence of these JSON
files does not mean that the device is calibrated and cannot enable a clinical
decision.

Before changing the status to `VALIDATED`, the device team must document and
review at least:

1. Phone manufacturer, exact model, camera module and lens identity.
2. Capture resolution, crop/orientation policy and camera settings.
3. Physical Placido ring count, diameters, thickness and spacing.
4. Phone-to-attachment geometry, camera offset and working distance.
5. Image-axis and orientation conventions.
6. Camera intrinsics and distortion results from a documented procedure.
7. Placido geometry measurements and repeatability checks.
8. The KERASCAN device configuration fingerprint in every package file.

The device team and technical lead must review the measurement procedure,
acceptance criteria and status transition before any future clinical stage is
enabled. Week 1 performs only package structure and fingerprint checks.
