# Member 3 integration: local interface and manifest

The Streamlit application in `src/corneal_screening/application/app.py` uses
the existing FastAPI service and shared `AnalysisRequest`/`AnalysisResult`
contracts. It defaults to `MOCK`, allows an explicit `EXPERIMENTAL` request and
can opt in to inline overlays. It does not contain screening or referral
policy.

Start the local API and UI in separate terminals:

```bash
uvicorn corneal_screening.application.api:app --host 127.0.0.1 --port 8000
streamlit run src/corneal_screening/application/app.py
```

The UI sends the original upload bytes to `/analyze`. A preview is display-only.
The optional “Return review overlays” control adds
`?include_overlays=true`; artifacts arrive in the same result as base64 PNGs
with `retained: false`. The default request has no artifacts and the service
does not retain image or overlay files.

The request, success and failure examples, stage semantics, output fields and
overlay response contract are in
[experimental_pipeline.md](experimental_pipeline.md). The generated Pydantic
schemas remain authoritative. Invalid metadata receives HTTP 422, an upload
over the request limit receives HTTP 413, and image decode failures use the
shared result with a typed reason code.

The manifest row remains defined by
[`dataset_manifest.schema.json`](../schemas/dataset_manifest.schema.json),
with entry guidance in [dataset_manifest_guide.md](dataset_manifest_guide.md).
Use anonymous identifiers and relative image paths. Keep patient images out of
Git and personal cloud storage.
