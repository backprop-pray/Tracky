from __future__ import annotations

from pathlib import Path
from typing import Optional, Protocol

import cv2
import numpy as np

from plant_pipeline.config.settings import DetectSettings
from plant_pipeline.quality.gate import build_vegetation_mask
from plant_pipeline.schemas.models import BoundingBox, PlantDetectionResult

try:
    import tflite_runtime.interpreter as tflite  # type: ignore
except ImportError:  # pragma: no cover
    tflite = None


class DetectorBackend(Protocol):
    def detect(self, image_bgr: np.ndarray) -> list[tuple[BoundingBox, float]]:
        ...


class TFLiteEfficientDetBackend:
    def __init__(self, model_path: str) -> None:
        if tflite is None:
            raise RuntimeError("tflite_runtime is not installed.")
        self.interpreter = tflite.Interpreter(model_path=model_path)
        self.interpreter.allocate_tensors()
        self.input_details = self.interpreter.get_input_details()[0]
        self.output_details = self.interpreter.get_output_details()
        self.input_size = int(self.input_details["shape"][2])

    def detect(self, image_bgr: np.ndarray) -> list[tuple[BoundingBox, float]]:
        rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (self.input_size, self.input_size))
        tensor = np.expand_dims(resized, axis=0)
        if self.input_details["dtype"] == np.float32:
            tensor = tensor.astype(np.float32) / 255.0
        else:
            tensor = tensor.astype(self.input_details["dtype"])
        self.interpreter.set_tensor(self.input_details["index"], tensor)
        self.interpreter.invoke()

        boxes = self.interpreter.get_tensor(self.output_details[0]["index"])[0]
        classes = self.interpreter.get_tensor(self.output_details[1]["index"])[0]
        scores = self.interpreter.get_tensor(self.output_details[2]["index"])[0]
        count = int(self.interpreter.get_tensor(self.output_details[3]["index"])[0])

        height, width = image_bgr.shape[:2]
        results: list[tuple[BoundingBox, float]] = []
        for idx in range(count):
            if int(classes[idx]) != 0:
                continue
            y_min, x_min, y_max, x_max = boxes[idx]
            box = BoundingBox(
                x_min=max(0, int(x_min * width)),
                y_min=max(0, int(y_min * height)),
                x_max=min(width, int(x_max * width)),
                y_max=min(height, int(y_max * height)),
            )
            results.append((box, float(scores[idx])))
        return results


class VegetationFallbackDetector:
    """Heuristic fallback when no TFLite detector is available."""

    def detect(self, image_bgr: np.ndarray) -> list[tuple[BoundingBox, float]]:
        vegetation = build_vegetation_mask(image_bgr)
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(vegetation.mask, connectivity=8)
        candidates: list[tuple[BoundingBox, float]] = []
        image_area = image_bgr.shape[0] * image_bgr.shape[1]
        for idx in range(1, num_labels):
            x, y, w, h, area = stats[idx]
            if area < max(100, image_area * 0.01):
                continue
            score = min(0.8, area / image_area * 4.0)
            candidates.append((BoundingBox(x_min=int(x), y_min=int(y), x_max=int(x + w), y_max=int(y + h)), float(score)))
        candidates.sort(key=lambda item: item[1], reverse=True)
        return candidates


