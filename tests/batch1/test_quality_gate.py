from __future__ import annotations

import cv2

from plant_pipeline.quality.gate import Batch1QualityGate


def _evaluate(path, config):
    image = cv2.imread(str(path))
    working = cv2.resize(image, (config.batch1.working_size, config.batch1.working_size))
    return Batch1QualityGate(config.quality_batch1).evaluate(working)


def test_accepts_sharp_well_exposed_image(batch1_config, sharp_plant_image):
    result = _evaluate(sharp_plant_image, batch1_config)
    assert result.is_valid
    assert result.reject_reason is None


def test_rejects_blurry_image(batch1_config, blurry_plant_image):
    result = _evaluate(blurry_plant_image, batch1_config)
    assert not result.is_valid
    assert result.reject_reason == "blur"


def test_rejects_underexposed_image(batch1_config, dark_image):
    result = _evaluate(dark_image, batch1_config)
    assert not result.is_valid
    assert result.reject_reason == "underexposed"


def test_rejects_overexposed_image(batch1_config, overexposed_image):
    result = _evaluate(overexposed_image, batch1_config)
    assert not result.is_valid
    assert result.reject_reason == "overexposed"


def test_rejects_motion_blurred_image(batch1_config, motion_blur_image):
    result = _evaluate(motion_blur_image, batch1_config)
    assert not result.is_valid
    assert result.reject_reason == "motion_blur"


def test_does_not_reject_yellow_or_brown_plant_when_quality_is_ok(batch1_config, yellow_plant_image):
    result = _evaluate(yellow_plant_image, batch1_config)
    assert result.is_valid
