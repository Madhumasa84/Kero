# Week 1 acceptance record

Verification date: 2026-09-08 (Asia/Calcutta).

The project was started from an empty worktree: no application files or
AGENTS.md instructions were present. The target interpreter and dependencies
were installed into the ignored `.venv` using Python 3.11.15 and the pinned
versions in `requirements-lock.txt`/`pyproject.toml`.

## Implemented and checked

| Acceptance area | Evidence | Result |
| --- | --- | --- |
| Typed request/result/configuration/manifest contracts | Pydantic models plus generated JSON schemas; `tests/unit/test_contracts.py` and `tests/unit/test_schemas.py` | Passed |
| Required identifiers, OD/OS and timezone-aware timestamps | Contract unit tests, including naive timestamp rejection | Passed |
| JPEG/PNG loading and source immutability | `tests/unit/test_image_io.py` | Passed |
| Missing, empty, corrupt, unsupported and extension-mismatch input | Typed `ImageLoadError` tests with recovery instructions | Passed |
| Upload-size and decoded-dimension limits | Loader tests and API hard-limit test | Passed |
| Known SHA-256 | 68-byte synthetic PNG fixture with expected SHA-256 `431ced6916a2a21a156e38701afe55bbd7f88969fbbfc56d7fe099d47f265460` | Passed |
| Stable device fingerprint and calibration compatibility | `tests/unit/test_configuration.py`; changing geometry changes the fingerprint and invalidates the old package | Passed |
| Missing/unvalidated calibration safety | Calibration package is reported `UNVALIDATED`; missing package is reported `MISSING`; no negative status is emitted | Passed |
| Mock result and unexecuted stages | `tests/unit/test_pipeline.py` and `tests/unit/test_policy.py` | Passed |
| Strict JSON and non-finite values | Result JSON validated with `jsonschema`; NaN/infinity rejected and unavailable fields serialize as `null` | Passed |
| Local API health, devices, upload and validation errors | `tests/integration/test_api.py` through FastAPI ASGI transport | Passed |
| Temporary upload cleanup | API success, corrupt-image and over-limit paths assert empty temporary parent | Passed |
| CLI | Synthetic PNG invocation returned `MANUAL_REVIEW`, `MOCK`, the required mock message and the known hash | Passed |
| Formatting and linting | `./.venv/bin/ruff format --check src tests scripts`; `./.venv/bin/ruff check src tests scripts` | Passed |
| Full test suite | `./.venv/bin/python -m pytest -q` | 36 passed in 0.57s |
| CI definition | `.github/workflows/ci.yml` runs install, format, lint, schema generation check and pytest with synthetic fixtures | Added |

The FastAPI application imports and completes application startup. This
executor does not permit binding a TCP socket, so the live `uvicorn` process
smoke test could not bind even to loopback; the endpoint behavior was checked
through the ASGI integration tests. The documented command is ready for a
normal local machine.

## Deliberately deferred

The following are not Week 1 acceptance items and remain unavailable:

- eye-content or capture-quality assessment;
- centre detection;
- image enhancement or clinical segmentation;
- Placido ring tracking and ring counts;
- Placido geometry mapping, working-distance estimation and calibration
  measurements;
- Arc-Step, Zernike, corneal topography and model inference;
- disease classification, clinical thresholds, `SCREEN_NEGATIVE` and
  `PENTACAM_EVALUATION_RECOMMENDED` decisions;
- clinical validation and capture-protocol approval;
- the Streamlit application.

`configs/devices/device_v1.yaml` and its calibration package intentionally
retain unknown physical values as `null` and status `UNVALIDATED`. The device
team must provide and review the measurements listed in
`docs/device_spec.md` before any future validated processing path is enabled.
