from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


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

    @property
    def area(self) -> int:
        return self.width * self.height


class Batch1Request(BaseModel):
    image_path: str
    image_id: Optional[str] = None
    mission_id: Optional[str] = None
    row_id: Optional[str] = None
    section_id: Optional[str] = None
    pose: Optional[dict[str, Any]] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LoadedImageMeta(BaseModel):
    image_id: str
    image_path: str
    width: int
    height: int


class QualityDiagnostics(BaseModel):
    blur_score: float
    motion_ratio: float
    brightness_mean: float
    dark_fraction: float
    bright_fraction: float
    vegetation_fraction: Optional[float] = None
    central_vegetation_fraction: Optional[float] = None


class QualityResult(BaseModel):
    is_valid: bool
    reject_reason: Optional[str] = None
    diagnostics: QualityDiagnostics


class DetectionBox(BaseModel):
    bbox: BoundingBox
    confidence: float
    label: str


class DetectorInfo(BaseModel):
    backend_name: str
    model_name: str
    license_tag: str
    runtime_device: str


class DetectorResult(BaseModel):
    info: DetectorInfo
    raw_detections: list[DetectionBox] = Field(default_factory=list)
    filtered_detections: list[DetectionBox] = Field(default_factory=list)


class RoiCluster(BaseModel):
    cluster_id: int
    member_count: int
    bbox: BoundingBox
    sum_confidence: float
    mean_confidence: float
    coverage_ratio: float
    centrality_score: float
    cluster_score: float


class PlantLocalizationResult(BaseModel):
    contains_plant: bool
    detector_confidence: float
    bbox: Optional[BoundingBox] = None
    roi_path: Optional[str] = None
    selected_cluster: Optional[RoiCluster] = None
    candidate_clusters: list[RoiCluster] = Field(default_factory=list)
    detector_info: DetectorInfo


class Batch1PlantResult(BaseModel):
    image_id: str
    image_path: str
    valid: bool
    reject_reason: Optional[str] = None
    contains_plant: bool
    quality: QualityResult
    detector: Optional[DetectorResult] = None
    localization: Optional[PlantLocalizationResult] = None
    artifacts: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
