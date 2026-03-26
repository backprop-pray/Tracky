from __future__ import annotations

from pathlib import Path

import pytest

from plant_pipeline.anomaly.backends.patchcore_backend import PatchCoreBackend, predict_patchcore_paths
from plant_pipeline.schemas.batch2 import Batch2Request


def test_backend_loads_valid_bundle(batch2_config):
    backend = PatchCoreBackend(batch2_config)
    backend.load()
    assert backend.model_name == batch2_config.patchcore.model_name
    assert backend.model_version == batch2_config.patchcore.model_version
    backend.close()


def test_missing_checkpoint_fails_fast(batch2_config):
    checkpoint_path = Path(batch2_config.patchcore.bundle_root) / batch2_config.patchcore.model_version / "model.ckpt"
    checkpoint_path.unlink()
    backend = PatchCoreBackend(batch2_config)
    with pytest.raises(FileNotFoundError):
        backend.load()


def test_missing_thresholds_fail_fast(batch2_config):
    thresholds_path = Path(batch2_config.patchcore.bundle_root) / batch2_config.patchcore.model_version / "thresholds.json"
    thresholds_path.unlink()
    backend = PatchCoreBackend(batch2_config)
    with pytest.raises(FileNotFoundError):
        backend.load()


def test_backend_returns_structured_result(batch2_config, good_roi):
    backend = PatchCoreBackend(batch2_config)
    result = backend.predict(Batch2Request(image_id="img-1", roi_path=str(good_roi)))
    assert result.image_id == "img-1"
    assert result.model_name == batch2_config.patchcore.model_name
    assert result.model_version == batch2_config.patchcore.model_version
    backend.close()


def test_backend_raises_when_real_inference_fails_and_fallback_disabled(batch2_config, good_roi, monkeypatch):
    batch2_config.patchcore.allow_inference_fallback = False
    backend = PatchCoreBackend(batch2_config)
    monkeypatch.setattr(
        "plant_pipeline.anomaly.backends.patchcore_backend.predict_patchcore_paths",
        lambda *args, **kwargs: (_ for _ in ()).throw(UnboundLocalError("boom")),
    )
    backend._anomalib_available = True
    backend._loaded = True
    backend.bundle = type("Bundle", (), {"bundle_dir": "bundle", "checkpoint_path": "/tmp/model.ckpt", "thresholds": type("T", (), {"lower_threshold": 0.3, "upper_threshold": 0.7})(), "model_name": "patchcore", "model_version": "v1"})()
    with pytest.raises(RuntimeError):
        backend.predict(Batch2Request(image_id="img-1", roi_path=str(good_roi)))


def test_predict_patchcore_paths_handles_single_file_path(monkeypatch, tmp_path):
    image = tmp_path / "sample.png"
    image.write_bytes(b"img")

    class FakeInferenceDataset:
        def __init__(self, path, transform):
            assert isinstance(path, Path)
            self.path = path
            self.transform = transform

        def __len__(self):
            return 1

        def __getitem__(self, index):
            return {"image_path": str(self.path)}

    class FakeTrainer:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        def predict(self, model, dataloaders):
            return [
                {
                    "image_path": [str(image)],
                    "pred_scores": [0.42],
                    "anomaly_maps": [[[ [1.0, 2.0], [3.0, 4.0] ]]],
                }
            ]

    monkeypatch.setattr(
        "plant_pipeline.anomaly.backends.patchcore_backend.load_patchcore_checkpoint",
        lambda checkpoint_path, device="cpu": (
            object(),
            {"hyper_parameters": {}},
            {
                "InputNormalizationMethod": type("Norm", (), {"IMAGENET": object()}),
                "get_transforms": lambda **kwargs: "transform",
                "InferenceDataset": FakeInferenceDataset,
                "pl": type("PL", (), {"Trainer": FakeTrainer}),
            },
        ),
    )

    items = predict_patchcore_paths(
        "/tmp/model.ckpt",
        image,
        image_size=224,
        center_crop=None,
        device="cpu",
        batch_size=1,
        num_workers=0,
    )
    assert items[0]["image_path"] == str(image)
    assert items[0]["score"] == 0.42
