from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate

from corneal_screening.contracts import AnalysisRequest, AnalysisResult, DatasetManifest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_generated_schema_files_match_authoritative_models():
    expected = {
        "analysis_request.schema.json": AnalysisRequest,
        "analysis_result.schema.json": AnalysisResult,
        "dataset_manifest.schema.json": DatasetManifest,
    }
    for filename, model in expected.items():
        actual = json.loads((PROJECT_ROOT / "schemas" / filename).read_text())
        assert actual == model.model_json_schema()


def test_mock_result_validates_against_generated_schema(
    valid_png_path, metadata, device_config
):
    from corneal_screening.pipeline import analyze_capture

    result = analyze_capture(valid_png_path, metadata, device_config)
    schema = json.loads(
        (PROJECT_ROOT / "schemas" / "analysis_result.schema.json").read_text()
    )

    validate(instance=json.loads(result.to_json()), schema=schema)
