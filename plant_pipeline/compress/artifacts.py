from __future__ import annotations

from pathlib import Path
from typing import Optional

from PIL import Image

from plant_pipeline.config.settings import CompressionSettings
from plant_pipeline.schemas.models import BoundingBox, UploadArtifactSet


class ArtifactGenerator:
    def __init__(self, settings: CompressionSettings) -> None:
        self.settings = settings

    def generate(self, full_image_path: str, bbox: Optional[BoundingBox], output_dir: Path) -> UploadArtifactSet:
        output_dir.mkdir(parents=True, exist_ok=True)
        image = Image.open(full_image_path).convert("RGB")

        thumbnail = self._resize_copy(image, self.settings.thumbnail_max_side)
        review = self._resize_copy(image, self.settings.review_max_side)
        roi_image = self._crop_roi(image, bbox)
        roi = self._resize_copy(roi_image, self.settings.roi_max_side)

        suffix = "webp" if self.settings.format.lower() == "webp" else "jpg"
        thumb_path = output_dir / f"thumbnail.{suffix}"
        review_path = output_dir / f"review.{suffix}"
        roi_path = output_dir / f"roi.{suffix}"

        self._save_image(thumbnail, thumb_path)
        self._save_image(review, review_path)
        self._save_image(roi, roi_path)

        return UploadArtifactSet(
            thumbnail_path=str(thumb_path),
            review_image_path=str(review_path),
            roi_path=str(roi_path),
            bytes_thumbnail=thumb_path.stat().st_size,
            bytes_review=review_path.stat().st_size,
            bytes_roi=roi_path.stat().st_size,
            compression_format=self.settings.format.lower(),
        )

    def _resize_copy(self, image: Image.Image, max_side: int) -> Image.Image:
        copy = image.copy()
        copy.thumbnail((max_side, max_side))
        return copy

    def _crop_roi(self, image: Image.Image, bbox: Optional[BoundingBox]) -> Image.Image:
        if bbox is None:
            return image.copy()
        return image.crop((bbox.x_min, bbox.y_min, bbox.x_max, bbox.y_max))

    def _save_image(self, image: Image.Image, path: Path) -> None:
        if self.settings.format.lower() == "webp":
            image.save(path, format="WEBP", quality=self.settings.webp_quality)
            return
        image.save(path, format="JPEG", quality=self.settings.jpeg_quality)
