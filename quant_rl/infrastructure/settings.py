from __future__ import annotations

import os
from dataclasses import dataclass
from dataclasses import field
from functools import lru_cache
from pathlib import Path


def _first_env(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return default


@dataclass(slots=True)
class Settings:
    app_env: str = field(default_factory=lambda: _first_env("APP_ENV", "APP_MODE", default="local"))
    app_host: str = field(default_factory=lambda: _first_env("APP_HOST", default="0.0.0.0"))
    app_port: int = field(default_factory=lambda: int(_first_env("APP_PORT", default="8000")))

    project_name: str = "ESG Quant RL Patch"
    api_prefix: str = "/api/v1/quant/rl"

    storage_dir: Path = field(default_factory=lambda: Path(_first_env("QUANT_RL_STORAGE_DIR", "STORAGE_DIR", default="storage/quant/rl")))
    sqlite_db_path: Path = field(default_factory=lambda: Path(_first_env("QUANT_RL_SQLITE_DB_PATH", "SQLITE_DB_PATH", default="storage/quant/rl/metadata.sqlite3")))
    experiment_root: Path = field(default_factory=lambda: Path(_first_env("QUANT_RL_EXPERIMENT_ROOT", default="storage/quant/rl-experiments")))

    supabase_url: str | None = field(default_factory=lambda: _first_env("SUPABASE_URL") or None)
    supabase_key: str | None = field(default_factory=lambda: _first_env("SUPABASE_API_KEY", "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_KEY") or None)

    r2_endpoint_url: str | None = field(default_factory=lambda: _first_env("R2_ENDPOINT_URL", "R2_ENDPOINT") or None)
    r2_access_key_id: str | None = field(default_factory=lambda: _first_env("R2_ACCESS_KEY_ID") or None)
    r2_secret_access_key: str | None = field(default_factory=lambda: _first_env("R2_SECRET_ACCESS_KEY") or None)
    r2_bucket: str | None = field(default_factory=lambda: _first_env("R2_BUCKET") or None)
    r2_prefix: str = field(default_factory=lambda: _first_env("R2_PREFIX", default="quant/rl-agent"))

    @property
    def artifacts_dir(self) -> Path:
        return self.storage_dir / "artifacts"

    @property
    def checkpoints_dir(self) -> Path:
        return self.storage_dir / "checkpoints"

    @property
    def reports_dir(self) -> Path:
        return self.storage_dir / "reports"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    settings.artifacts_dir.mkdir(parents=True, exist_ok=True)
    settings.checkpoints_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)
    settings.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.experiment_root.mkdir(parents=True, exist_ok=True)
    return settings
