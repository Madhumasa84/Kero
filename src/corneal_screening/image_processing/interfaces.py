"""Extension points for image processing stages that are not implemented yet."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import numpy as np

from .image_io import ImageLoadLimits, LoadedImage


class ImageLoader(Protocol):
    def load_image(
        self,
        image_path: str | Path,
        limits: ImageLoadLimits | None = None,
    ) -> LoadedImage:
        """Load and validate original image bytes."""


class QualityAssessment(Protocol):
    def assess(self, image: np.ndarray) -> object:
        """Assess capture quality; an implementation must report its state."""


class CentreDetector(Protocol):
    def detect(self, image: np.ndarray) -> object:
        """Detect the Placido/cornea centre when a future stage is enabled."""


class Segmentation(Protocol):
    def segment(self, image: np.ndarray) -> object:
        """Segment mire or corneal regions in a future stage."""


class RingTracker(Protocol):
    def track(self, image: np.ndarray, centre: object) -> object:
        """Track Placido rings in a future stage."""


class FeatureExtractor(Protocol):
    def extract(self, image: np.ndarray, ring_tracks: object) -> object:
        """Extract geometric features in a future stage."""
