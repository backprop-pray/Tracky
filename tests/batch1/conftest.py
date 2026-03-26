from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from plant_pipeline.config.settings import load_batch1_settings
from plant_pipeline.schemas.batch1 import BoundingBox, DetectionBox


def _write_image(path: Path, image: np.ndarray) -> Path:
    cv2.imwrite(str(path), image)
    return path


@pytest.fixture
def batch1_config(tmp_path: Path):
    config = load_batch1_settings()
    config.batch1.output_root = str(tmp_path / "batch1-output")
    config.detector_batch1.backend = "mock"
    return config


@pytest.fixture
def sharp_plant_image(tmp_path: Path) -> Path:
    image = np.full((900, 1200, 3), (55, 75, 105), dtype=np.uint8)
    cv2.ellipse(image, (600, 450), (190, 260), 0, 0, 360, (45, 180, 45), thickness=-1)
    cv2.ellipse(image, (510, 450), (80, 170), 20, 0, 360, (60, 205, 60), thickness=-1)
    cv2.ellipse(image, (690, 450), (80, 170), -20, 0, 360, (60, 205, 60), thickness=-1)
    cv2.line(image, (600, 180), (600, 700), (35, 120, 35), thickness=5)
    rng = np.random.default_rng(9)
    noise = rng.integers(-18, 19, size=image.shape, dtype=np.int16)
    image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return _write_image(tmp_path / "sharp_plant.png", image)


@pytest.fixture
def blurry_plant_image(tmp_path: Path, sharp_plant_image: Path) -> Path:
    image = cv2.imread(str(sharp_plant_image))
    blurred = cv2.GaussianBlur(image, (31, 31), 0)
    return _write_image(tmp_path / "blurred_plant.png", blurred)


@pytest.fixture
def dark_image(tmp_path: Path, sharp_plant_image: Path) -> Path:
    image = cv2.imread(str(sharp_plant_image))
    dark = (image * 0.12).astype(np.uint8)
    return _write_image(tmp_path / "dark.png", dark)


@pytest.fixture
def overexposed_image(tmp_path: Path, sharp_plant_image: Path) -> Path:
    image = cv2.imread(str(sharp_plant_image))
    over = np.clip(image.astype(np.int16) + 170, 0, 255).astype(np.uint8)
    return _write_image(tmp_path / "over.png", over)


@pytest.fixture
def yellow_plant_image(tmp_path: Path, sharp_plant_image: Path) -> Path:
    image = cv2.imread(str(sharp_plant_image))
    image[:, :, 1] = np.clip(image[:, :, 1] * 0.9, 0, 255).astype(np.uint8)
    image[:, :, 2] = np.clip(image[:, :, 2] + 40, 0, 255).astype(np.uint8)
    return _write_image(tmp_path / "yellow.png", image)


@pytest.fixture
def motion_blur_image(tmp_path: Path, sharp_plant_image: Path) -> Path:
    image = cv2.imread(str(sharp_plant_image))
    kernel = np.zeros((1, 35), dtype=np.float32)
    kernel[0, :] = 1.0 / 35.0
    blurred = cv2.filter2D(image, -1, kernel)
    return _write_image(tmp_path / "motion_blur.png", blurred)


@pytest.fixture
def soil_image(tmp_path: Path) -> Path:
    image = np.full((900, 1200, 3), (95, 110, 135), dtype=np.uint8)
    rng = np.random.default_rng(13)
    noise = rng.integers(-12, 13, size=image.shape, dtype=np.int16)
    image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    return _write_image(tmp_path / "soil.png", image)


@pytest.fixture
def dense_leaf_detections() -> list[DetectionBox]:
    return [
        DetectionBox(bbox=BoundingBox(x_min=220, y_min=120, x_max=330, y_max=320), confidence=0.72, label="leaf"),
        DetectionBox(bbox=BoundingBox(x_min=300, y_min=150, x_max=420, y_max=340), confidence=0.83, label="leaf"),
        DetectionBox(bbox=BoundingBox(x_min=380, y_min=180, x_max=500, y_max=360), confidence=0.78, label="leaf"),
    ]
