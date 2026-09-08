# KERASCAN device specification inputs

`configs/devices/device_v1.yaml` is a versioned placeholder. Unknown values
are represented by `null`. Filling a JSON or YAML field does not establish
calibration; the device team and technical lead must review measurements,
repeatability and the status transition to `VALIDATED`.

The following inputs are required before a physical device can support a future
validated processing path:

| Area | Required information |
| --- | --- |
| Phone and camera/lens identity | Phone manufacturer, exact model, camera module and lens identity |
| Capture | Width and height, image format, focus mode, flash mode, zoom, ISO and exposure settings |
| Placido hardware | Physical ring count, ring diameters, ring thickness and ring spacing |
| Phone-to-device geometry | Attachment geometry, camera-to-attachment offset and the reference used to measure it |
| Working distance | Camera or lens reference point to corneal apex, with units and measurement method |
| Orientation | Image x/y convention, phone/device orientation and any rotation or mirroring rule |
| Camera calibration | Intrinsics and distortion results, linked to the exact device fingerprint |
| Placido calibration | Measured ring geometry and repeatability results, linked to the exact fingerprint |

The current package contains no physical measurements. Its calibration status
is `UNVALIDATED`. The package files must all carry the same calibration
identifier and the SHA-256 fingerprint of the calibration-relevant `physical`
configuration. Changing a field such as working distance or lens identity
therefore invalidates the old package.

Runtime image limits and storage settings are operational controls. They do not
stand in for physical measurements and are excluded from the calibration
fingerprint. Application UI preferences are held in `configs/application.yaml`
and likewise do not invalidate physical calibration.

Do not claim calibration or clinical validation is complete until the protocol
in [calibration/device_v1/calibration_protocol.md](../calibration/device_v1/calibration_protocol.md)
has been executed and reviewed.
