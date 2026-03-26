from __future__ import annotations

import logging

from plant_pipeline.schemas.models import FinalInspectionRecord


class LoraNotifier:
    def __init__(self, enabled: bool = False) -> None:
        self.enabled = enabled
        self.logger = logging.getLogger(__name__)

    def emit_lora_alert(self, record: FinalInspectionRecord) -> None:
        if not self.enabled or record.suspicion_label != "suspicious":
            return
        payload = {
            "alert_id": f"alert-{record.image_id}",
            "image_id": record.image_id,
            "suspicious_flag": True,
            "queue_status": record.upload_status.value,
        }
        self.logger.info("LoRa alert payload=%s", payload)
