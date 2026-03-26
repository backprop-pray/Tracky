from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

from plant_pipeline.config.settings import Batch1Config, Batch1Settings, load_batch1_settings
from plant_pipeline.detect.base import DetectorBackend
from plant_pipeline.detect.factory import build_detector_backend
from plant_pipeline.quality.gate import Batch1QualityGate
from plant_pipeline.roi.cluster import cluster_detections
from plant_pipeline.roi.crop import write_overlay, write_roi
from plant_pipeline.roi.select import (
    ensure_minimum_roi_size,
    expand_and_clip_bbox,
    gather_single_detection_context,
    score_clusters,
    select_best_cluster,
)
from plant_pipeline.schemas.batch1 import (
    Batch1PlantResult,
    Batch1Request,
    DetectorInfo,
    DetectorResult,
    LoadedImageMeta,
    PlantLocalizationResult,
    QualityDiagnostics,
    QualityResult,
)


class Batch1Service:
    def __init__(
        self,
        config: Batch1Config,
        detector_backend: Optional[DetectorBackend] = None,
    ) -> None:
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.output_root = Path(config.batch1.output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.quality_gate = Batch1QualityGate(config.quality_batch1)
        self.detector = detector_backend or build_detector_backend(config.detector_batch1)
        self.detector.load()
        self.logger.info(
            "Batch1 detector backend=%s model=%s license=%s note=%s",
            self.detector.name,
            self.detector.model_name,
            self.detector.license_tag,
            config.detector_batch1.licensing_note,
        )

    def run(self, request: Batch1Request) -> Batch1PlantResult:
        image_id = request.image_id or uuid.uuid4().hex
        loaded = self._load_image(request.image_path, image_id)
        if loaded is None:
            quality = QualityResult(
                is_valid=False,
                reject_reason="image_read_error",
                diagnostics=QualityDiagnostics(
                    blur_score=0.0,
                    motion_ratio=0.0,
                    brightness_mean=0.0,
                    dark_fraction=0.0,
                    bright_fraction=0.0,
                ),
            )
            return Batch1PlantResult(
                image_id=image_id,
                image_path=request.image_path,
                valid=False,
                reject_reason="image_read_error",
                contains_plant=False,
                quality=quality,
                metadata={"load_error": f"Unable to read image at {request.image_path}", **request.metadata},
            )

        image_meta, full_image = loaded
        working = cv2.resize(full_image, (self.config.batch1.working_size, self.config.batch1.working_size))
        quality = self.quality_gate.evaluate(working)
        if not quality.is_valid:
            return Batch1PlantResult(
                image_id=image_id,
                image_path=request.image_path,
                valid=False,
                reject_reason=quality.reject_reason,
                contains_plant=False,
                quality=quality,
                metadata={**request.metadata, "loaded_image": image_meta.model_dump(mode="json")},
            )

        raw = self.detector.detect(working)
        filtered = [
            item
            for item in raw
            if item.confidence >= self.config.detector_batch1.min_confidence
            and item.label in self.config.detector_batch1.allowed_labels
        ]
        detector_info = DetectorInfo(
            backend_name=self.detector.name,
            model_name=self.detector.model_name,
            license_tag=self.detector.license_tag,
            runtime_device=self.detector.device,
        )
        detector_result = DetectorResult(info=detector_info, raw_detections=raw, filtered_detections=filtered)
        if not filtered:
            localization = PlantLocalizationResult(
                contains_plant=False,
                detector_confidence=0.0,
                detector_info=detector_info,
            )
            return Batch1PlantResult(
                image_id=image_id,
                image_path=request.image_path,
                valid=True,
                contains_plant=False,
                quality=quality,
                detector=detector_result,
                localization=localization,
                metadata={**request.metadata, "loaded_image": image_meta.model_dump(mode="json")},
            )

        clusters = cluster_detections(filtered, working.shape, self.config.cluster)
        scored_clusters = score_clusters(clusters, working.shape, self.config.cluster)
        selected = select_best_cluster(scored_clusters, self.config.cluster)
        selected_via_fallback = False
        if selected is None:
            selected = self._fallback_small_cluster(scored_clusters, quality)
            selected_via_fallback = selected is not None
        if selected is None:
            localization = PlantLocalizationResult(
                contains_plant=False,
                detector_confidence=0.0,
                candidate_clusters=self._scale_clusters(scored_clusters, working.shape, full_image.shape),
                detector_info=detector_info,
            )
            return Batch1PlantResult(
                image_id=image_id,
                image_path=request.image_path,
                valid=True,
                contains_plant=False,
                quality=quality,
                detector=detector_result,
                localization=localization,
                metadata={**request.metadata, "loaded_image": image_meta.model_dump(mode="json")},
            )

        context_bbox = (
            selected.bbox
            if selected_via_fallback and selected.member_count == 1
            else gather_single_detection_context(selected, filtered, working.shape, self.config.cluster)
        )
        scaled = self._scale_bbox(context_bbox, working.shape, full_image.shape)
        expand_ratio = (
            self.config.cluster.single_detection_expand_ratio
            if selected.member_count == 1
            else self.config.cluster.bbox_expand_ratio
        )
        final_bbox = expand_and_clip_bbox(scaled, full_image.shape, expand_ratio)
        final_bbox = ensure_minimum_roi_size(
            final_bbox,
            full_image.shape,
            self.config.cluster.min_final_roi_width_ratio,
            self.config.cluster.min_final_roi_height_ratio,
        )
        scaled_clusters = self._scale_clusters(scored_clusters, working.shape, full_image.shape)
        selected_cluster = next((item for item in scaled_clusters if item.cluster_id == selected.cluster_id), None)
        if self._is_obvious_false_positive(final_bbox, selected, quality):
            localization = PlantLocalizationResult(
                contains_plant=False,
                detector_confidence=0.0,
                candidate_clusters=scaled_clusters,
                detector_info=detector_info,
            )
            return Batch1PlantResult(
                image_id=image_id,
                image_path=request.image_path,
                valid=True,
                contains_plant=False,
                quality=quality,
                detector=detector_result,
                localization=localization,
                metadata={**request.metadata, "loaded_image": image_meta.model_dump(mode="json"), "detector_sanity_reject": "single_full_frame_low_vegetation"},
            )

        image_dir = self.output_root / image_id
        artifacts: dict[str, str] = {}
        roi_path = None
        if self.config.batch1.write_roi:
            roi_path = write_roi(full_image, final_bbox, image_dir / f"roi.{self.config.batch1.roi_format}")
            artifacts["roi_path"] = roi_path
        if self.config.batch1.debug_overlays:
            overlay_path = write_overlay(full_image, self._scale_detections(filtered, working.shape, full_image.shape), selected, image_dir / "overlay.png")
            artifacts["overlay_path"] = overlay_path

        localization = PlantLocalizationResult(
            contains_plant=True,
            detector_confidence=selected.mean_confidence,
            bbox=final_bbox,
            roi_path=roi_path,
            selected_cluster=selected_cluster,
            candidate_clusters=scaled_clusters,
            detector_info=detector_info,
        )
        return Batch1PlantResult(
            image_id=image_id,
            image_path=request.image_path,
            valid=True,
            contains_plant=True,
            quality=quality,
            detector=detector_result,
            localization=localization,
            artifacts=artifacts,
            metadata={**request.metadata, "loaded_image": image_meta.model_dump(mode="json")},
        )

    def close(self) -> None:
        self.detector.close()

    def _load_image(self, image_path: str, image_id: str) -> Optional[tuple[LoadedImageMeta, np.ndarray]]:
        image = cv2.imread(image_path)
        if image is None:
            return None
        h, w = image.shape[:2]
        return LoadedImageMeta(image_id=image_id, image_path=image_path, width=w, height=h), image

    def _scale_bbox(self, bbox, working_shape, full_shape):
        work_h, work_w = working_shape[:2]
        full_h, full_w = full_shape[:2]
        return bbox.model_copy(
            update={
                "x_min": int(bbox.x_min * full_w / work_w),
                "y_min": int(bbox.y_min * full_h / work_h),
                "x_max": int(bbox.x_max * full_w / work_w),
                "y_max": int(bbox.y_max * full_h / work_h),
            }
        )

    def _scale_detections(self, detections, working_shape, full_shape):
        scaled = []
        for detection in detections:
            scaled.append(detection.model_copy(update={"bbox": self._scale_bbox(detection.bbox, working_shape, full_shape)}))
        return scaled

    def _scale_clusters(self, clusters, working_shape, full_shape):
        scaled = []
        for cluster in clusters:
            scaled.append(cluster.model_copy(update={"bbox": self._scale_bbox(cluster.bbox, working_shape, full_shape)}))
        return scaled

    def _is_obvious_false_positive(self, final_bbox, selected_cluster, quality: QualityResult) -> bool:
        vegetation_fraction = quality.diagnostics.vegetation_fraction
        if vegetation_fraction is None:
            return False
        frame_coverage = selected_cluster.coverage_ratio
        return (
            selected_cluster.member_count == 1
            and frame_coverage >= 0.95
            and vegetation_fraction < 0.01
        )

    def _fallback_small_cluster(self, clusters, quality: QualityResult):
        vegetation_fraction = quality.diagnostics.vegetation_fraction or 0.0
        central_vegetation_fraction = quality.diagnostics.central_vegetation_fraction or 0.0
        scene_vegetation = max(vegetation_fraction, central_vegetation_fraction)
        if scene_vegetation < self.config.cluster.dense_scene_fallback_min_vegetation_fraction:
            return None
        for cluster in clusters:
            if cluster.mean_confidence < self.config.cluster.small_cluster_fallback_min_mean_confidence:
                continue
            if cluster.cluster_score < self.config.cluster.small_cluster_fallback_min_score:
                continue
            return cluster
        return None


def build_batch1_service(config_path: str | None = None) -> Batch1Service:
    return Batch1Service(load_batch1_settings(config_path))
