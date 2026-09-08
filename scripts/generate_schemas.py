"""Generate JSON Schema artifacts from the Pydantic contract models."""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from corneal_screening.contracts import (  # noqa: E402
    AnalysisRequest,
    AnalysisResult,
    DatasetManifest,
)

SCHEMAS = {
    "analysis_request.schema.json": AnalysisRequest,
    "analysis_result.schema.json": AnalysisResult,
    "dataset_manifest.schema.json": DatasetManifest,
}


def main() -> None:
    output_directory = PROJECT_ROOT / "schemas"
    output_directory.mkdir(parents=True, exist_ok=True)
    for filename, model in SCHEMAS.items():
        path = output_directory / filename
        path.write_text(
            json.dumps(
                model.model_json_schema(),
                indent=2,
                ensure_ascii=False,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
