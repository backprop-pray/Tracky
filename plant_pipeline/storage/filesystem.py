from __future__ import annotations

from datetime import datetime
from pathlib import Path


class PipelinePaths:
    def __init__(self, root_dir: str) -> None:
        self.root = Path(root_dir)

    def ensure_root(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def inspection_dir(self, timestamp: datetime, image_id: str) -> Path:
        day_dir = self.root / timestamp.strftime("%Y") / timestamp.strftime("%m") / timestamp.strftime("%d")
        target = day_dir / image_id
        target.mkdir(parents=True, exist_ok=True)
        return target
