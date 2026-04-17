from __future__ import annotations

from functools import lru_cache

from quant_rl.database.repositories import RunRepository
from quant_rl.database.sqlite_store import SQLiteRunStore
from quant_rl.infrastructure.storage import ArtifactStore
from quant_rl.infrastructure.supabase_adapter import SupabaseMetadataAdapter
from quant_rl.infrastructure.settings import get_settings


@lru_cache(maxsize=1)
def get_run_repository() -> RunRepository:
    settings = get_settings()
    store = SQLiteRunStore(settings.sqlite_db_path)
    supabase = SupabaseMetadataAdapter(settings.supabase_url, settings.supabase_key)
    return RunRepository(store=store, supabase=supabase)


@lru_cache(maxsize=1)
def get_artifact_store() -> ArtifactStore:
    return ArtifactStore()
