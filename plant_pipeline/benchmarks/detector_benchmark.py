from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path

import cv2

from plant_pipeline.config.settings import load_batch1_settings
from plant_pipeline.detect.factory import build_detector_backend

IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Batch1 detector backends")
    parser.add_argument("--images", required=True, help="Directory of images")
    parser.add_argument("--config", default=None, help="Path to batch1 YAML config")
    parser.add_argument("--backend", default=None, help="Override detector backend id")
    args = parser.parse_args()

    config = load_batch1_settings(args.config)
    if args.backend:
        config.detector_batch1.backend = args.backend
    backend = build_detector_backend(config.detector_batch1)
    backend.load()

    paths = sorted(path for path in Path(args.images).iterdir() if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES)
    for _ in range(config.detector_batch1.warmup_runs):
        for path in paths[:1]:
            image = cv2.imread(str(path))
            if image is not None:
                backend.detect(image)

    latencies = []
    detections_per_image = []
    failures = 0
    plant_found = 0
    for path in paths:
        image = cv2.imread(str(path))
        if image is None:
            failures += 1
            continue
        start = time.perf_counter()
        detections = backend.detect(image)
        latencies.append((time.perf_counter() - start) * 1000.0)
        detections_per_image.append(len(detections))
        if detections:
            plant_found += 1
    backend.close()

    p50 = statistics.median(latencies) if latencies else 0.0
    p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies, default=0.0)
    print(
        {
            "backend": backend.name,
            "model_name": backend.model_name,
            "license_tag": backend.license_tag,
            "images": len(paths),
            "mean_latency_ms": round(statistics.mean(latencies), 3) if latencies else 0.0,
            "p50_latency_ms": round(p50, 3),
            "p95_latency_ms": round(p95, 3),
            "detections_per_image": round(statistics.mean(detections_per_image), 3) if detections_per_image else 0.0,
            "plant_found_rate": round(plant_found / len(paths), 3) if paths else 0.0,
            "failure_count": failures,
        }
    )


if __name__ == "__main__":
    main()
