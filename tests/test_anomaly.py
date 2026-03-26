from __future__ import annotations

import cv2
import numpy as np

from plant_pipeline.anomaly.patchcore import PatchCoreScorer


def test_patchcore_scores_normal_like_image(settings, synthetic_plant_image):
    image = cv2.imread(str(synthetic_plant_image))
    scorer = PatchCoreScorer(settings.anomaly)
    result = scorer.score(image)
    assert result.label in {"normal", "uncertain", "suspicious"}
    assert 0.0 <= result.suspicious_score <= 1.0


def test_patchcore_scores_outlier_shape(settings):
    image = np.full((300, 300, 3), 240, dtype=np.uint8)
    cv2.rectangle(image, (50, 50), (250, 250), (0, 0, 255), thickness=-1)
    scorer = PatchCoreScorer(settings.anomaly)
    result = scorer.score(image)
    assert 0.0 <= result.suspicious_score <= 1.0
