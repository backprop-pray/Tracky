from __future__ import annotations

from pathlib import Path

from plant_pipeline.detect.backends.mock_backend import MockDetectorBackend
from plant_pipeline.schemas.batch1 import Batch1Request, BoundingBox, DetectionBox
from plant_pipeline.services.batch1_service import Batch1Service


def test_invalid_image_path_returns_structured_failure(batch1_config):
    service = Batch1Service(batch1_config, detector_backend=MockDetectorBackend())
    try:
        result = service.run(Batch1Request(image_path="/missing/file.png"))
        assert not result.valid
        assert result.reject_reason == "image_read_error"
    finally:
        service.close()


def test_quality_failure_short_circuits_detector(batch1_config, dark_image):
    class FailIfCalled(MockDetectorBackend):
        def detect(self, image_bgr):
            raise AssertionError("Detector should not run for invalid images")

    service = Batch1Service(batch1_config, detector_backend=FailIfCalled())
    try:
        result = service.run(Batch1Request(image_path=str(dark_image)))
        assert not result.valid
        assert result.contains_plant is False
    finally:
        service.close()


def test_valid_image_without_plant_returns_contains_plant_false(batch1_config, sharp_plant_image):
    service = Batch1Service(batch1_config, detector_backend=MockDetectorBackend())
    try:
        result = service.run(Batch1Request(image_path=str(sharp_plant_image)))
        assert result.valid
        assert not result.contains_plant
    finally:
        service.close()


def test_valid_image_with_cluster_returns_roi_path(batch1_config, sharp_plant_image, dense_leaf_detections):
    service = Batch1Service(batch1_config, detector_backend=MockDetectorBackend(detections=dense_leaf_detections))
    try:
        result = service.run(Batch1Request(image_path=str(sharp_plant_image)))
        assert result.valid
        assert result.contains_plant
        assert "roi_path" in result.artifacts
        assert Path(result.artifacts["roi_path"]).exists()
    finally:
        service.close()


def test_debug_overlay_written_when_enabled(batch1_config, sharp_plant_image, dense_leaf_detections):
    batch1_config.batch1.debug_overlays = True
    service = Batch1Service(batch1_config, detector_backend=MockDetectorBackend(detections=dense_leaf_detections))
    try:
        result = service.run(Batch1Request(image_path=str(sharp_plant_image)))
        assert "overlay_path" in result.artifacts
        assert Path(result.artifacts["overlay_path"]).exists()
    finally:
        service.close()


def test_result_contains_backend_and_license_info(batch1_config, sharp_plant_image, dense_leaf_detections):
    service = Batch1Service(batch1_config, detector_backend=MockDetectorBackend(detections=dense_leaf_detections))
    try:
        result = service.run(Batch1Request(image_path=str(sharp_plant_image)))
        assert result.detector is not None
        assert result.detector.info.backend_name == "mock"
        assert result.detector.info.license_tag == "internal-test-only"
    finally:
        service.close()


def test_single_full_frame_detection_with_low_vegetation_is_rejected(batch1_config, soil_image):
    full_frame = [
        DetectionBox(
            bbox=BoundingBox(x_min=0, y_min=0, x_max=batch1_config.batch1.working_size, y_max=batch1_config.batch1.working_size),
            confidence=0.9,
            label="leaf",
        )
    ]
    service = Batch1Service(batch1_config, detector_backend=MockDetectorBackend(detections=full_frame))
    try:
        result = service.run(Batch1Request(image_path=str(soil_image)))
        assert result.valid
        assert not result.contains_plant
        assert result.metadata["detector_sanity_reject"] == "single_full_frame_low_vegetation"
    finally:
        service.close()


def test_single_detection_roi_is_expanded_with_context(batch1_config, sharp_plant_image):
    detections = [
        DetectionBox(bbox=BoundingBox(x_min=500, y_min=300, x_max=560, y_max=420), confidence=0.9, label="leaf"),
        DetectionBox(bbox=BoundingBox(x_min=430, y_min=280, x_max=490, y_max=390), confidence=0.35, label="leaf"),
    ]
    service = Batch1Service(batch1_config, detector_backend=MockDetectorBackend(detections=detections))
    try:
        result = service.run(Batch1Request(image_path=str(sharp_plant_image)))
        assert result.contains_plant
        assert result.localization is not None
        assert result.localization.bbox is not None
        image_width = result.metadata["loaded_image"]["width"]
        image_height = result.metadata["loaded_image"]["height"]
        assert result.localization.bbox.width >= int(image_width * batch1_config.cluster.min_final_roi_width_ratio)
        assert result.localization.bbox.height >= int(image_height * batch1_config.cluster.min_final_roi_height_ratio)
    finally:
        service.close()


def test_dense_scene_small_cluster_fallback_rescues_roi(batch1_config, sharp_plant_image):
    detections = [
        DetectionBox(bbox=BoundingBox(x_min=300, y_min=220, x_max=345, y_max=300), confidence=0.82, label="leaf"),
    ]
    batch1_config.cluster.min_cluster_area_ratio = 0.03
    batch1_config.cluster.dense_scene_fallback_min_vegetation_fraction = 0.10
    service = Batch1Service(batch1_config, detector_backend=MockDetectorBackend(detections=detections))
    try:
        result = service.run(Batch1Request(image_path=str(sharp_plant_image)))
        assert result.valid
        assert result.contains_plant
        assert result.localization is not None
        assert result.localization.bbox is not None
        image_width = result.metadata["loaded_image"]["width"]
        image_height = result.metadata["loaded_image"]["height"]
        assert result.localization.bbox.width >= int(image_width * batch1_config.cluster.min_final_roi_width_ratio)
        assert result.localization.bbox.height >= int(image_height * batch1_config.cluster.min_final_roi_height_ratio)
    finally:
        service.close()
