from __future__ import annotations

import tempfile
from pathlib import Path

from plant_pipeline.config.settings import Batch1Config, load_batch1_settings
from plant_pipeline.schemas.batch1 import Batch1Request
from plant_pipeline.services.batch1_service import Batch1Service

try:  # pragma: no cover - optional dependency path
    from fastapi import FastAPI, File, HTTPException, UploadFile
except ImportError:  # pragma: no cover
    FastAPI = None
    File = None
    HTTPException = RuntimeError
    UploadFile = None


def create_app(config: Batch1Config | None = None):
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Install fastapi and uvicorn to use the API.")
    config = config or load_batch1_settings()
    service = Batch1Service(config)
    app = FastAPI(title="Plant Pipeline Batch 1")

    @app.post("/batch1/inspect")
    async def inspect_image(image_path: str | None = None, file: UploadFile | None = File(default=None)):  # type: ignore[valid-type]
        if file is not None:
            with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename or "upload.png").suffix) as tmp:
                tmp.write(await file.read())
                target = tmp.name
        elif image_path:
            target = image_path
        else:
            raise HTTPException(status_code=400, detail="Provide either image_path or a multipart file.")
        return service.run(Batch1Request(image_path=target)).model_dump(mode="json")

    return app
