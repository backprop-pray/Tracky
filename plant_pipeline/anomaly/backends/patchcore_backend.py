from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from torch.utils.data import DataLoader

from plant_pipeline.anomaly.base import AnomalyBackend
from plant_pipeline.anomaly.bundle import load_model_bundle
from plant_pipeline.config.settings import Batch2Config
from plant_pipeline.schemas.batch2 import Batch2FolderRequest, Batch2FolderResult, Batch2Request, SuspicionResult


def _resolve_lightning_accelerator(device: str) -> str:
    normalized = device.lower()
    if normalized in {"cpu", "cuda", "gpu", "mps", "auto"}:
        return "cuda" if normalized == "gpu" else normalized
    return "cpu"


def _load_anomalib_runtime() -> dict[str, Any]:
    data_module = importlib.import_module("anomalib.data")
    data_utils_module = importlib.import_module("anomalib.data.utils")
    models_module = importlib.import_module("anomalib.models")
    post_processing_module = importlib.import_module("anomalib.post_processing")
    pl_module = importlib.import_module("pytorch_lightning")
    torch_module = importlib.import_module("torch")
    anomalib_module = importlib.import_module("anomalib")
    return {
        "anomalib": anomalib_module,
        "torch": torch_module,
        "pl": pl_module,
        "InferenceDataset": getattr(data_module, "InferenceDataset"),
        "InputNormalizationMethod": getattr(data_utils_module, "InputNormalizationMethod"),
        "get_transforms": getattr(data_utils_module, "get_transforms"),
        "get_model": getattr(models_module, "get_model"),
        "ThresholdMethod": getattr(post_processing_module, "ThresholdMethod"),
    }


def load_patchcore_checkpoint(checkpoint_path: str | Path, device: str = "cpu") -> tuple[Any, dict[str, Any], dict[str, Any]]:
    runtime = _load_anomalib_runtime()
    torch_module = runtime["torch"]
    checkpoint = torch_module.load(str(checkpoint_path), map_location=device, weights_only=False)
    model = runtime["get_model"](checkpoint["hyper_parameters"])
    model.load_state_dict(checkpoint["state_dict"], strict=False)
    model.threshold_method = runtime["ThresholdMethod"].MANUAL
    model.eval()
    return model, checkpoint, runtime


def predict_patchcore_paths(
    checkpoint_path: str | Path,
    input_path: str | Path,
    *,
    image_size: int,
    center_crop: int | None,
    device: str,
    batch_size: int = 1,
    num_workers: int = 0,
) -> list[dict[str, Any]]:
    model, checkpoint, runtime = load_patchcore_checkpoint(checkpoint_path, device=device)
    normalization = runtime["InputNormalizationMethod"].IMAGENET
    transform = runtime["get_transforms"](
        image_size=image_size,
        center_crop=center_crop,
        normalization=normalization,
    )
    dataset = runtime["InferenceDataset"](path=str(input_path), transform=transform)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers)
    trainer = runtime["pl"].Trainer(
        accelerator=_resolve_lightning_accelerator(device),
        devices=1,
        logger=False,
        enable_progress_bar=False,
        num_sanity_val_steps=0,
    )
    predictions = trainer.predict(model=model, dataloaders=dataloader)
    items: list[dict[str, Any]] = []
    for batch in predictions:
        image_paths = batch["image_path"]
        pred_scores = batch["pred_scores"]
        anomaly_maps = batch.get("anomaly_maps")
        if isinstance(image_paths, str):
            image_paths = [image_paths]
        if hasattr(pred_scores, "detach"):
            pred_scores = pred_scores.detach().cpu()
        if anomaly_maps is not None and hasattr(anomaly_maps, "detach"):
            anomaly_maps = anomaly_maps.detach().cpu()
        for index, image_path in enumerate(image_paths):
            score_value = pred_scores[index]
            if hasattr(score_value, "item"):
                score = float(score_value.item())
            else:
                score = float(score_value)
            anomaly_map = None
            if anomaly_maps is not None:
                anomaly_map = np.asarray(anomaly_maps[index]).squeeze().astype(np.float32)
            items.append(
                {
                    "image_path": str(image_path),
                    "score": score,
                    "anomaly_map": anomaly_map,
                    "checkpoint_hparams": checkpoint["hyper_parameters"],
                }
            )
    return items


