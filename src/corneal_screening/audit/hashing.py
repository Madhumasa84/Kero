"""Deterministic hashes for original inputs and physical configurations."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def canonical_json_bytes(value: Any) -> bytes:
    """Encode JSON with stable key ordering and strict numeric handling."""

    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    """Hash a file without loading it all into memory."""

    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        while chunk := stream.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def hash_device_configuration(device_config: Any) -> str:
    """Hash only the calibration-relevant part of a device configuration."""

    if not hasattr(device_config, "calibration_fingerprint_payload"):
        raise TypeError("device_config must expose calibration_fingerprint_payload()")
    return sha256_bytes(
        canonical_json_bytes(device_config.calibration_fingerprint_payload())
    )
