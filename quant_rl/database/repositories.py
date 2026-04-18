from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from quant_rl.infrastructure.types import RunInfo


class RunRepository:
    def __init__(self, store, supabase=None) -> None:
        self.store = store
        self.supabase = supabase

    def save(self, run: RunInfo) -> None:
        payload = {
            "run_id": run.run_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "algorithm": run.algorithm,
            "phase": run.phase,
            "status": run.status,
            "config": run.config,
            "metrics": run.metrics,
            "artifacts": run.artifacts,
        }
        self.store.upsert_run(payload)
        if self.supabase is not None:
            self.supabase.upsert_run(
                "quant_rl_runs",
                {
                    "run_id": payload["run_id"],
                    "created_at": payload["created_at"],
                    "algorithm": payload["algorithm"],
                    "phase": payload["phase"],
                    "status": payload["status"],
                    "config_json": json.dumps(run.config, ensure_ascii=False, default=str),
                    "metrics_json": json.dumps(run.metrics, ensure_ascii=False, default=str),
                    "artifacts_json": json.dumps(run.artifacts, ensure_ascii=False, default=str),
                },
            )

    def list_runs(self) -> list[dict[str, Any]]:
        return self.store.list_runs()

    def get(self, run_id: str) -> dict[str, Any] | None:
        return self.store.get_run(run_id)
