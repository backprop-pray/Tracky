from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from plant_pipeline.schemas.batch1 import BoundingBox, DetectionBox, RoiCluster


def write_roi(image_bgr: np.ndarray, bbox: BoundingBox, output_path: Path) -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    roi = image_bgr[bbox.y_min : bbox.y_max, bbox.x_min : bbox.x_max]
    cv2.imwrite(str(output_path), roi)
    return str(output_path)


def write_overlay(
    image_bgr: np.ndarray,
    detections: list[DetectionBox],
    selected_cluster: RoiCluster | None,
    output_path: Path,
) -> str:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    overlay = image_bgr.copy()
    for detection in detections:
        cv2.rectangle(
            overlay,
            (detection.bbox.x_min, detection.bbox.y_min),
            (detection.bbox.x_max, detection.bbox.y_max),
            (255, 180, 0),
            2,
        )
    if selected_cluster is not None:
        bbox = selected_cluster.bbox
        cv2.rectangle(overlay, (bbox.x_min, bbox.y_min), (bbox.x_max, bbox.y_max), (0, 255, 0), 3)
    cv2.imwrite(str(output_path), overlay)
    return str(output_path)
