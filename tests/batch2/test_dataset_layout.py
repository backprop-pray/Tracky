from __future__ import annotations

import json
from pathlib import Path

import pytest

from plant_pipeline.anomaly.dataset import (
    ensure_dataset_layout,
    ingest_rois,
    load_dataset_manifest,
    validate_dataset_layout,
)


def test_dataset_helper_creates_required_layout(tmp_path: Path):
    dataset_root = tmp_path / "dataset"
    ensure_dataset_layout(dataset_root)
    validate_dataset_layout(dataset_root)


def test_ingest_rois_uses_unique_stable_names_and_manifest(tmp_path: Path):
    source_a = tmp_path / "source_a"
    source_b = tmp_path / "source_b"
    source_a.mkdir()
    source_b.mkdir()
    (source_a / "leaf.png").write_bytes(b"a")
    (source_b / "leaf.png").write_bytes(b"b")
    dataset_root = tmp_path / "dataset"
    ensure_dataset_layout(dataset_root)

    written_a = ingest_rois(source_a, dataset_root, "val", "bad", mode="copy", source_tag="class_a")
    written_b = ingest_rois(source_b, dataset_root, "val", "bad", mode="copy", source_tag="class_b")

    assert written_a[0].name != written_b[0].name
    manifest = load_dataset_manifest(dataset_root)
    assert manifest["naming_policy"] == "<source-tag>__<sha1-12>__<original-name>"
    assert len(manifest["entries"]) == 2
    assert manifest["split_counts"]["val/bad"] == 2
    assert written_a[0].suffix == ".png"
    assert written_b[0].suffix == ".png"


def test_validate_dataset_rejects_incomplete_root(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        validate_dataset_layout(tmp_path / "missing")
