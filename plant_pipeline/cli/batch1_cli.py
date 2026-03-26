from __future__ import annotations

import argparse
import json
import logging

from plant_pipeline.config.settings import load_batch1_settings
from plant_pipeline.schemas.batch1 import Batch1Request
from plant_pipeline.services.batch1_service import Batch1Service


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Batch 1 plant ROI pipeline")
    parser.add_argument("--image", required=True, help="Path to an input image")
    parser.add_argument("--config", default=None, help="Path to batch1 YAML config")
    parser.add_argument("--image-id", default=None)
    parser.add_argument("--mission-id", default=None)
    parser.add_argument("--row-id", default=None)
    parser.add_argument("--section-id", default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    config = load_batch1_settings(args.config)
    logging.basicConfig(level=logging.INFO)
    service = Batch1Service(config)
    try:
        result = service.run(
            Batch1Request(
                image_path=args.image,
                image_id=args.image_id,
                mission_id=args.mission_id,
                row_id=args.row_id,
                section_id=args.section_id,
            )
        )
        print(json.dumps(result.model_dump(mode="json"), indent=2))
    finally:
        service.close()


if __name__ == "__main__":
    main()
