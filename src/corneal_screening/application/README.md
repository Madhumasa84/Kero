# Local Streamlit interface

This optional UI uploads original JPEG/PNG bytes and metadata to the local
FastAPI service. It defaults to `MOCK`; `EXPERIMENTAL` is an explicit choice
and returns pixel-space measurements for manual review. It does not diagnose,
classify a normal screen or make referral recommendations.

Install the optional UI dependencies after the core, without suppressing the
UI dependency installation:

```bash
python -m pip install -e ".[ui]"
```

Run the API and UI in separate terminals:

```bash
uvicorn corneal_screening.application.api:app --host 127.0.0.1 --port 8000
streamlit run src/corneal_screening/application/app.py
```

Review overlays are optional. When requested, the API includes their PNG bytes
inline in `artifact_references` with `retained: false`; otherwise the list is
empty. See [member3_handoff.md](../../../docs/member3_handoff.md) and
[experimental_pipeline.md](../../../docs/experimental_pipeline.md) for the
shared contract and examples.
