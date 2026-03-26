from __future__ import annotations

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from picamera2 import Picamera2  # type: ignore
except ImportError:  # pragma: no cover - Pi-only dependency
    Picamera2 = None

from plant_pipeline.schemas.models import CaptureRequest, CapturedFrame


class PlantCamera:
    """Capture frames either from Picamera2 or a provided image path."""

    def __init__(self, image_format: str = "jpg", simulate: bool = True) -> None:
        self.image_format = image_format
        self.simulate = simulate
        self._camera: Optional[Picamera2] = None

    def initialize(self) -> None:
        if self.simulate:
            return
        if Picamera2 is None:
            raise RuntimeError("Picamera2 is not installed; enable simulate mode or install picamera2.")
        self._camera = Picamera2()
        self._camera.configure(self._camera.create_still_configuration())
        self._camera.start()

    def close(self) -> None:
        if self._camera is not None:
            self._camera.close()
            self._camera = None

    def capture(self, request: CaptureRequest, output_dir: Path) -> CapturedFrame:
        output_dir.mkdir(parents=True, exist_ok=True)
        image_id = uuid.uuid4().hex
        timestamp = datetime.now(timezone.utc)
        image_path = output_dir / f"{image_id}.{self.image_format}"
        camera_meta: dict[str, Any] = {}

        if request.source_image_path:
            shutil.copy2(request.source_image_path, image_path)
            camera_meta["source"] = "file"
            camera_meta["source_image_path"] = request.source_image_path
        else:
            if self._camera is None:
                self.initialize()
            if self._camera is None:
                raise RuntimeError("Camera is not initialized.")
            self._camera.capture_file(str(image_path))
            try:
                camera_meta.update(self._camera.capture_metadata())
            except Exception:
                camera_meta["capture_metadata_error"] = True
            camera_meta["source"] = "picamera2"

        return CapturedFrame(
            image_id=image_id,
            timestamp=timestamp,
            mission_id=request.mission_id,
            path_full=str(image_path),
            row_id=request.row_id,
            section_id=request.section_id,
            pose=request.pose,
            camera_meta=camera_meta,
        )
