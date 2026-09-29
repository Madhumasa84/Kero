from __future__ import annotations

import json
import re
from pathlib import Path

from corneal_screening.contracts import AnalysisRequest, AnalysisResult


def test_documented_request_and_responses_validate_against_shared_contracts():
    project_root = Path(__file__).resolve().parents[2]
    documentation = (project_root / "docs" / "experimental_pipeline.md").read_text()
    examples = re.findall(r"```json\s*(.*?)\s*```", documentation, flags=re.DOTALL)

    assert len(examples) == 4
    request = json.loads(examples[0])
    AnalysisRequest.model_validate(request)
    for example in examples[1:]:
        result = AnalysisResult.model_validate(json.loads(example))
        assert result.analysis_mode.value in {"MOCK", "EXPERIMENTAL"}
        assert result.status.value == "MANUAL_REVIEW"
