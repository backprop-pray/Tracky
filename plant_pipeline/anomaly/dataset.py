from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

from plant_pipeline.config.settings import Batch2PatchCoreSettings


REQUIRED_SPLITS = {
    ("train", "good"),
    ("val", "good"),
    ("val", "bad"),
    ("test", "good"),
    ("test", "bad"),
}

MANIFEST_NAME = "dataset_manifest.json"


def ensure_dataset_layout(dataset_root: Path) -> None:
    for split, label in REQUIRED_SPLITS:
        (dataset_root / split / label).mkdir(parents=True, exist_ok=True)


def validate_dataset_layout(dataset_root: Path) -> None:
    missing = [str(dataset_root / split / label) for split, label in REQUIRED_SPLITS if not (dataset_root / split / label).exists()]
    if missing:
        raise FileNotFoundError(f"Dataset layout is incomplete: {missing}")


def stable_dataset_filename(roi_path: Path, *, source_tag: str) -> str:
    digest = hashlib.sha1(str(roi_path.resolve()).encode("utf-8")).hexdigest()[:12]
    normalized_name = f"{roi_path.stem}{roi_path.suffix.lower()}"
    return f"{source_tag}__{digest}__{normalized_name}"


def _manifest_path(dataset_root: Path) -> Path:
    return dataset_root / MANIFEST_NAME


def load_dataset_manifest(dataset_root: Path) -> dict[str, Any]:
    path = _manifest_path(dataset_root)
    if not path.exists():
        return {
            "naming_policy": "<source-tag>__<sha1-12>__<original-name>",
            "entries": [],
            "split_counts": {},
        }
    return json.loads(path.read_text())


def write_dataset_manifest(dataset_root: Path, manifest: dict[str, Any]) -> Path:
    path = _manifest_path(dataset_root)
    path.write_text(json.dumps(manifest, indent=2))
    return path


def ingest_rois(
    source_dir: Path,
    dataset_root: Path,
    target_split: str,
    target_label: str,
    mode: str = "symlink",
    *,
    source_tag: str | None = None,
) -> list[Path]:
    target_dir = dataset_root / target_split / target_label
    target_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_dataset_manifest(dataset_root)
    written: list[Path] = []
    tag = source_tag or source_dir.name.replace(" ", "_")
    manifest_entries = manifest.setdefault("entries", [])
    split_counts = manifest.setdefault("split_counts", {})

    for roi_path in sorted(source_dir.glob("*")):
        if not roi_path.is_file():
            continue
        if roi_path.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
            continue
        destination = target_dir / stable_dataset_filename(roi_path, source_tag=tag)
        if destination.exists() or destination.is_symlink():
            destination.unlink()
        if mode == "symlink":
            destination.symlink_to(roi_path.resolve())
        elif mode == "copy":
            shutil.copy2(roi_path, destination)
        else:
            raise ValueError(f"Unknown ingest mode: {mode}")
        manifest_entries.append(
            {
                "split": target_split,
                "label": target_label,
                "output_name": destination.name,
                "source_path": str(roi_path.resolve()),
                "source_tag": tag,
                "mode": mode,
            }
        )
        written.append(destination)

    split_counts[f"{target_split}/{target_label}"] = len(list(target_dir.iterdir()))
    write_dataset_manifest(dataset_root, manifest)
    return written


def dataset_paths(settings: Batch2PatchCoreSettings) -> dict[str, Path]:
    return {
        "dataset_root": Path(settings.dataset_root),
        "train_good": Path(settings.normal_train_dir),
        "val_good": Path(settings.val_good_dir),
        "val_bad": Path(settings.val_bad_dir),
        "test_good": Path(settings.test_good_dir),
        "test_bad": Path(settings.test_bad_dir),
    }
