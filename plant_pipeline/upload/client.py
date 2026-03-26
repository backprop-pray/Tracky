from __future__ import annotations

import json
import socket
from pathlib import Path

import requests

from plant_pipeline.config.settings import UploadSettings


class UploadClient:
    def __init__(self, settings: UploadSettings) -> None:
        self.settings = settings

    def wifi_available(self) -> bool:
        try:
            with socket.create_connection(
                (self.settings.wifi_check_host, self.settings.wifi_check_port),
                timeout=1.0,
            ):
                return True
        except OSError:
            return False

    def upload_record(self, payload: dict, files: dict[str, str]) -> None:
        multipart = {}
        opened = []
        try:
            for name, path in files.items():
                handle = open(Path(path), "rb")
                opened.append(handle)
                multipart[name] = handle
            response = requests.post(
                self.settings.endpoint,
                data={"metadata": json.dumps(payload)},
                files=multipart,
                timeout=self.settings.timeout_seconds,
            )
            response.raise_for_status()
        finally:
            for handle in opened:
                handle.close()
