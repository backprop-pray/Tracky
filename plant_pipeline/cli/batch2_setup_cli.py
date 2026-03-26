from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

from plant_pipeline.anomaly.backends.patchcore_backend import predict_patchcore_paths
from plant_pipeline.anomaly.bundle import resolve_bundle_dir, write_model_bundle_metadata
from plant_pipeline.anomaly.calibration import calibrate_thresholds, write_threshold_bundle
from plant_pipeline.anomaly.dataset import ensure_dataset_layout, ingest_rois, validate_dataset_layout
from plant_pipeline.config.settings import Batch2Config, load_batch2_settings


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch 2 dataset/setup utilities")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_dataset = subparsers.add_parser("init-dataset")
    init_dataset.add_argument("--config", default=None)

    ingest = subparsers.add_parser("ingest")
    ingest.add_argument("--config", default=None)
    ingest.add_argument("--source-dir", required=True)
    ingest.add_argument("--split", required=True, choices=["train", "val", "test"])
    ingest.add_argument("--label", required=True, choices=["good", "bad"])
    ingest.add_argument("--mode", default="symlink", choices=["symlink", "copy"])

    fit = subparsers.add_parser("fit")
    fit.add_argument("--config", default=None)
    fit.add_argument("--dataset-version", required=True)

    calibrate = subparsers.add_parser("calibrate")
    calibrate.add_argument("--config", default=None)
    calibrate.add_argument("--dataset-version", required=True)
    calibrate.add_argument("--val-good-dir", default=None)
    calibrate.add_argument("--val-bad-dir", default=None)

    return parser


def _relative_to_dataset_root(config: Batch2Config, path: str) -> str:
    return str(Path(path).resolve().relative_to(Path(config.patchcore.dataset_root).resolve()))


def _build_anomalib_config(config: Batch2Config, project_path: Path) -> Any:
    return OmegaConf.create(
        {
            "dataset": {
                "task": "classification",
                "image_size": config.patchcore.image_size,
                "center_crop": config.patchcore.center_crop,
                "normalization": "imagenet",
                "train_batch_size": config.patchcore.train_batch_size,
                "eval_batch_size": config.patchcore.eval_batch_size,
                "num_workers": config.patchcore.num_workers,
            },
            "model": {
                "name": config.patchcore.model_name,
                "input_size": [config.patchcore.image_size, config.patchcore.image_size],
                "backbone": config.patchcore.backbone,
                "pre_trained": True,
                "layers": config.patchcore.layers,
                "coreset_sampling_ratio": config.patchcore.coreset_sampling_ratio,
                "num_neighbors": config.patchcore.num_neighbors,
                "normalization_method": config.patchcore.normalization_method,
            },
            "metrics": {
                "image": ["F1Score", "AUROC"],
                "pixel": [],
                "threshold": {"method": "adaptive", "manual_image": None, "manual_pixel": None},
            },
            "visualization": {
                "show_images": False,
                "save_images": False,
                "log_images": False,
                "image_save_path": None,
                "mode": "simple",
            },
            "project": {
                "path": str(project_path),
                "seed": 0,
            },
            "logging": {"logger": [], "log_graph": False},
            "optimization": {"export_mode": None},
            "trainer": {
                "accelerator": config.patchcore.device,
                "devices": 1,
                "max_epochs": 1,
                "enable_checkpointing": True,
                "default_root_dir": str(project_path),
                "enable_progress_bar": False,
                "num_sanity_val_steps": 0,
                "limit_train_batches": 1.0,
                "limit_val_batches": 1.0,
                "check_val_every_n_epoch": 1,
                "val_check_interval": 1.0,
            },
        }
    )


