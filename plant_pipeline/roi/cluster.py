from __future__ import annotations

from collections import defaultdict

from plant_pipeline.config.settings import Batch1ClusterSettings
from plant_pipeline.schemas.batch1 import BoundingBox, DetectionBox


def intersection_over_union(a: BoundingBox, b: BoundingBox) -> float:
    x1 = max(a.x_min, b.x_min)
    y1 = max(a.y_min, b.y_min)
    x2 = min(a.x_max, b.x_max)
    y2 = min(a.y_max, b.y_max)
    inter_w = max(0, x2 - x1)
    inter_h = max(0, y2 - y1)
    intersection = inter_w * inter_h
    if intersection == 0:
        return 0.0
    union = a.area + b.area - intersection
    return intersection / union if union else 0.0


def normalized_edge_distance(a: BoundingBox, b: BoundingBox, image_shape: tuple[int, int, int]) -> float:
    h, w = image_shape[:2]
    gap_x = max(0, max(a.x_min - b.x_max, b.x_min - a.x_max))
    gap_y = max(0, max(a.y_min - b.y_max, b.y_min - a.y_max))
    return ((gap_x**2 + gap_y**2) ** 0.5) / max(h, w)


def union_bbox(boxes: list[DetectionBox]) -> BoundingBox:
    return BoundingBox(
        x_min=min(item.bbox.x_min for item in boxes),
        y_min=min(item.bbox.y_min for item in boxes),
        x_max=max(item.bbox.x_max for item in boxes),
        y_max=max(item.bbox.y_max for item in boxes),
    )


def cluster_detections(
    detections: list[DetectionBox],
    image_shape: tuple[int, int, int],
    settings: Batch1ClusterSettings,
) -> list[list[DetectionBox]]:
    if not detections:
        return []
    graph: dict[int, set[int]] = defaultdict(set)
    for idx, left in enumerate(detections):
        for jdx in range(idx + 1, len(detections)):
            right = detections[jdx]
            if (
                intersection_over_union(left.bbox, right.bbox) >= settings.merge_iou_threshold
                or normalized_edge_distance(left.bbox, right.bbox, image_shape) <= settings.merge_distance_threshold
            ):
                graph[idx].add(jdx)
                graph[jdx].add(idx)

    clusters: list[list[DetectionBox]] = []
    visited: set[int] = set()
    for idx in range(len(detections)):
        if idx in visited:
            continue
        queue = [idx]
        component: list[DetectionBox] = []
        visited.add(idx)
        while queue:
            current = queue.pop()
            component.append(detections[current])
            for neighbor in graph[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)
        clusters.append(component)
    return clusters
