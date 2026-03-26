from __future__ import annotations

import math

from plant_pipeline.config.settings import Batch1ClusterSettings
from plant_pipeline.roi.cluster import normalized_edge_distance, union_bbox
from plant_pipeline.schemas.batch1 import BoundingBox, DetectionBox, RoiCluster


def _centrality_score(bbox: BoundingBox, image_shape: tuple[int, int, int]) -> float:
    h, w = image_shape[:2]
    image_cx = w / 2.0
    image_cy = h / 2.0
    bbox_cx = (bbox.x_min + bbox.x_max) / 2.0
    bbox_cy = (bbox.y_min + bbox.y_max) / 2.0
    dx = abs(bbox_cx - image_cx) / max(w / 2.0, 1.0)
    dy = abs(bbox_cy - image_cy) / max(h / 2.0, 1.0)
    return max(0.0, 1.0 - ((dx * dx + dy * dy) ** 0.5))


def _normalize(value: float, values: list[float]) -> float:
    if not values:
        return 0.0
    low = min(values)
    high = max(values)
    if high == low:
        return 1.0 if value > 0 else 0.0
    return (value - low) / (high - low)


def _border_touch_count(bbox: BoundingBox, image_shape: tuple[int, int, int], margin_ratio: float) -> int:
    h, w = image_shape[:2]
    margin_x = w * margin_ratio
    margin_y = h * margin_ratio
    return sum(
        [
            bbox.x_min <= margin_x,
            bbox.y_min <= margin_y,
            bbox.x_max >= w - margin_x,
            bbox.y_max >= h - margin_y,
        ]
    )


def _oversized_cluster_penalty(
    coverage: float,
    border_touch_count: int,
    settings: Batch1ClusterSettings,
) -> float:
    if coverage <= settings.oversized_cluster_penalty_start:
        coverage_penalty = 0.0
    else:
        coverage_penalty = (coverage - settings.oversized_cluster_penalty_start) / max(
            1.0 - settings.oversized_cluster_penalty_start,
            1e-6,
        )
    return (
        settings.oversized_cluster_penalty_weight * coverage_penalty
        + settings.border_touch_penalty_weight * (border_touch_count / 4.0)
    )


def score_clusters(
    clustered: list[list[DetectionBox]],
    image_shape: tuple[int, int, int],
    settings: Batch1ClusterSettings,
) -> list[RoiCluster]:
    h, w = image_shape[:2]
    image_area = float(h * w)
    raw = []
    for cluster_id, members in enumerate(clustered):
        bbox = union_bbox(members)
        sum_conf = sum(member.confidence for member in members)
        mean_conf = sum_conf / len(members)
        coverage = bbox.area / image_area if image_area else 0.0
        centrality = _centrality_score(bbox, image_shape)
        border_touch_count = _border_touch_count(bbox, image_shape, settings.border_touch_margin_ratio)
        raw.append((cluster_id, members, bbox, sum_conf, mean_conf, coverage, centrality, border_touch_count))

    sum_values = [item[3] for item in raw]
    area_values = [item[5] for item in raw]

    clusters: list[RoiCluster] = []
    for cluster_id, members, bbox, sum_conf, mean_conf, coverage, centrality, border_touch_count in raw:
        base_score = (
            settings.score_weight_confidence * _normalize(sum_conf, sum_values)
            + settings.score_weight_area * _normalize(coverage, area_values)
            + settings.score_weight_centrality * centrality
        )
        cluster_score = max(
            0.0,
            base_score - _oversized_cluster_penalty(coverage, border_touch_count, settings),
        )
        clusters.append(
            RoiCluster(
                cluster_id=cluster_id,
                member_count=len(members),
                bbox=bbox,
                sum_confidence=sum_conf,
                mean_confidence=mean_conf,
                coverage_ratio=coverage,
                centrality_score=centrality,
                cluster_score=cluster_score,
            )
        )
    return sorted(clusters, key=lambda item: item.cluster_score, reverse=True)


def select_best_cluster(clusters: list[RoiCluster], settings: Batch1ClusterSettings) -> RoiCluster | None:
    if not clusters:
        return None
    top = clusters[0]
    if top.member_count < settings.min_cluster_members:
        return None
    if top.coverage_ratio < settings.min_cluster_area_ratio:
        return None
    return top


def expand_and_clip_bbox(
    bbox: BoundingBox,
    image_shape: tuple[int, int, int],
    expand_ratio: float,
) -> BoundingBox:
    h, w = image_shape[:2]
    pad_x = int(bbox.width * expand_ratio)
    pad_y = int(bbox.height * expand_ratio)
    return BoundingBox(
        x_min=max(0, bbox.x_min - pad_x),
        y_min=max(0, bbox.y_min - pad_y),
        x_max=min(w, bbox.x_max + pad_x),
        y_max=min(h, bbox.y_max + pad_y),
    )


def gather_single_detection_context(
    selected_cluster: RoiCluster,
    detections: list[DetectionBox],
    image_shape: tuple[int, int, int],
    settings: Batch1ClusterSettings,
) -> BoundingBox:
    if selected_cluster.member_count > 1:
        return selected_cluster.bbox

    nearby = [
        detection
        for detection in detections
        if normalized_edge_distance(detection.bbox, selected_cluster.bbox, image_shape)
        <= settings.single_detection_context_distance_ratio
    ]
    if len(nearby) <= 1:
        return selected_cluster.bbox
    return union_bbox(nearby)


def ensure_minimum_roi_size(
    bbox: BoundingBox,
    image_shape: tuple[int, int, int],
    min_width_ratio: float,
    min_height_ratio: float,
) -> BoundingBox:
    h, w = image_shape[:2]
    target_w = min(w, max(bbox.width, int(math.ceil(w * min_width_ratio))))
    target_h = min(h, max(bbox.height, int(math.ceil(h * min_height_ratio))))
    center_x = (bbox.x_min + bbox.x_max) / 2.0
    center_y = (bbox.y_min + bbox.y_max) / 2.0

    x_min = int(round(center_x - target_w / 2.0))
    y_min = int(round(center_y - target_h / 2.0))
    x_max = x_min + target_w
    y_max = y_min + target_h

    if x_min < 0:
        x_max -= x_min
        x_min = 0
    if y_min < 0:
        y_max -= y_min
        y_min = 0
    if x_max > w:
        shift = x_max - w
        x_min = max(0, x_min - shift)
        x_max = w
    if y_max > h:
        shift = y_max - h
        y_min = max(0, y_min - shift)
        y_max = h

    return BoundingBox(x_min=x_min, y_min=y_min, x_max=x_max, y_max=y_max)
