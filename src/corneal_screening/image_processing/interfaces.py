"""Typed interfaces for image loading and experimental processing stages."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import numpy as np

from ..contracts import (
    CentreInformation,
    ExperimentalConfiguration,
    FeatureMeasurements,
    QualityMeasurements,
    RingTrackingInformation,
)
from .experimental import PolarSamples, RingCandidates
from .image_io import ImageLoadLimits, LoadedImage


class ImageLoader(Protocol):
    def load_image(
        self,
        image_path: str | Path,
        limits: ImageLoadLimits | None = None,
    ) -> LoadedImage:
        """Load and validate original image bytes."""


class QualityAssessment(Protocol):
    def assess(
        self,
        image: np.ndarray,
        configuration: ExperimentalConfiguration | None = None,
    ) -> QualityMeasurements:
        """Return experimental image statistics without a pass/fail decision."""


class CentreDetector(Protocol):
    def detect(
        self,
        image: np.ndarray,
        configuration: ExperimentalConfiguration | None = None,
    ) -> CentreInformation:
        """Return a supported centre or an explicit failure with diagnostics."""


class PolarSampler(Protocol):
    def sample(
        self,
        image: np.ndarray,
        centre: CentreInformation,
        configuration: ExperimentalConfiguration | None = None,
    ) -> PolarSamples:
        """Sample intensities and validity around a detected centre."""


class Segmentation(Protocol):
    def segment(self, image: np.ndarray) -> object:
        """Segment a region if a separately reviewed stage is introduced."""


class RingCandidateDetector(Protocol):
    def detect(
        self,
        polar: PolarSamples,
        configuration: ExperimentalConfiguration | None = None,
    ) -> RingCandidates:
        """Return variable candidate lists, retaining empty/missing angles."""


class RingTracker(Protocol):
    def track(
        self,
        candidates: RingCandidates,
        configuration: ExperimentalConfiguration | None = None,
    ) -> RingTrackingInformation:
        """Return ordered tracks with missing observations represented as null."""


class FeatureExtractor(Protocol):
    def extract(self, tracking: RingTrackingInformation) -> FeatureMeasurements:
        """Return descriptive pixel geometry after tracking meets its gate."""
