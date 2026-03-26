from __future__ import annotations

import cv2
import numpy as np

from plant_pipeline.detect.tflite_detector import PlantDetector, VegetationFallbackDetector


def test_detector_finds_plant_roi(settings, synthetic_plant_image, tmp_path):
    image = cv2.imread(str(synthetic_plant_image))
    working = cv2.resize(image, (settings.capture.working_size, settings.capture.working_size))
    detector = PlantDetector(settings.detect, backend=VegetationFallbackDetector())
    result = detector.detect(working, image, str(tmp_path / "roi.png"))
    assert result.contains_plant
    assert result.bbox is not None
    assert result.confidence > 0


def test_detector_skips_nonplant_frame(settings, tmp_path):
    image = np.full((800, 1200, 3), (70, 95, 120), dtype=np.uint8)
    working = cv2.resize(image, (settings.capture.working_size, settings.capture.working_size))
    detector = PlantDetector(settings.detect, backend=VegetationFallbackDetector())
    result = detector.detect(working, image, str(tmp_path / "roi.png"))
    assert not result.contains_plant
    assert result.bbox is None
