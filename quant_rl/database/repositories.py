from __future__ import annotations

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
            self.supabase.upsert_run("quant_rl_runs", payload)

    def list_runs(self) -> list[dict[str, Any]]:
        return self.store.list_runs()

    def get(self, run_id: str) -> dict[str, Any] | None:
        return self.store.get_run(run_id)
