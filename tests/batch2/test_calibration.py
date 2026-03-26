from __future__ import annotations

from plant_pipeline.anomaly.calibration import calibrate_thresholds
from plant_pipeline.config.settings import Batch2ThresholdSettings


def test_calibration_computes_valid_thresholds():
    settings = Batch2ThresholdSettings(min_val_good_count=1, min_val_bad_count=1)
    bundle = calibrate_thresholds(
        [0.10, 0.12, 0.18, 0.22],
        [0.72, 0.81, 0.88],
        settings,
        dataset_version="dataset-v1",
    )
    assert bundle.upper_threshold > bundle.lower_threshold


def test_calibration_supports_normal_only_fallback():
    settings = Batch2ThresholdSettings(min_val_good_count=1, min_val_bad_count=1, require_bad_validation=False)
    bundle = calibrate_thresholds(
        [0.10, 0.12, 0.18, 0.22],
        [],
        settings,
        dataset_version="dataset-v1",
    )
    assert bundle.upper_threshold > bundle.lower_threshold


def test_calibration_rejects_undersized_bad_validation():
    settings = Batch2ThresholdSettings(min_val_good_count=1, min_val_bad_count=2)
    try:
        calibrate_thresholds([0.1, 0.2], [0.9], settings, dataset_version="dataset-v1")
    except ValueError as exc:
        assert "val/bad" in str(exc)
    else:
        raise AssertionError("Expected calibration to reject undersized val/bad.")
