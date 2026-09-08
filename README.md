# KERASCAN Week 1

KERASCAN is an offline Placido-image screening research prototype. Week 1
implements the boundary around a future analysis engine:

```text
original JPEG/PNG bytes + capture metadata
  -> metadata and device validation
  -> original-byte SHA-256 and immutable decode
  -> explicit MOCK pipeline
  -> schema-valid JSON result
  -> local FastAPI response
```

A valid Week 1 request returns `MANUAL_REVIEW` and the message `Mock result:
image analysis has not been performed.` Image quality assessment, centre
detection, segmentation, ring tracking, feature extraction, clinical
thresholds and model inference are not implemented. The only screening
disclaimer is:

> Screening/referral support only; not a diagnosis. Pentacam and clinician review are required for confirmation.

The project requires Python 3.11. Streamlit is deliberately not a dependency
of the core.

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
well. The timestamp must include an offset such as `+05:30` or `Z`.

## Run the local API

```bash
uvicorn corneal_screening.application.api:app --host 127.0.0.1 --port 8000
```

The service binds to loopback by default and makes no cloud, telemetry or
external-inference calls. It exposes `GET /health`, `GET /devices` and
`POST /analyze`. The upload uses two multipart fields: `image` containing a
JPEG or PNG and `metadata` containing JSON for `AnalysisRequest`.

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -F 'image=@./capture.jpg;type=image/jpeg' \
  -F 'metadata={"anonymous_patient_id":"demo-001","eye":"OD","capture_session_id":"session-001","device_version":"device_v1","operator_id":"operator-001","capture_timestamp":"2026-09-08T12:00:00+05:30","analysis_mode":"MOCK"}'
```

In Windows PowerShell use `curl.exe` if the `curl` alias points to
`Invoke-WebRequest`. See [member3_handoff.md](docs/member3_handoff.md) for
the response and validation examples.

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

## Handoffs

- [Architecture](docs/architecture.md)
- [SmartKC reference review](docs/smartkc_reference_review.md)
- [Week 1 acceptance](docs/week1_acceptance.md)
- [Member 2 handoff](docs/member2_handoff.md)
- [Member 3 handoff](docs/member3_handoff.md)
