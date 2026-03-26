from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from plant_pipeline.schemas.models import FinalInspectionRecord, SyncSummary, UploadArtifactSet, UploadStatus


SCHEMA = """
CREATE TABLE IF NOT EXISTS inspection_records (
    image_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    mission_id TEXT NOT NULL,
    valid INTEGER NOT NULL,
    contains_plant INTEGER NOT NULL,
    suspicious INTEGER NOT NULL,
    suspicion_label TEXT NOT NULL,
    suspicious_score REAL NOT NULL,
    detector_confidence REAL NOT NULL,
    upload_status TEXT NOT NULL,
    artifact_paths TEXT NOT NULL,
    metadata_blob TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS artifacts (
    image_id TEXT PRIMARY KEY,
    thumbnail_path TEXT NOT NULL,
    review_image_path TEXT NOT NULL,
    roi_path TEXT NOT NULL,
    bytes_thumbnail INTEGER NOT NULL,
    bytes_review INTEGER NOT NULL,
    bytes_roi INTEGER NOT NULL,
    compression_format TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS upload_queue (
    image_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TEXT,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS upload_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    image_id TEXT NOT NULL,
    attempted_at TEXT NOT NULL,
    success INTEGER NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS model_versions (
    image_id TEXT PRIMARY KEY,
    detector_model_version TEXT NOT NULL,
    anomaly_model_version TEXT NOT NULL
);
"""


class SQLiteStore:
    def __init__(self, sqlite_path: str) -> None:
        self.sqlite_path = Path(sqlite_path)
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.sqlite_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def save_inspection(
        self,
        record: FinalInspectionRecord,
        artifacts: UploadArtifactSet,
        detector_version: str,
        anomaly_version: str,
    ) -> None:
        self.conn.execute(
            """
            INSERT OR REPLACE INTO inspection_records (
                image_id, timestamp, mission_id, valid, contains_plant, suspicious,
                suspicion_label, suspicious_score, detector_confidence, upload_status,
                artifact_paths, metadata_blob
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.image_id,
                record.timestamp.isoformat(),
                record.mission_id,
                int(record.valid),
                int(record.contains_plant),
                int(record.suspicious),
                record.suspicion_label,
                record.suspicious_score,
                record.detector_confidence,
                record.upload_status.value,
                json.dumps(record.artifact_paths),
                json.dumps(record.metadata_blob),
            ),
        )
        self.conn.execute(
            """
            INSERT OR REPLACE INTO artifacts (
                image_id, thumbnail_path, review_image_path, roi_path, bytes_thumbnail,
                bytes_review, bytes_roi, compression_format
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                record.image_id,
                artifacts.thumbnail_path,
                artifacts.review_image_path,
                artifacts.roi_path,
                artifacts.bytes_thumbnail,
                artifacts.bytes_review,
                artifacts.bytes_roi,
                artifacts.compression_format,
            ),
        )
        self.conn.execute(
            """
            INSERT OR REPLACE INTO upload_queue (image_id, status, attempts, next_attempt_at, last_error)
            VALUES (?, ?, COALESCE((SELECT attempts FROM upload_queue WHERE image_id = ?), 0), NULL, NULL)
            """,
            (record.image_id, record.upload_status.value, record.image_id),
        )
        self.conn.execute(
            """
            INSERT OR REPLACE INTO model_versions (image_id, detector_model_version, anomaly_model_version)
            VALUES (?, ?, ?)
            """,
            (record.image_id, detector_version, anomaly_version),
        )
        self.conn.commit()

    def list_pending_uploads(self, now: Optional[datetime] = None) -> list[sqlite3.Row]:
        now = now or datetime.now(timezone.utc)
        cursor = self.conn.execute(
            """
            SELECT ir.*, a.thumbnail_path, a.review_image_path, a.roi_path, uq.attempts, uq.last_error, uq.next_attempt_at
            FROM upload_queue uq
            JOIN inspection_records ir ON ir.image_id = uq.image_id
            JOIN artifacts a ON a.image_id = uq.image_id
            WHERE uq.status IN (?, ?)
              AND (uq.next_attempt_at IS NULL OR uq.next_attempt_at <= ?)
            ORDER BY ir.timestamp ASC
            """,
            (UploadStatus.PENDING.value, UploadStatus.FAILED.value, now.isoformat()),
        )
        return cursor.fetchall()

    def mark_upload_result(
        self,
        image_id: str,
        success: bool,
        error: Optional[str] = None,
        next_attempt_at: Optional[datetime] = None,
    ) -> None:
        status = UploadStatus.UPLOADED.value if success else UploadStatus.FAILED.value
        self.conn.execute(
            "UPDATE inspection_records SET upload_status = ? WHERE image_id = ?",
            (status, image_id),
        )
        self.conn.execute(
            """
            UPDATE upload_queue
            SET status = ?, attempts = attempts + 1, next_attempt_at = ?, last_error = ?
            WHERE image_id = ?
            """,
            (
                status,
                next_attempt_at.isoformat() if next_attempt_at else None,
                error,
                image_id,
            ),
        )
        self.conn.execute(
            """
            INSERT INTO upload_attempts (image_id, attempted_at, success, error)
            VALUES (?, ?, ?, ?)
            """,
            (image_id, datetime.now(timezone.utc).isoformat(), int(success), error),
        )
        self.conn.commit()

    def compute_backoff(self, attempts: int, base_seconds: int, max_seconds: int) -> datetime:
        delay = min(max_seconds, base_seconds * (2 ** max(0, attempts)))
        return datetime.now(timezone.utc) + timedelta(seconds=delay)

    def close(self) -> None:
        self.conn.close()