class PlantDetector:
    def __init__(self, settings: DetectSettings, backend: Optional[DetectorBackend] = None) -> None:
        self.settings = settings
        self.backend = backend or self._build_backend()

    def _build_backend(self) -> DetectorBackend:
        model_path = self.settings.model_path
        if model_path and Path(model_path).exists():
            return TFLiteEfficientDetBackend(model_path)
        return VegetationFallbackDetector()

    def detect(self, working_image_bgr: np.ndarray, full_image_bgr: np.ndarray, roi_path: str) -> PlantDetectionResult:
        vegetation = build_vegetation_mask(working_image_bgr)
        diagnostics = {
            "prefilter_fraction": vegetation.foreground_fraction,
            "central_foreground_fraction": vegetation.central_foreground_fraction,
        }
        if vegetation.foreground_fraction < self.settings.min_prefilter_fraction:
            return PlantDetectionResult(
                contains_plant=False,
                confidence=0.0,
                detector_model_version=self.settings.model_version,
                diagnostics=diagnostics,
            )

        detections = self.backend.detect(working_image_bgr)
        if detections:
            best_box, confidence = max(detections, key=lambda item: item[1])
            scaled = self._scale_bbox(best_box, working_image_bgr.shape, full_image_bgr.shape)
            expanded = self._expand_bbox(scaled, full_image_bgr.shape)
            if confidence >= self.settings.confidence_threshold:
                return PlantDetectionResult(
                    contains_plant=True,
                    confidence=confidence,
                    bbox=expanded,
                    roi_path=roi_path,
                    fallback_used=False,
                    detector_model_version=self.settings.model_version,
                    diagnostics=diagnostics,
                )
            if confidence >= self.settings.fallback_low_confidence and vegetation.central_foreground_fraction >= self.settings.centrality_threshold:
                return PlantDetectionResult(
                    contains_plant=True,
                    confidence=confidence,
                    bbox=expanded,
                    roi_path=roi_path,
                    fallback_used=True,
                    detector_model_version=self.settings.model_version,
                    diagnostics=diagnostics,
                )

        if vegetation.central_foreground_fraction >= self.settings.centrality_threshold:
            fallback_box = self._central_component_bbox(vegetation.mask, full_image_bgr.shape)
            if fallback_box is not None:
                return PlantDetectionResult(
                    contains_plant=True,
                    confidence=self.settings.fallback_low_confidence,
                    bbox=fallback_box,
                    roi_path=roi_path,
                    fallback_used=True,
                    detector_model_version=self.settings.model_version,
                    diagnostics=diagnostics,
                )

        return PlantDetectionResult(
            contains_plant=False,
            confidence=0.0,
            detector_model_version=self.settings.model_version,
            diagnostics=diagnostics,
        )

    def _scale_bbox(self, bbox: BoundingBox, working_shape: tuple[int, int, int], full_shape: tuple[int, int, int]) -> BoundingBox:
        work_h, work_w = working_shape[:2]
        full_h, full_w = full_shape[:2]
        scale_x = full_w / work_w
        scale_y = full_h / work_h
        return BoundingBox(
            x_min=int(bbox.x_min * scale_x),
            y_min=int(bbox.y_min * scale_y),
            x_max=int(bbox.x_max * scale_x),
            y_max=int(bbox.y_max * scale_y),
        )

    def _expand_bbox(self, bbox: BoundingBox, image_shape: tuple[int, int, int]) -> BoundingBox:
        height, width = image_shape[:2]
        pad_x = int(bbox.width * self.settings.bbox_expand_ratio)
        pad_y = int(bbox.height * self.settings.bbox_expand_ratio)
        return BoundingBox(
            x_min=max(0, bbox.x_min - pad_x),
            y_min=max(0, bbox.y_min - pad_y),
            x_max=min(width, bbox.x_max + pad_x),
            y_max=min(height, bbox.y_max + pad_y),
        )

    def _central_component_bbox(self, mask: np.ndarray, full_shape: tuple[int, int, int]) -> Optional[BoundingBox]:
        num_labels, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
        if num_labels <= 1:
            return None
        h, w = mask.shape
        cx, cy = w / 2.0, h / 2.0
        best_idx = None
        best_score = -1.0
        for idx in range(1, num_labels):
            x, y, bw, bh, area = stats[idx]
            component_cx = x + bw / 2.0
            component_cy = y + bh / 2.0
            distance = abs(component_cx - cx) / w + abs(component_cy - cy) / h
            score = area - distance * area
            if score > best_score:
                best_score = score
                best_idx = idx
        if best_idx is None:
            return None
        x, y, bw, bh, _ = stats[best_idx]
        work_box = BoundingBox(x_min=int(x), y_min=int(y), x_max=int(x + bw), y_max=int(y + bh))
        return self._expand_bbox(self._scale_bbox(work_box, (h, w, 3), full_shape), full_shape)
