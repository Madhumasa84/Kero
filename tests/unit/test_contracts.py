from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from corneal_screening.contracts import AnalysisRequest, Eye


def test_valid_metadata_uses_required_names_and_eye(metadata: AnalysisRequest):
    assert metadata.anonymous_patient_id == "synthetic-subject-001"
    assert metadata.eye is Eye.OD
    assert metadata.capture_timestamp.utcoffset() is not None


def test_missing_required_metadata_is_rejected():
    with pytest.raises(ValidationError):
        AnalysisRequest(
            anonymous_patient_id="subject",
            eye="OD",
            capture_session_id="session",
            device_version="device_v1",
            capture_timestamp="2026-09-08T12:00:00+00:00",
        )


def test_only_od_or_os_is_allowed(metadata: AnalysisRequest):
    with pytest.raises(ValidationError):
        AnalysisRequest.model_validate(
            {**metadata.model_dump(mode="json"), "eye": "LEFT"}
        )


def test_naive_capture_timestamp_is_rejected():
    with pytest.raises(ValidationError, match="timezone"):
        AnalysisRequest(
            anonymous_patient_id="subject",
            eye=Eye.OS,
            capture_session_id="session",
            device_version="device_v1",
            operator_id="operator",
            capture_timestamp=datetime(2026, 9, 8, 12, 0),
        )


def test_utc_timestamp_is_accepted():
    request = AnalysisRequest(
        anonymous_patient_id="subject",
        eye=Eye.OS,
        capture_session_id="session",
        device_version="device_v1",
        operator_id="operator",
        capture_timestamp=datetime(2026, 9, 8, 12, 0, tzinfo=timezone(timedelta(0))),
    )
    assert request.capture_timestamp.utcoffset() == timedelta(0)
