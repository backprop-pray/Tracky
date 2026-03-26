from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np


@dataclass
class BrightnessMetrics:
    brightness_mean: float
    dark_fraction: float
    bright_fraction: float


@dataclass
class VegetationMetrics:
    vegetation_fraction: float
    central_vegetation_fraction: float
    mask: np.ndarray


def blur_score(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def motion_ratio(gray: np.ndarray) -> float:
    sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    energy_x = float(np.mean(np.abs(sobel_x))) + 1e-6
    energy_y = float(np.mean(np.abs(sobel_y))) + 1e-6
    ratio = energy_x / energy_y
    return ratio if ratio >= 1.0 else 1.0 / ratio


def brightness_metrics(gray: np.ndarray) -> BrightnessMetrics:
    return BrightnessMetrics(
        brightness_mean=float(gray.mean()),
        dark_fraction=float(np.mean(gray < 25)),
        bright_fraction=float(np.mean(gray > 245)),
    )


def vegetation_metrics(image_bgr: np.ndarray) -> VegetationMetrics:
    hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
    lower = np.array([25, 40, 20], dtype=np.uint8)
    upper = np.array([95, 255, 255], dtype=np.uint8)
    hsv_mask = cv2.inRange(hsv, lower, upper)

    b, g, r = cv2.split(image_bgr.astype(np.float32))
    exg = 2 * g - r - b
    exg_mask = (exg > 15).astype(np.uint8) * 255

    mask = cv2.bitwise_and(hsv_mask, exg_mask)
    kernel = np.ones((5, 5), dtype=np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    vegetation_fraction = float(np.count_nonzero(mask)) / float(mask.size)
    h, w = mask.shape
    y0, y1 = int(h * 0.25), int(h * 0.75)
    x0, x1 = int(w * 0.25), int(w * 0.75)
    center = mask[y0:y1, x0:x1]
    central = float(np.count_nonzero(center)) / float(center.size)
    return VegetationMetrics(
        vegetation_fraction=vegetation_fraction,
        central_vegetation_fraction=central,
        mask=mask,
    )
