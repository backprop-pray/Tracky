from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from plant_pipeline.config.settings import Batch2ThresholdSettings
from plant_pipeline.schemas.batch2 import ThresholdBundle


def calibrate_thresholds(
    val_good_scores: list[float],
    val_bad_scores: list[float] | None,
    settings: Batch2ThresholdSettings,
    *,
    dataset_version: str,
) -> ThresholdBundle:
    if not val_good_scores:
        raise ValueError("Calibration requires at least one normal validation score.")
    if len(val_good_scores) < settings.min_val_good_count:
        raise ValueError(
            f"Calibration requires at least {settings.min_val_good_count} val/good scores, got {len(val_good_scores)}."
        )
    good = np.asarray(val_good_scores, dtype=np.float32)
    lower = float(np.quantile(good, settings.normal_percentile))
    calibration_mode = "normal-only"
    if val_bad_scores:
        if len(val_bad_scores) < settings.min_val_bad_count:
            raise ValueError(
                f"Calibration requires at least {settings.min_val_bad_count} val/bad scores, got {len(val_bad_scores)}."
            )
        if len({round(score, 6) for score in val_bad_scores}) < 2:
            raise ValueError("Calibration rejected val/bad scores because they collapse to fewer than 2 unique values.")
        bad = np.asarray(val_bad_scores, dtype=np.float32)
        upper = float(np.quantile(bad, settings.suspicious_percentile))
        calibration_mode = "bad-aware"
    else:
        if settings.require_bad_validation:
            raise ValueError("Calibration requires val/bad scores for bad-aware thresholding.")
        upper = max(lower + settings.min_gap, float(np.quantile(good, 0.999)))

    if upper <= lower:
        upper = min(1.0, lower + settings.min_gap)
    if upper <= lower:
        upper = lower + 1e-6

    return ThresholdBundle(
        lower_threshold=lower,
        upper_threshold=upper,
        normal_percentile=settings.normal_percentile,
        suspicious_percentile=settings.suspicious_percentile,
        calibration_dataset_version=dataset_version,
        score_summary={
            "calibration_mode": 1.0 if calibration_mode == "bad-aware" else 0.0,
            "good_count": float(len(val_good_scores)),
            "good_min": float(good.min()),
            "good_max": float(good.max()),
            "good_mean": float(good.mean()),
            "good_std": float(good.std()),
            "bad_count": float(len(val_bad_scores)) if val_bad_scores else 0.0,
            "bad_min": float(min(val_bad_scores)) if val_bad_scores else upper,
            "bad_max": float(max(val_bad_scores)) if val_bad_scores else upper,
            "bad_mean": float(np.asarray(val_bad_scores, dtype=np.float32).mean()) if val_bad_scores else upper,
        },
    )


def write_threshold_bundle(path: Path, bundle: ThresholdBundle) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle.model_dump(mode="json"), indent=2))
    return path
