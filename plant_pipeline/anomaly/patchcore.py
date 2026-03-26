from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from plant_pipeline.config.settings import AnomalySettings
from plant_pipeline.schemas.models import SuspicionResult

try:
    import torch
    from torchvision import models, transforms
except ImportError:  # pragma: no cover
    torch = None
    models = None
    transforms = None


class PatchCoreScorer:
    def __init__(self, settings: AnomalySettings) -> None:
        self.settings = settings
        self.memory_bank = self._load_memory_bank()
        self.backbone = self._load_backbone()

    def _load_memory_bank(self) -> np.ndarray:
        if self.settings.memory_bank_path and Path(self.settings.memory_bank_path).exists():
            payload = np.load(self.settings.memory_bank_path)
            return payload["memory_bank"].astype(np.float32)
        return np.zeros((1, 512), dtype=np.float32)

    def _load_backbone(self):  # type: ignore[no-untyped-def]
        if torch is None or models is None:
            return None
        model = models.resnet18(weights=None)
        model.fc = torch.nn.Identity()
        model.eval()
        return model

    def score(self, roi_bgr: np.ndarray) -> SuspicionResult:
        embedding = self._embed(roi_bgr)
        distances = np.linalg.norm(self.memory_bank - embedding[None, :], axis=1)
        raw_score = float(distances.min())
        normalized = self._normalize_score(raw_score)
        label = self._label_for_score(normalized)
        confidence = self._confidence_for_score(normalized)
        return SuspicionResult(
            label=label,
            suspicious_score=normalized,
            confidence=confidence,
            anomaly_model_version=self.settings.model_version,
            diagnostics={"raw_distance": raw_score},
        )

    def _embed(self, roi_bgr: np.ndarray) -> np.ndarray:
        roi_rgb = cv2.cvtColor(roi_bgr, cv2.COLOR_BGR2RGB)
        roi_rgb = cv2.resize(roi_rgb, (self.settings.image_size, self.settings.image_size))
        if self.backbone is not None and torch is not None and transforms is not None:
            transform = transforms.Compose(
                [
                    transforms.ToTensor(),
                    transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
                ]
            )
            tensor = transform(roi_rgb).unsqueeze(0)
            with torch.no_grad():
                features = self.backbone(tensor)
            return features.squeeze(0).detach().cpu().numpy().astype(np.float32)

        flat = roi_rgb.astype(np.float32).reshape(-1, 3)
        mean = flat.mean(axis=0)
        std = flat.std(axis=0)
        hist = []
        for channel in range(3):
            counts, _ = np.histogram(flat[:, channel], bins=16, range=(0, 255), density=True)
            hist.append(counts.astype(np.float32))
        embedding = np.concatenate([mean, std, *hist]).astype(np.float32)
        padded = np.zeros((512,), dtype=np.float32)
        padded[: embedding.shape[0]] = embedding
        return padded

    def _normalize_score(self, raw_score: float) -> float:
        scale = max(self.settings.suspicious_threshold * 2.0, 1e-6)
        return float(np.clip(raw_score / scale, 0.0, 1.0))

    def _label_for_score(self, score: float) -> str:
        if score < self.settings.normal_threshold:
            return "normal"
        if score > self.settings.suspicious_threshold:
            return "suspicious"
        return "uncertain"

    def _confidence_for_score(self, score: float) -> float:
        midpoint = (self.settings.normal_threshold + self.settings.suspicious_threshold) / 2.0
        if score < self.settings.normal_threshold:
            return float(np.clip((midpoint - score) / max(midpoint, 1e-6), 0.0, 1.0))
        if score > self.settings.suspicious_threshold:
            return float(np.clip((score - midpoint) / max(1.0 - midpoint, 1e-6), 0.0, 1.0))
        band = max((self.settings.suspicious_threshold - self.settings.normal_threshold) / 2.0, 1e-6)
        return float(np.clip(abs(score - midpoint) / band, 0.0, 1.0) * 0.5)
