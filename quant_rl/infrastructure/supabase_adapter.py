from __future__ import annotations

from typing import Any

from gateway.utils.logger import get_logger

logger = get_logger(__name__)


class SupabaseMetadataAdapter:
    def __init__(self, url: str | None, key: str | None) -> None:
        self.url = url
        self.key = key
        self._client = None
        self._degraded = False

    @property
    def enabled(self) -> bool:
        return bool(self.url and self.key and not self._degraded)

    def _ensure_client(self):
        if not self.enabled:
            return None
        if self._client is None:
            try:
                from supabase import create_client
            except ImportError:
                return None
            self._client = create_client(self.url, self.key)
        return self._client

    def upsert_run(self, table: str, payload: dict[str, Any]) -> None:
        client = self._ensure_client()
        if client is None:
            return
        try:
            client.table(table).upsert(payload).execute()
        except Exception as exc:
            self._degraded = True
            logger.warning(f"[QuantRL] Supabase upsert degraded for table {table}: {exc}")
