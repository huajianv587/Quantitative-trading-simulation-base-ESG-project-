from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from quant_rl.infrastructure.r2_adapter import R2ArtifactAdapter
from quant_rl.infrastructure.settings import get_settings


class ArtifactStore:
    def __init__(self) -> None:
        settings = get_settings()
        self.settings = settings
        self.r2 = R2ArtifactAdapter(
            endpoint_url=settings.r2_endpoint_url,
            access_key_id=settings.r2_access_key_id,
            secret_access_key=settings.r2_secret_access_key,
            bucket=settings.r2_bucket,
            prefix=settings.r2_prefix,
        )

    def run_dir(self, run_id: str) -> Path:
        path = self.settings.artifacts_dir / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def checkpoint_path(self, run_id: str, name: str = "model.pt") -> Path:
        path = self.settings.checkpoints_dir / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path / name

    def report_dir(self, run_id: str) -> Path:
        path = self.settings.reports_dir / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save_json(self, run_id: str, filename: str, payload: dict[str, Any]) -> str:
        path = self.run_dir(run_id) / filename
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._upload(path, f"{run_id}/{filename}")
        return str(path)

    def save_text(self, run_id: str, filename: str, content: str) -> str:
        path = self.run_dir(run_id) / filename
        path.write_text(content, encoding="utf-8")
        self._upload(path, f"{run_id}/{filename}")
        return str(path)

    def save_csv(self, run_id: str, filename: str, df: pd.DataFrame) -> str:
        path = self.run_dir(run_id) / filename
        df.to_csv(path, index=False)
        self._upload(path, f"{run_id}/{filename}")
        return str(path)

    def save_report_file(self, run_id: str, filename: str, source_path: str | Path) -> str:
        source_path = Path(source_path)
        target = self.report_dir(run_id) / filename
        target.write_bytes(source_path.read_bytes())
        self._upload(target, f"reports/{run_id}/{filename}")
        return str(target)

    def _upload(self, path: Path, remote_key: str) -> None:
        try:
            self.r2.upload_file(path, remote_key)
        except Exception:
            return
