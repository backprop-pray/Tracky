from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from plant_pipeline.config.settings import load_settings


@pytest.fixture
def settings(tmp_path: Path):
    settings = load_settings()
    settings.capture.simulate = True
    settings.storage.root_dir = str(tmp_path / "data")
    settings.storage.sqlite_path = str(tmp_path / "data" / "pipeline.db")
    settings.upload.enabled = False
    return settings


@pytest.fixture
def synthetic_plant_image(tmp_path: Path) -> Path:
    image = np.full((800, 1200, 3), (50, 70, 110), dtype=np.uint8)
    cv2.ellipse(image, (600, 420), (180, 260), 0, 0, 360, (40, 180, 40), thickness=-1)
    cv2.ellipse(image, (520, 430), (90, 140), 25, 0, 360, (55, 200, 55), thickness=-1)
    cv2.ellipse(image, (680, 430), (90, 140), -25, 0, 360, (55, 200, 55), thickness=-1)
    cv2.line(image, (600, 170), (600, 670), (25, 120, 25), thickness=5)
    for offset in range(-120, 140, 30):
        cv2.line(image, (600, 420), (600 + offset, 260), (35, 140, 35), thickness=3)
        cv2.line(image, (600, 420), (600 + offset, 580), (35, 140, 35), thickness=3)
    rng = np.random.default_rng(7)
    noise = rng.integers(-20, 21, size=image.shape, dtype=np.int16)
    image = np.clip(image.astype(np.int16) + noise, 0, 255).astype(np.uint8)
    path = tmp_path / "plant.jpg"
    cv2.imwrite(str(path), image)
    return path
