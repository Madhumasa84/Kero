"""Application service that resolves devices before calling the shared pipeline."""

from __future__ import annotations

from pathlib import Path

from .. import SOFTWARE_VERSION
from ..config import DeviceRegistry
from ..contracts import AnalysisRequest, AnalysisResult
from ..pipeline import analyze_capture, build_unknown_device_result


class AnalysisService:
    """Resolve a request to a configured device and run one pipeline."""

    def __init__(
        self,
        registry: DeviceRegistry,
        *,
        software_version: str = SOFTWARE_VERSION,
    ) -> None:
        self.registry = registry
        self.software_version = software_version

    def analyze(
        self,
        image_path: str | Path,
        metadata: AnalysisRequest,
    ) -> AnalysisResult:
        record = self.registry.get(metadata.device_version)
        if record is None:
            return build_unknown_device_result(
                metadata,
                software_version=self.software_version,
            )
        return analyze_capture(
            image_path,
            metadata,
            record.configuration,
            software_version=self.software_version,
        )
