"""Command-line entry point for one local Week 1 mock analysis."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime

from pydantic import ValidationError

from .config import load_default_runtime
from .contracts import AnalysisRequest, Eye


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run KERASCAN Week 1 mock analysis")
    parser.add_argument("image_path", help="Path to a JPEG or PNG image")
    parser.add_argument("--anonymous-patient-id", required=True)
    parser.add_argument("--eye", choices=[eye.value for eye in Eye], required=True)
    parser.add_argument("--capture-session-id", required=True)
    parser.add_argument("--device-version", required=True)
    parser.add_argument("--operator-id", required=True)
    parser.add_argument(
        "--capture-timestamp",
        required=True,
        help="ISO-8601 timestamp with timezone, for example 2026-09-08T12:00:00+05:30",
    )
    parser.add_argument(
        "--project-root",
        default=None,
        help="Project root containing configs/ (defaults to this checkout)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        metadata = AnalysisRequest(
            anonymous_patient_id=args.anonymous_patient_id,
            eye=args.eye,
            capture_session_id=args.capture_session_id,
            device_version=args.device_version,
            operator_id=args.operator_id,
            capture_timestamp=datetime.fromisoformat(args.capture_timestamp),
        )
        application, registry = load_default_runtime(args.project_root)
        record = registry.get(metadata.device_version)
        if record is None:
            from .pipeline import build_unknown_device_result

            result = build_unknown_device_result(
                metadata,
                software_version=application.software_version,
            )
        else:
            from .pipeline import analyze_capture

            result = analyze_capture(
                args.image_path,
                metadata,
                record.configuration,
                software_version=application.software_version,
            )
    except ValidationError as exc:
        print(
            "Invalid metadata: " + "; ".join(error["msg"] for error in exc.errors()),
            file=sys.stderr,
        )
        return 2
    except (OSError, ValueError) as exc:
        print(f"Could not start analysis: {exc}", file=sys.stderr)
        return 2

    print(result.to_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
