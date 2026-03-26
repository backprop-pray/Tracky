from __future__ import annotations

import pytest

from plant_pipeline.detect.factory import build_detector_backend


def test_builds_mock_backend(batch1_config):
    backend = build_detector_backend(batch1_config.detector_batch1)
    assert backend.name == "mock"


def test_builds_ultralytics_backend(batch1_config):
    batch1_config.detector_batch1.backend = "ultralytics_leaf"
    batch1_config.detector_batch1.model_path = "/tmp/yolo11x_leaf.pt"
    backend = build_detector_backend(batch1_config.detector_batch1)
    assert backend.name == "ultralytics_leaf"


def test_unknown_backend_raises_error(batch1_config):
    batch1_config.detector_batch1.backend = "missing"
    with pytest.raises(ValueError):
        build_detector_backend(batch1_config.detector_batch1)


def test_backend_surfaces_license_tag(batch1_config):
    batch1_config.detector_batch1.backend = "ultralytics_leaf"
    batch1_config.detector_batch1.model_path = "/tmp/yolo11x_leaf.pt"
    backend = build_detector_backend(batch1_config.detector_batch1)
    assert backend.license_tag == "AGPL-3.0-or-commercial"
