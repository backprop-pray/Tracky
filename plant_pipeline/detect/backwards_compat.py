from __future__ import annotations

from plant_pipeline.config.settings import Batch1DetectorSettings


def ensure_batch1_detector_settings(settings: Batch1DetectorSettings) -> None:
    if settings.backend == "ultralytics_leaf" and not settings.model_path:
        raise ValueError("Ultralytics backend selected but model_path is empty.")
