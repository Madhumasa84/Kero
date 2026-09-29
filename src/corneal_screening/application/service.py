"""Application service that resolves devices before calling the shared pipeline."""

from __future__ import annotations

from pathlib import Path

from .. import SOFTWARE_VERSION
from ..config import DeviceRegistry
from ..contracts import AnalysisRequest, AnalysisResult, ExperimentalConfiguration
from ..pipeline import analyze_capture, build_unknown_device_result


class AnalysisService:
    """Resolve a request to a configured device and run one pipeline."""

    def __init__(
        self,
        registry: DeviceRegistry,
        *,
        software_version: str = SOFTWARE_VERSION,
        experimental_configuration: ExperimentalConfiguration | None = None,
    ) -> None:
        self.registry = registry
        self.software_version = software_version
        self.experimental_configuration = (
            experimental_configuration or ExperimentalConfiguration()
        )

    def analyze(
        self,
        image_path: str | Path,
        metadata: AnalysisRequest,
        *,
        include_overlays: bool = False,
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
            experimental_configuration=self.experimental_configuration,
            include_overlays=include_overlays,
        )