class PatchCoreBackend(AnomalyBackend):
    name = "patchcore"

    def __init__(self, config: Batch2Config) -> None:
        self.config = config
        self.bundle = None
        self.model_name = config.patchcore.model_name
        self.model_version = config.patchcore.model_version
        self._loaded = False
        self._anomalib_available = False
        self._fallback_reason: str | None = None

    def load(self) -> None:
        self.bundle = load_model_bundle(self.config)
        checkpoint = Path(self.bundle.checkpoint_path)
        if not checkpoint.exists():
            raise FileNotFoundError(f"PatchCore checkpoint not found: {checkpoint}")
        self.model_name = self.bundle.model_name
        self.model_version = self.bundle.model_version
        try:
            _load_anomalib_runtime()
        except Exception as exc:  # pragma: no cover - depends on local ml env
            self._anomalib_available = False
            self._fallback_reason = f"anomalib_unavailable:{type(exc).__name__}"
        else:
            self._anomalib_available = True
            self._fallback_reason = None
        self._loaded = True

    def predict(self, request: Batch2Request) -> SuspicionResult:
        if not self._loaded:
            self.load()
        roi_path = Path(request.roi_path)
        if not roi_path.exists():
            raise FileNotFoundError(f"ROI not found: {request.roi_path}")
        image = cv2.imread(str(roi_path))
        if image is None:
            raise ValueError(f"Failed to read ROI image: {request.roi_path}")
        score, anomaly_map, mode = self._predict_raw(request, image)
        lower, upper = self._thresholds()
        label = self._label_for_score(score, lower, upper)
        confidence = self._confidence_for_score(score, lower, upper)
        anomaly_map_path = None
        if anomaly_map is not None and self.config.batch2.write_anomaly_map:
            anomaly_map_path = self._write_anomaly_map(request.image_id, anomaly_map)
        return SuspicionResult(
            image_id=request.image_id,
            roi_path=request.roi_path,
            label=label,
            suspicious=label == "suspicious",
            suspicious_score=score,
            confidence=confidence,
            lower_threshold=lower,
            upper_threshold=upper,
            anomaly_map_path=anomaly_map_path,
            model_name=self.model_name,
            model_version=self.model_version,
            debug={
                "backend_mode": mode,
                "anomalib_available": self._anomalib_available,
                "fallback_reason": self._fallback_reason,
                "bundle_dir": self.bundle.bundle_dir if self.bundle is not None else "",
                "metadata": request.metadata,
            },
        )

    def predict_folder(self, request: Batch2FolderRequest) -> Batch2FolderResult:
        if not self._loaded:
            self.load()
        input_dir = Path(request.input_dir)
        if not input_dir.exists():
            raise FileNotFoundError(f"ROI folder not found: {request.input_dir}")
        results = []
        failed_count = 0
        for roi_path in sorted(input_dir.glob(request.glob_pattern)):
            if not roi_path.is_file():
                continue
            image_id = roi_path.stem
            try:
                results.append(self.predict(Batch2Request(image_id=image_id, roi_path=str(roi_path), metadata=request.metadata)))
            except Exception:
                failed_count += 1
        return Batch2FolderResult(
            results=results,
            processed_count=len(results),
            failed_count=failed_count,
            debug={"input_dir": str(input_dir), "glob_pattern": request.glob_pattern},
        )

    def close(self) -> None:
        self._loaded = False

    def _predict_raw(self, request: Batch2Request, image_bgr: np.ndarray) -> tuple[float, np.ndarray | None, str]:
        if self._anomalib_available and self.bundle is not None:
            try:
                items = predict_patchcore_paths(
                    self.bundle.checkpoint_path,
                    request.roi_path,
                    image_size=self.config.patchcore.image_size,
                    center_crop=self.config.patchcore.center_crop,
                    device=self.config.patchcore.device,
                    batch_size=1,
                    num_workers=self.config.patchcore.num_workers,
                )
                if items:
                    return float(items[0]["score"]), items[0]["anomaly_map"], "anomalib_patchcore"
            except Exception as exc:  # pragma: no cover - fallback path depends on local env
                self._fallback_reason = f"anomalib_predict_failed:{type(exc).__name__}"
        return (*self._fallback_predict_raw(image_bgr), "fallback_heuristic")

    def _fallback_predict_raw(self, image_bgr: np.ndarray) -> tuple[float, np.ndarray | None]:
        image = cv2.resize(image_bgr, (self.config.patchcore.image_size, self.config.patchcore.image_size))
        hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
        sat = hsv[:, :, 1].astype(np.float32) / 255.0
        val = hsv[:, :, 2].astype(np.float32) / 255.0
        exg = (
            2.0 * image[:, :, 1].astype(np.float32)
            - image[:, :, 2].astype(np.float32)
            - image[:, :, 0].astype(np.float32)
        ) / 255.0
        anomaly_map = np.clip(np.abs(exg - np.median(exg)) + np.abs(val - np.median(val)) * 0.5 + sat * 0.15, 0.0, 1.0)
        score = float(np.clip(np.percentile(anomaly_map, 97), 0.0, 1.0))
        return score, anomaly_map

    def _thresholds(self) -> tuple[float, float]:
        if self.bundle is None:
            raise RuntimeError("PatchCore bundle is not loaded.")
        lower = self.config.thresholds.lower_threshold
        upper = self.config.thresholds.upper_threshold
        return (
            float(self.bundle.thresholds.lower_threshold if lower is None else lower),
            float(self.bundle.thresholds.upper_threshold if upper is None else upper),
        )

    def _label_for_score(self, score: float, lower: float, upper: float) -> str:
        if score < lower:
            return "normal"
        if score > upper:
            return "suspicious"
        return "uncertain"

    def _confidence_for_score(self, score: float, lower: float, upper: float) -> float:
        midpoint = (lower + upper) / 2.0
        if score < lower:
            return float(np.clip((midpoint - score) / max(abs(midpoint), 1e-6), 0.0, 1.0))
        if score > upper:
            return float(np.clip((score - midpoint) / max(abs(score), 1e-6), 0.0, 1.0))
        half_band = max((upper - lower) / 2.0, 1e-6)
        return float(np.clip(abs(score - midpoint) / half_band, 0.0, 1.0) * 0.5)

    def _write_anomaly_map(self, image_id: str, anomaly_map: np.ndarray) -> str:
        output_dir = Path(self.config.batch2.output_root) / image_id
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"anomaly_map.{self.config.batch2.anomaly_map_format}"
        normalized = cv2.normalize(anomaly_map, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)
        colored = cv2.applyColorMap(normalized, cv2.COLORMAP_JET)
        cv2.imwrite(str(output_path), colored)
        return str(output_path)
