from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import cv2

from plant_pipeline.anomaly.patchcore import PatchCoreScorer
from plant_pipeline.capture.camera import PlantCamera
from plant_pipeline.compress.artifacts import ArtifactGenerator
from plant_pipeline.config.settings import PipelineSettings
from plant_pipeline.detect.tflite_detector import PlantDetector
from plant_pipeline.quality.gate import QualityGate
from plant_pipeline.schemas.models import (
    CaptureRequest,
    FinalInspectionRecord,
    SyncSummary,
    UploadStatus,
)
from plant_pipeline.services.lora import LoraNotifier
from plant_pipeline.storage.filesystem import PipelinePaths
from plant_pipeline.storage.sqlite_store import SQLiteStore
from plant_pipeline.upload.client import UploadClient


class PlantInspectionPipeline:
    def __init__(
        self,
        settings: PipelineSettings,
        camera: Optional[PlantCamera] = None,
        quality_gate: Optional[QualityGate] = None,
        detector: Optional[PlantDetector] = None,
        anomaly_scorer: Optional[PatchCoreScorer] = None,
        artifact_generator: Optional[ArtifactGenerator] = None,
        store: Optional[SQLiteStore] = None,
        upload_client: Optional[UploadClient] = None,
        lora_notifier: Optional[LoraNotifier] = None,
    ) -> None:
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.paths = PipelinePaths(settings.storage.root_dir)
        self.paths.ensure_root()
        self.camera = camera or PlantCamera(
            image_format=settings.capture.image_format,
            simulate=settings.capture.simulate,
        )
        self.quality_gate = quality_gate or QualityGate(settings.quality)
        self.detector = detector or PlantDetector(settings.detect)
        self.anomaly_scorer = anomaly_scorer or PatchCoreScorer(settings.anomaly)
        self.artifact_generator = artifact_generator or ArtifactGenerator(settings.compression)
        self.store = store or SQLiteStore(settings.storage.sqlite_path)
        self.upload_client = upload_client or UploadClient(settings.upload)
        self.lora_notifier = lora_notifier or LoraNotifier(settings.lora.enabled)

    def run_inspection(self, capture_request: CaptureRequest) -> FinalInspectionRecord:
        temp_timestamp = datetime.now(timezone.utc)
        temp_dir = self.paths.inspection_dir(temp_timestamp, "capture_tmp")
        captured = self.camera.capture(capture_request, temp_dir)
        inspection_dir = self.paths.inspection_dir(captured.timestamp, captured.image_id)
        source_path = Path(captured.path_full)
        target_path = inspection_dir / source_path.name
        if source_path != target_path:
            source_path.replace(target_path)
        captured.path_full = str(target_path)
        (inspection_dir / "metadata.json").write_text(json.dumps(captured.model_dump(mode="json"), indent=2))

        full_image = cv2.imread(captured.path_full)
        if full_image is None:
            raise RuntimeError(f"Failed to read captured image at {captured.path_full}")
        working = cv2.resize(full_image, (self.settings.capture.working_size, self.settings.capture.working_size))

        quality = self.quality_gate.evaluate(working)
        if not quality.is_valid:
            artifacts = self.artifact_generator.generate(captured.path_full, None, inspection_dir / "artifacts")
            record = FinalInspectionRecord(
                image_id=captured.image_id,
                timestamp=captured.timestamp,
                mission_id=captured.mission_id,
                valid=False,
                contains_plant=False,
                suspicious=False,
                suspicion_label="invalid",
                suspicious_score=0.0,
                detector_confidence=0.0,
                upload_status=UploadStatus.PENDING,
                artifact_paths={
                    "full": captured.path_full,
                    "thumbnail": artifacts.thumbnail_path,
                    "review": artifacts.review_image_path,
                    "roi": artifacts.roi_path,
                },
                metadata_blob={
                    "capture": captured.model_dump(mode="json"),
                    "quality": quality.model_dump(mode="json"),
                },
            )
            self.store.save_inspection(record, artifacts, self.settings.detect.model_version, self.settings.anomaly.model_version)
            return record

        roi_target = inspection_dir / "roi-source.png"
        detection = self.detector.detect(working, full_image, str(roi_target))

        suspicion_label = "not_applicable"
        suspicious_score = 0.0
        suspicious = False
        suspicion_meta = None
        if detection.contains_plant and detection.bbox is not None:
            roi = full_image[detection.bbox.y_min : detection.bbox.y_max, detection.bbox.x_min : detection.bbox.x_max]
            cv2.imwrite(str(roi_target), roi)
            suspicion = self.anomaly_scorer.score(roi)
            suspicion_label = suspicion.label
            suspicious_score = suspicion.suspicious_score
            suspicious = suspicion.label == "suspicious"
            suspicion_meta = suspicion.model_dump(mode="json")

        artifacts = self.artifact_generator.generate(captured.path_full, detection.bbox, inspection_dir / "artifacts")
        record = FinalInspectionRecord(
            image_id=captured.image_id,
            timestamp=captured.timestamp,
            mission_id=captured.mission_id,
            valid=True,
            contains_plant=detection.contains_plant,
            suspicious=suspicious,
            suspicion_label=suspicion_label,
            suspicious_score=suspicious_score,
            detector_confidence=detection.confidence,
            upload_status=UploadStatus.PENDING,
            artifact_paths={
                "full": captured.path_full,
                "thumbnail": artifacts.thumbnail_path,
                "review": artifacts.review_image_path,
                "roi": artifacts.roi_path,
            },
            metadata_blob={
                "capture": captured.model_dump(mode="json"),
                "quality": quality.model_dump(mode="json"),
                "detection": detection.model_dump(mode="json"),
                "suspicion": suspicion_meta,
            },
        )
        self.store.save_inspection(record, artifacts, detection.detector_model_version, self.settings.anomaly.model_version)
        self.lora_notifier.emit_lora_alert(record)
        return record

    def retry_pending_uploads(self) -> SyncSummary:
        summary = SyncSummary()
        if not self.settings.upload.enabled:
            return summary
        if not self.upload_client.wifi_available():
            self.logger.info("Wi-Fi unavailable; skipping upload retry.")
            return summary
        for row in self.store.list_pending_uploads():
            summary.attempted += 1
            payload = {
                "image_id": row["image_id"],
                "mission_id": row["mission_id"],
                "timestamp": row["timestamp"],
                "suspicion_label": row["suspicion_label"],
                "suspicious_score": row["suspicious_score"],
                "metadata_blob": json.loads(row["metadata_blob"]),
            }
            files = {
                "thumbnail": row["thumbnail_path"],
                "review_image": row["review_image_path"],
                "roi": row["roi_path"],
            }
            try:
                self.upload_client.upload_record(payload, files)
                self.store.mark_upload_result(row["image_id"], success=True)
                summary.uploaded += 1
            except Exception as exc:
                next_attempt = self.store.compute_backoff(
                    attempts=row["attempts"],
                    base_seconds=self.settings.upload.retry_base_seconds,
                    max_seconds=self.settings.upload.retry_max_seconds,
                )
                self.store.mark_upload_result(row["image_id"], success=False, error=str(exc), next_attempt_at=next_attempt)
                summary.failed += 1
        return summary

    def close(self) -> None:
        self.camera.close()
        self.store.close()
