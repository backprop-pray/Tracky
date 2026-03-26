from __future__ import annotations

import cv2
import numpy as np

from plant_pipeline.quality.gate import QualityGate


def test_quality_gate_accepts_sharp_plant(settings, synthetic_plant_image):
    image = cv2.imread(str(synthetic_plant_image))
    working = cv2.resize(image, (settings.capture.working_size, settings.capture.working_size))
    result = QualityGate(settings.quality).evaluate(working)
    assert result.is_valid
    assert result.reject_reason is None


def test_quality_gate_rejects_dark_frame(settings):
    image = np.zeros((640, 640, 3), dtype=np.uint8)
    result = QualityGate(settings.quality).evaluate(image)
    assert not result.is_valid
    assert result.reject_reason == "blur"
