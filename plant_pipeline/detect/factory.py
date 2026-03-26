from __future__ import annotations

from plant_pipeline.config.settings import Batch1DetectorSettings
from plant_pipeline.detect.backwards_compat import ensure_batch1_detector_settings
from plant_pipeline.detect.backends.mock_backend import MockDetectorBackend
from plant_pipeline.detect.backends.ultralytics_backend import UltralyticsLeafBackend
from plant_pipeline.detect.base import DetectorBackend


def build_detector_backend(settings: Batch1DetectorSettings) -> DetectorBackend:
    ensure_batch1_detector_settings(settings)
    if settings.backend == "mock":
        return MockDetectorBackend(device=settings.device)
    if settings.backend == "ultralytics_leaf":
        return UltralyticsLeafBackend(model_path=settings.model_path, device=settings.device)
    raise ValueError(f"Unknown detector backend: {settings.backend}")
