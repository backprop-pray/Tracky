from __future__ import annotations

from typing import Protocol

import numpy as np

from plant_pipeline.schemas.batch1 import DetectionBox


class DetectorBackend(Protocol):
    name: str
    model_name: str
    license_tag: str
    device: str

    def load(self) -> None:
        ...

    def detect(self, image_bgr: np.ndarray) -> list[DetectionBox]:
        ...

    def close(self) -> None:
        ...
