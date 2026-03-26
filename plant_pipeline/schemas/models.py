from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class UploadStatus(str, Enum):
    PENDING = "pending"
    UPLOADED = "uploaded"
    FAILED = "failed"
    SKIPPED = "skipped"


class BoundingBox(BaseModel):
    x_min: int
    y_min: int
    x_max: int
    y_max: int

    @property
    def width(self) -> int:
        return max(0, self.x_max - self.x_min)

    @property
    def height(self) -> int:
        return max(0, self.y_max - self.y_min)


class CaptureRequest(BaseModel):
    mission_id: str
    row_id: Optional[str] = None
    section_id: Optional[str] = None
    pose: Optional[dict[str, Any]] = None
    source_image_path: Optional[str] = None


class CapturedFrame(BaseModel):
    image_id: str
    timestamp: datetime
    mission_id: str
    path_full: str
    row_id: Optional[str] = None
    section_id: Optional[str] = None
    pose: Optional[dict[str, Any]] = None
    camera_meta: dict[str, Any] = Field(default_factory=dict)


class QualityResult(BaseModel):
    is_valid: bool
    blur_score: float
    motion_blur_score: float
    brightness_score: float
    foreground_score: float
    reject_reason: Optional[str] = None
    diagnostics: dict[str, float] = Field(default_factory=dict)


class PlantDetectionResult(BaseModel):
    contains_plant: bool
    confidence: float
    bbox: Optional[BoundingBox] = None
    roi_path: Optional[str] = None
    fallback_used: bool = False
    detector_model_version: str
    diagnostics: dict[str, float] = Field(default_factory=dict)


class SuspicionResult(BaseModel):
    label: str
    suspicious_score: float
    confidence: float
    anomaly_model_version: str
    diagnostics: dict[str, float] = Field(default_factory=dict)


class UploadArtifactSet(BaseModel):
    thumbnail_path: str
    review_image_path: str
    roi_path: str
    bytes_thumbnail: int
    bytes_review: int
    bytes_roi: int
    compression_format: str


class FinalInspectionRecord(BaseModel):
    image_id: str
    timestamp: datetime
    mission_id: str
    valid: bool
    contains_plant: bool
    suspicious: bool
    suspicion_label: str
    suspicious_score: float
    detector_confidence: float
    upload_status: UploadStatus
    artifact_paths: dict[str, str] = Field(default_factory=dict)
    metadata_blob: dict[str, Any] = Field(default_factory=dict)


class SyncSummary(BaseModel):
    attempted: int = 0
    uploaded: int = 0
    failed: int = 0
    skipped: int = 0
