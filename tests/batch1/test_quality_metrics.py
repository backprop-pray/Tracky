from __future__ import annotations

import cv2

from plant_pipeline.quality.metrics import blur_score, brightness_metrics, motion_ratio


def test_laplacian_blur_score_changes_with_blur(sharp_plant_image, blurry_plant_image):
    sharp = cv2.cvtColor(cv2.imread(str(sharp_plant_image)), cv2.COLOR_BGR2GRAY)
    blurry = cv2.cvtColor(cv2.imread(str(blurry_plant_image)), cv2.COLOR_BGR2GRAY)
    assert blur_score(sharp) > blur_score(blurry)


def test_motion_ratio_changes_with_directional_smear(sharp_plant_image, motion_blur_image):
    sharp = cv2.cvtColor(cv2.imread(str(sharp_plant_image)), cv2.COLOR_BGR2GRAY)
    blurred = cv2.cvtColor(cv2.imread(str(motion_blur_image)), cv2.COLOR_BGR2GRAY)
    assert motion_ratio(blurred) > motion_ratio(sharp)


def test_brightness_metrics_detect_dark_and_bright_frames(dark_image, overexposed_image):
    dark = cv2.cvtColor(cv2.imread(str(dark_image)), cv2.COLOR_BGR2GRAY)
    bright = cv2.cvtColor(cv2.imread(str(overexposed_image)), cv2.COLOR_BGR2GRAY)
    dark_metrics = brightness_metrics(dark)
    bright_metrics = brightness_metrics(bright)
    assert dark_metrics.brightness_mean < bright_metrics.brightness_mean
    assert bright_metrics.bright_fraction >= dark_metrics.bright_fraction