def _fit_patchcore_bundle(config: Batch2Config) -> Path:
    validate_dataset_layout(Path(config.patchcore.dataset_root))
    try:
        import pytorch_lightning as pl
        from anomalib.data import Folder, TaskType
        from anomalib.models import get_model
        from anomalib.utils.callbacks import get_callbacks
    except ImportError as exc:  # pragma: no cover - depends on local ml env
        raise RuntimeError("Anomalib training dependencies are not installed.") from exc

    bundle_dir = resolve_bundle_dir(config)
    project_path = bundle_dir / "_training"
    project_path.mkdir(parents=True, exist_ok=True)
    anomalib_config = _build_anomalib_config(config, project_path)
    model = get_model(anomalib_config)
    callbacks = get_callbacks(anomalib_config)
    trainer = pl.Trainer(logger=False, callbacks=callbacks, **anomalib_config.trainer)
    datamodule = Folder(
        root=config.patchcore.dataset_root,
        normal_dir=_relative_to_dataset_root(config, config.patchcore.normal_train_dir),
        abnormal_dir=_relative_to_dataset_root(config, config.patchcore.val_bad_dir),
        normal_test_dir=_relative_to_dataset_root(config, config.patchcore.val_good_dir),
        task=TaskType.CLASSIFICATION,
        image_size=config.patchcore.image_size,
        center_crop=config.patchcore.center_crop,
        train_batch_size=config.patchcore.train_batch_size,
        eval_batch_size=config.patchcore.eval_batch_size,
        num_workers=config.patchcore.num_workers,
        test_split_mode="from_dir",
        val_split_mode="same_as_test",
    )
    trainer.fit(model=model, datamodule=datamodule)
    trained_checkpoint = project_path / "weights" / "lightning" / "model.ckpt"
    if not trained_checkpoint.exists():
        raise FileNotFoundError(f"Expected trained checkpoint at {trained_checkpoint}")
    bundle_dir.mkdir(parents=True, exist_ok=True)
    output_checkpoint = bundle_dir / "model.ckpt"
    shutil.copy2(trained_checkpoint, output_checkpoint)
    return output_checkpoint


def _collect_scores(config: Batch2Config, directory: Path) -> list[float]:
    if not directory.exists():
        return []
    bundle_dir = resolve_bundle_dir(config)
    checkpoint_path = bundle_dir / "model.ckpt"
    items = predict_patchcore_paths(
        checkpoint_path,
        directory,
        image_size=config.patchcore.image_size,
        center_crop=config.patchcore.center_crop,
        device=config.patchcore.device,
        batch_size=config.patchcore.eval_batch_size,
        num_workers=config.patchcore.num_workers,
    )
    return [float(item["score"]) for item in items]


def _installed_anomalib_version() -> str:
    try:
        import anomalib
    except ImportError:
        return "unavailable"
    return getattr(anomalib, "__version__", "unknown")


def main() -> None:
    args = build_parser().parse_args()
    config = load_batch2_settings(getattr(args, "config", None))

    if args.command == "init-dataset":
        ensure_dataset_layout(Path(config.patchcore.dataset_root))
        print(json.dumps({"dataset_root": config.patchcore.dataset_root, "status": "ok"}, indent=2))
        return

    if args.command == "ingest":
        written = ingest_rois(
            Path(args.source_dir),
            Path(config.patchcore.dataset_root),
            args.split,
            args.label,
            mode=args.mode,
        )
        print(json.dumps({"written_count": len(written), "target_split": args.split, "target_label": args.label}, indent=2))
        return

    if args.command == "fit":
        checkpoint_path = _fit_patchcore_bundle(config)
        print(
            json.dumps(
                {
                    "bundle_dir": str(resolve_bundle_dir(config)),
                    "checkpoint_path": str(checkpoint_path),
                    "train_good_dir": config.patchcore.normal_train_dir,
                },
                indent=2,
            )
        )
        return

    val_good_dir = Path(args.val_good_dir or config.patchcore.val_good_dir)
    val_bad_dir = Path(args.val_bad_dir or config.patchcore.val_bad_dir)
    good_scores = _collect_scores(config, val_good_dir)
    bad_scores = _collect_scores(config, val_bad_dir)
    thresholds = calibrate_thresholds(good_scores, bad_scores, config.thresholds, dataset_version=args.dataset_version)
    bundle_dir = resolve_bundle_dir(config)
    bundle_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = bundle_dir / "model.ckpt"
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Expected fitted checkpoint at {checkpoint_path}. Run the fit command first.")
    thresholds_path = write_threshold_bundle(bundle_dir / "thresholds.json", thresholds)
    metadata_path = write_model_bundle_metadata(
        bundle_dir,
        model_name=config.patchcore.model_name,
        model_version=config.patchcore.model_version,
        backbone=config.patchcore.backbone,
        layers=config.patchcore.layers,
        image_size=config.patchcore.image_size,
        dataset_version=args.dataset_version,
        anomalib_version=_installed_anomalib_version(),
        checkpoint_path=checkpoint_path,
        thresholds_path=thresholds_path,
        calibration_mode="bad-aware" if bad_scores else "normal-only",
        score_summary=thresholds.score_summary,
    )
    print(
        json.dumps(
            {
                "bundle_dir": str(bundle_dir),
                "checkpoint_path": str(checkpoint_path),
                "thresholds_path": str(thresholds_path),
                "metadata_path": str(metadata_path),
                "good_score_count": len(good_scores),
                "bad_score_count": len(bad_scores),
                "lower_threshold": thresholds.lower_threshold,
                "upper_threshold": thresholds.upper_threshold,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
