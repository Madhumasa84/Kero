# Member 2 handoff: image input and capture data organization

Member 2 can work on image-input behavior and test-image organization without
installing Streamlit or touching clinical policy.

Files to own or extend:

- `src/corneal_screening/image_processing/image_io.py` for loader behavior.
- `src/corneal_screening/image_processing/interfaces.py` for the documented loader interface.
- `tests/unit/test_image_io.py` for synthetic input tests.
- `tests/fixtures/README.md` and temporary local fixture generation. Keep actual image fixtures outside Git.
- Capture documentation additions after technical-lead and device-team review.

The exact loader signature is:

```python
from pathlib import Path
from corneal_screening.image_processing import ImageLoadLimits, LoadedImage

def load_image(
    image_path: str | Path,
    limits: ImageLoadLimits | None = None,
) -> LoadedImage:
    ...
```

`load_image` reads original bytes, hashes them, verifies both extension and
content signature, decodes JPEG/PNG with OpenCV and returns a read-only working
array. It does not rotate, sharpen, enhance or overwrite the source. Week 1
records `orientation_transformation == "none"`; an eventual orientation step
must preserve the original bytes and hash and record its transformation.
Successful decoding only proves that the file is a supported image within its
limits. It does not prove that an eye is present or that the capture is
clinically acceptable.

Construct valid metadata with the shared model:

```python
from datetime import datetime, timezone
from corneal_screening.contracts import AnalysisRequest

metadata = AnalysisRequest(
    anonymous_patient_id="synthetic-subject-001",
    eye="OD",
    capture_session_id="synthetic-session-001",
    device_version="device_v1",
    operator_id="operator-test",
    capture_timestamp=datetime(2026, 9, 8, 12, 0, tzinfo=timezone.utc),
)
```

Use an offset or `Z`; a naive `datetime` is rejected. `eye` accepts only `OD`
or `OS`.

Generate a dummy image in a test’s `tmp_path`:

```python
import cv2
import numpy as np

image = np.zeros((80, 100, 3), dtype=np.uint8)
ok, encoded = cv2.imencode(".jpg", image)
assert ok
path = tmp_path / "synthetic_capture.jpg"
path.write_bytes(encoded.tobytes())
```

Expected input errors are typed `ImageLoadError` values:

| Case | Code | Recovery |
| --- | --- | --- |
| Missing path | `IMAGE_READ_ERROR` | Choose an existing image file. |
| Empty file | `IMAGE_EMPTY` | Recapture or select a non-empty JPEG/PNG. |
| Corrupt bytes | `IMAGE_CORRUPT` | Recapture or export again. |
| Unsupported extension | `IMAGE_UNSUPPORTED_FORMAT` | Use `.jpg`, `.jpeg` or `.png`. |
| Extension/content mismatch | `IMAGE_EXTENSION_CONTENT_MISMATCH` | Re-export or rename to match the bytes. |
| Upload too large | `IMAGE_TOO_LARGE` | Use the configured upload limit. |
| Decoded dimensions too large | `IMAGE_DIMENSIONS_EXCEEDED` | Capture/export within configured limits. |

Verify source bytes remain unchanged:

```python
import hashlib

before = path.read_bytes()
loaded = load_image(path)
assert path.read_bytes() == before
assert loaded.original_bytes == before
assert loaded.original_sha256 == hashlib.sha256(before).hexdigest()
```

Tests to add or maintain include content-signature cases, grayscale and alpha
channel reporting, exact size-boundary behavior, dimension and pixel limits,
orientation metadata, and source immutability after `analyze_capture`. Run:

```bash
pytest tests/unit/test_image_io.py -q
ruff format --check src/corneal_screening/image_processing tests/unit/test_image_io.py
ruff check src/corneal_screening/image_processing tests/unit/test_image_io.py
```

Capture instructions require technical-lead and device-team review before they
are treated as accepted protocol. Do not commit patient images to Git. Keep
clinical captures on approved local storage and use synthetic temporary images
for tests.
