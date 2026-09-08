"""Loading and registry helpers for versioned application/device settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from .calibration.validation import validate_calibration_package
from .contracts import (
    ApplicationConfiguration,
    CalibrationValidation,
    DeviceConfiguration,
)


class ConfigurationError(ValueError):
    """Raised when a YAML configuration cannot be loaded or validated."""


def _read_yaml(path: Path) -> dict:
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigurationError(f"could not read configuration {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigurationError(f"configuration {path} must contain a YAML object")
    return value


def load_application_configuration(path: str | Path) -> ApplicationConfiguration:
    """Load application settings, which are excluded from device fingerprints."""

    config_path = Path(path)
    try:
        return ApplicationConfiguration.model_validate(_read_yaml(config_path))
    except Exception as exc:
        if isinstance(exc, ConfigurationError):
            raise
        raise ConfigurationError(
            f"invalid application configuration {config_path}: {exc}"
        ) from exc


def load_device_configuration(
    path: str | Path,
    project_root: str | Path | None = None,
) -> DeviceConfiguration:
    """Load one device definition and resolve its package path for runtime use."""

    config_path = Path(path)
    try:
        config = DeviceConfiguration.model_validate(_read_yaml(config_path))
    except Exception as exc:
        if isinstance(exc, ConfigurationError):
            raise
        raise ConfigurationError(
            f"invalid device configuration {config_path}: {exc}"
        ) from exc

    if config.calibration_package_path is None:
        return config

    root = (
        Path(project_root)
        if project_root is not None
        else config_path.resolve().parents[2]
    )
    package_path = Path(config.calibration_package_path)
    if not package_path.is_absolute():
        package_path = root / package_path
    return config.model_copy(
        update={"calibration_package_path": str(package_path.resolve())}
    )


@dataclass(frozen=True)
class DeviceRecord:
    configuration: DeviceConfiguration
    calibration: CalibrationValidation


class DeviceRegistry:
    """In-memory registry of configured devices and their package summaries."""

    def __init__(self, records: dict[str, DeviceRecord]) -> None:
        self._records = dict(records)

    @classmethod
    def from_directory(
        cls,
        devices_directory: str | Path,
        project_root: str | Path | None = None,
    ) -> DeviceRegistry:
        directory = Path(devices_directory)
        records: dict[str, DeviceRecord] = {}
        if not directory.is_dir():
            raise ConfigurationError(
                f"device configuration directory is missing: {directory}"
            )
        paths = sorted((*directory.glob("*.yaml"), *directory.glob("*.yml")))
        if not paths:
            raise ConfigurationError(f"no device configurations found in {directory}")
        for path in paths:
            config = load_device_configuration(path, project_root=project_root)
            if config.device_version in records:
                raise ConfigurationError(
                    f"duplicate device version: {config.device_version}"
                )
            calibration = validate_calibration_package(config)
            records[config.device_version] = DeviceRecord(config, calibration)
        return cls(records)

    def get(self, device_version: str) -> DeviceRecord | None:
        return self._records.get(device_version)

    def records(self) -> tuple[DeviceRecord, ...]:
        return tuple(self._records[key] for key in sorted(self._records))


def load_default_runtime(
    project_root: str | Path | None = None,
) -> tuple[ApplicationConfiguration, DeviceRegistry]:
    root = (
        Path(project_root)
        if project_root is not None
        else Path(__file__).resolve().parents[2]
    )
    application = load_application_configuration(root / "configs" / "application.yaml")
    devices_directory = root / application.devices_directory
    registry = DeviceRegistry.from_directory(devices_directory, project_root=root)
    return application, registry
