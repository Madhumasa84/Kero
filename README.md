# KERASCAN experimental Placido pipeline

KERASCAN is an offline Placido-image engineering prototype. The Week 1 input
and mock baseline is preserved; an explicit experimental mode estimates a
candidate ring centre and tracks visible ring candidates:

```text
original JPEG/PNG bytes + capture metadata
  -> metadata and device validation
  -> original-byte SHA-256 and immutable decode
  -> MOCK pipeline by default, or explicitly requested EXPERIMENTAL pipeline
  -> schema-valid JSON result
  -> local FastAPI response
```

A `MOCK` request still returns `MANUAL_REVIEW` and the message `Mock result:
image analysis has not been performed.` An `EXPERIMENTAL` request returns
uncalibrated pixel-space measurements for manual review. Neither mode diagnoses
keratoconus or produces a normal screening result. Clinical thresholds,
corneal power conversion and model inference are not implemented. The
screening disclaimer is:

> Engineering prototype only; not a diagnosis or a normal screening result. Experimental results require manual review; clinical confirmation requires Pentacam and clinician review.

The project requires Python 3.11. Streamlit remains optional and is not
imported by the processing core.

## Setup on Linux or macOS

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt
python -m pip install -e . --no-deps
```

## Setup in Windows PowerShell

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements-lock.txt
python -m pip install -e . --no-deps
```

The tested runtime, development and transitive pins are listed in
[requirements-lock.txt](requirements-lock.txt).
For the optional Streamlit interface, install `python -m pip install -e ".[ui]"`.

## Run one local mock analysis

```bash
kera-analyze ./capture.jpg \
  --anonymous-patient-id demo-001 \
  --eye OD \
  --capture-session-id session-001 \
  --device-version device_v1 \
  --operator-id operator-001 \
  --capture-timestamp 2026-09-08T12:00:00+05:30
```

The command prints one JSON result to standard output. A PNG is accepted as
well. The timestamp must include an offset such as `+05:30` or `Z`. Add
`--analysis-mode EXPERIMENTAL` to run the image-space prototype; `MOCK` remains
the default.

## Run the local API

```bash
uvicorn corneal_screening.application.api:app --host 127.0.0.1 --port 8000
```

The service binds to loopback by default and makes no cloud, telemetry or
external-inference calls. It exposes `GET /health`, `GET /devices` and
`POST /analyze`. The upload uses two multipart fields: `image` containing the
original JPEG or PNG and `metadata` containing JSON for `AnalysisRequest`.
Requests default to `MOCK`; set `analysis_mode` to `EXPERIMENTAL` for pixel-space
measurements. The response always uses the shared `AnalysisResult` contract.
Review overlays are opt-in with `POST /analyze?include_overlays=true`; they are
returned inline for that response and are not retained on disk.

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -F 'image=@./capture.jpg;type=image/jpeg' \
  -F 'metadata={"anonymous_patient_id":"demo-001","eye":"OD","capture_session_id":"session-001","device_version":"device_v1","operator_id":"operator-001","capture_timestamp":"2026-09-08T12:00:00+05:30","analysis_mode":"MOCK"}'
```

In Windows PowerShell use `curl.exe` if the `curl` alias points to
`Invoke-WebRequest`. See [experimental_pipeline.md](docs/experimental_pipeline.md)
for request and result examples, stage behavior, measurements, overlays and
synthetic acceptance tolerances.

## Test and lint

```bash
pytest
ruff format --check src tests scripts
ruff check src tests scripts
python scripts/generate_schemas.py
```

Tests create synthetic images in temporary directories. No clinical dataset is
needed.

## Configuration and calibration

Application settings live in [configs/application.yaml](configs/application.yaml).
Device-dependent settings and runtime image limits live in
[configs/devices/device_v1.yaml](configs/devices/device_v1.yaml). The Week 1
placeholder calibration package is under
[calibration/device_v1](calibration/device_v1). Its physical values are
unknown, its status is `UNVALIDATED`, and its presence does not mean the
device is calibrated. Required measurements are listed in
[docs/device_spec.md](docs/device_spec.md).

The Pydantic models in
[src/corneal_screening/contracts/models.py](src/corneal_screening/contracts/models.py)
are authoritative. The three JSON Schema files under `schemas/` are generated
by `scripts/generate_schemas.py`.

Experimental parameters are versioned in `configs/application.yaml` under
`experimental.configuration_version`. Their thresholds and progression gates
are engineering settings, not validated capture-quality rules. Physical
camera, lens, ring and geometry values remain unknown; calibration remains
`UNVALIDATED`.

## Handoffs

- [Architecture](docs/architecture.md)
- [SmartKC reference review](docs/smartkc_reference_review.md)
- [Week 1 acceptance](docs/week1_acceptance.md)
- [Member 2 handoff](docs/member2_handoff.md)
- [Member 3 handoff](docs/member3_handoff.md)
- [Weeks 2–3 experimental pipeline](docs/experimental_pipeline.md)
- [Limitations and validation scope](docs/limitations.md)
