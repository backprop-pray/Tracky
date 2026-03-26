from __future__ import annotations

from typing import Iterable, Optional

import numpy as np

from plant_pipeline.schemas.batch1 import DetectionBox


class MockDetectorBackend:
    name = "mock"
    model_name = "mock-detector"
    license_tag = "internal-test-only"

    def __init__(self, detections: Optional[Iterable[DetectionBox]] = None, device: str = "cpu") -> None:
        self._detections = list(detections or [])
        self.device = device

    def load(self) -> None:
        return None

    def detect(self, image_bgr: np.ndarray) -> list[DetectionBox]:
        return list(self._detections)

    def close(self) -> None:
        return None
