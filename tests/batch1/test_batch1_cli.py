from __future__ import annotations

import json
import sys

from plant_pipeline.cli.batch1_cli import main
from plant_pipeline.schemas.batch1 import Batch1PlantResult, QualityDiagnostics, QualityResult


class _FakeService:
    def __init__(self, result):
        self._result = result

    def run(self, request):
        return self._result

    def close(self):
        return None


def _result(contains_plant: bool) -> Batch1PlantResult:
    return Batch1PlantResult(
        image_id="img-1",
        image_path="/tmp/sample.png",
        valid=True,
        contains_plant=contains_plant,
        quality=QualityResult(
            is_valid=True,
            diagnostics=QualityDiagnostics(
                blur_score=100.0,
                motion_ratio=1.0,
                brightness_mean=90.0,
                dark_fraction=0.0,
                bright_fraction=0.0,
            ),
        ),
    )


def test_cli_returns_json_for_valid_image(monkeypatch, capsys):
    monkeypatch.setattr("plant_pipeline.cli.batch1_cli.load_batch1_settings", lambda path=None: object())
    monkeypatch.setattr("plant_pipeline.cli.batch1_cli.Batch1Service", lambda config: _FakeService(_result(True)))
    monkeypatch.setattr(sys, "argv", ["batch1", "--image", "/tmp/example.png"])
    main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["contains_plant"] is True


def test_cli_returns_json_for_no_plant_case(monkeypatch, capsys):
    monkeypatch.setattr("plant_pipeline.cli.batch1_cli.load_batch1_settings", lambda path=None: object())
    monkeypatch.setattr("plant_pipeline.cli.batch1_cli.Batch1Service", lambda config: _FakeService(_result(False)))
    monkeypatch.setattr(sys, "argv", ["batch1", "--image", "/tmp/example.png"])
    main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["contains_plant"] is False
