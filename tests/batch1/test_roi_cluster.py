from __future__ import annotations

from plant_pipeline.roi.cluster import cluster_detections, union_bbox
from plant_pipeline.schemas.batch1 import BoundingBox, DetectionBox


def test_merges_overlapping_boxes(batch1_config):
    detections = [
        DetectionBox(bbox=BoundingBox(x_min=10, y_min=10, x_max=60, y_max=60), confidence=0.8, label="leaf"),
        DetectionBox(bbox=BoundingBox(x_min=40, y_min=30, x_max=90, y_max=80), confidence=0.7, label="leaf"),
    ]
    clusters = cluster_detections(detections, (200, 200, 3), batch1_config.cluster)
    assert len(clusters) == 1


def test_merges_nearby_boxes_without_overlap(batch1_config):
    detections = [
        DetectionBox(bbox=BoundingBox(x_min=100, y_min=100, x_max=140, y_max=140), confidence=0.8, label="leaf"),
        DetectionBox(bbox=BoundingBox(x_min=145, y_min=100, x_max=185, y_max=140), confidence=0.7, label="leaf"),
    ]
    clusters = cluster_detections(detections, (500, 500, 3), batch1_config.cluster)
    assert len(clusters) == 1


def test_keeps_far_boxes_separate(batch1_config):
    detections = [
        DetectionBox(bbox=BoundingBox(x_min=10, y_min=10, x_max=60, y_max=60), confidence=0.8, label="leaf"),
        DetectionBox(bbox=BoundingBox(x_min=300, y_min=300, x_max=360, y_max=360), confidence=0.7, label="leaf"),
    ]
    clusters = cluster_detections(detections, (500, 500, 3), batch1_config.cluster)
    assert len(clusters) == 2


def test_cluster_bbox_is_union_of_members():
    detections = [
        DetectionBox(bbox=BoundingBox(x_min=10, y_min=10, x_max=40, y_max=40), confidence=0.8, label="leaf"),
        DetectionBox(bbox=BoundingBox(x_min=25, y_min=20, x_max=70, y_max=90), confidence=0.7, label="leaf"),
    ]
    bbox = union_bbox(detections)
    assert bbox.x_min == 10
    assert bbox.y_min == 10
    assert bbox.x_max == 70
    assert bbox.y_max == 90
