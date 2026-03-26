from __future__ import annotations

import cv2
import numpy as np

from plant_pipeline.anomaly.patchcore import PatchCoreScorer
from plant_pipeline.detect.tflite_detector import PlantDetector, VegetationFallbackDetector
from plant_pipeline.schemas.models import CaptureRequest
from plant_pipeline.services.pipeline_service import PlantInspectionPipeline


class OfflineUploadClient:
    def wifi_available(self) -> bool:
        return False

    def upload_record(self, payload: dict, files: dict[str, str]) -> None:
        raise AssertionError("upload_record should not be called when Wi-Fi is unavailable")


def test_pipeline_runs_end_to_end(settings, synthetic_plant_image):
    pipeline = PlantInspectionPipeline(
        settings,
        detector=PlantDetector(settings.detect, backend=VegetationFallbackDetector()),
        anomaly_scorer=PatchCoreScorer(settings.anomaly),
        upload_client=OfflineUploadClient(),
    )
    try:
        record = pipeline.run_inspection(CaptureRequest(mission_id="mission-1", source_image_path=str(synthetic_plant_image)))
        assert record.valid
        assert record.contains_plant
        assert record.artifact_paths["thumbnail"]
    finally:
        pipeline.close()


def test_pipeline_rejects_invalid_quality(settings, tmp_path):
    image = np.zeros((800, 1200, 3), dtype=np.uint8)
    path = tmp_path / "dark.jpg"
    cv2.imwrite(str(path), image)
    pipeline = PlantInspectionPipeline(
        settings,
        detector=PlantDetector(settings.detect, backend=VegetationFallbackDetector()),
        anomaly_scorer=PatchCoreScorer(settings.anomaly),
        upload_client=OfflineUploadClient(),
    )
    try:
        record = pipeline.run_inspection(CaptureRequest(mission_id="mission-2", source_image_path=str(path)))
        assert not record.valid
        assert record.suspicion_label == "invalid"
    finally:
        pipeline.close()
