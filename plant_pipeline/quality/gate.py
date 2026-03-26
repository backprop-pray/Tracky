from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import cv2
import numpy as np

from plant_pipeline.config.settings import Batch1QualitySettings, QualitySettings
from plant_pipeline.quality.metrics import brightness_metrics, blur_score, motion_ratio, vegetation_metrics
from plant_pipeline.schemas.batch1 import QualityDiagnostics as Batch1QualityDiagnostics
from plant_pipeline.schemas.batch1 import QualityResult as Batch1QualityResult
from plant_pipeline.schemas.models import QualityResult


@dataclass
class VegetationMaskResult:
    mask: np.ndarray
    foreground_fraction: float
    central_foreground_fraction: float


def build_vegetation_mask(image_bgr: np.ndarray) -> VegetationMaskResult:
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

    foreground_fraction = float(np.count_nonzero(mask)) / float(mask.size)
    h, w = mask.shape
    y0, y1 = int(h * 0.25), int(h * 0.75)
    x0, x1 = int(w * 0.25), int(w * 0.75)
    central = mask[y0:y1, x0:x1]
    central_fraction = float(np.count_nonzero(central)) / float(central.size)
    return VegetationMaskResult(mask=mask, foreground_fraction=foreground_fraction, central_foreground_fraction=central_fraction)


class QualityGate:
    def __init__(self, settings: QualitySettings) -> None:
        self.settings = settings

    def evaluate(self, image_bgr: np.ndarray) -> QualityResult:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())

        sobel_x = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
        energy_x = float(np.mean(np.abs(sobel_x))) + 1e-6
        energy_y = float(np.mean(np.abs(sobel_y))) + 1e-6
        motion_ratio = energy_x / energy_y

        brightness = float(gray.mean())
        dark_fraction = float(np.mean(gray < 25))
        bright_fraction = float(np.mean(gray > 245))

        vegetation = build_vegetation_mask(image_bgr)

        reject_reason: Optional[str] = None
        if blur_score < self.settings.min_blur_score:
            reject_reason = "blur"
        elif motion_ratio < self.settings.min_motion_ratio or motion_ratio > self.settings.max_motion_ratio:
            reject_reason = "motion_blur"
        elif brightness < self.settings.min_brightness or dark_fraction > self.settings.max_dark_fraction:
            reject_reason = "underexposed"
        elif brightness > self.settings.max_brightness or bright_fraction > self.settings.max_bright_fraction:
            reject_reason = "overexposed"
        elif vegetation.foreground_fraction < self.settings.min_foreground_fraction:
            reject_reason = "too_little_foreground"

        diagnostics = {
            "dark_fraction": dark_fraction,
            "bright_fraction": bright_fraction,
            "central_foreground_fraction": vegetation.central_foreground_fraction,
        }

        return QualityResult(
            is_valid=reject_reason is None,
            blur_score=blur_score,
            motion_blur_score=motion_ratio,
            brightness_score=brightness,
            foreground_score=vegetation.foreground_fraction,
            reject_reason=reject_reason,
            diagnostics=diagnostics,
        )


class Batch1QualityGate:
    def __init__(self, settings: Batch1QualitySettings) -> None:
        self.settings = settings

    def evaluate(self, image_bgr: np.ndarray) -> Batch1QualityResult:
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)
        blur = blur_score(gray)
        motion = motion_ratio(gray)
        brightness = brightness_metrics(gray)

        vegetation = vegetation_metrics(image_bgr) if self.settings.compute_vegetation_metrics else None
        reject_reason: Optional[str] = None
        if brightness.brightness_mean < self.settings.min_brightness or brightness.dark_fraction > self.settings.max_dark_fraction:
            reject_reason = "underexposed"
        elif brightness.brightness_mean > self.settings.max_brightness or brightness.bright_fraction > self.settings.max_bright_fraction:
            reject_reason = "overexposed"
        elif motion < self.settings.min_motion_ratio or motion > self.settings.max_motion_ratio:
            reject_reason = "motion_blur"
        elif blur < self.settings.min_blur_score and motion >= max(1.75, self.settings.max_motion_ratio / 3.0):
            reject_reason = "motion_blur"
        elif blur < self.settings.min_blur_score:
            reject_reason = "blur"
        elif self.settings.reject_on_vegetation_fraction and vegetation is not None and vegetation.vegetation_fraction <= 0.0:
            reject_reason = "too_little_foreground"

        diagnostics = Batch1QualityDiagnostics(
            blur_score=blur,
            motion_ratio=motion,
            brightness_mean=brightness.brightness_mean,
            dark_fraction=brightness.dark_fraction,
            bright_fraction=brightness.bright_fraction,
            vegetation_fraction=vegetation.vegetation_fraction if vegetation is not None else None,
            central_vegetation_fraction=vegetation.central_vegetation_fraction if vegetation is not None else None,
        )
        return Batch1QualityResult(is_valid=reject_reason is None, reject_reason=reject_reason, diagnostics=diagnostics)
