from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


class SQLiteRunStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    algorithm TEXT NOT NULL,
                    phase TEXT NOT NULL,
                    status TEXT NOT NULL,
                    config_json TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    artifacts_json TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def upsert_run(self, payload: dict[str, Any]) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO runs (run_id, created_at, algorithm, phase, status, config_json, metrics_json, artifacts_json)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    created_at=excluded.created_at,
                    algorithm=excluded.algorithm,
                    phase=excluded.phase,
                    status=excluded.status,
                    config_json=excluded.config_json,
                    metrics_json=excluded.metrics_json,
                    artifacts_json=excluded.artifacts_json
                """,
                (
                    payload["run_id"],
                    payload["created_at"],
                    payload["algorithm"],
                    payload["phase"],
                    payload["status"],
                    json.dumps(payload.get("config", {}), ensure_ascii=False),
                    json.dumps(payload.get("metrics", {}), ensure_ascii=False),
                    json.dumps(payload.get("artifacts", {}), ensure_ascii=False),
                ),
            )
            conn.commit()

    def list_runs(self) -> list[dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM runs ORDER BY created_at DESC").fetchall()
        return [self._row_to_dict(row) for row in rows]

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
        return self._row_to_dict(row) if row else None

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "run_id": row["run_id"],
            "created_at": row["created_at"],
            "algorithm": row["algorithm"],
            "phase": row["phase"],
            "status": row["status"],
            "config": json.loads(row["config_json"]),
            "metrics": json.loads(row["metrics_json"]),
            "artifacts": json.loads(row["artifacts_json"]),
        }
