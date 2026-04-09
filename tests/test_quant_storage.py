from __future__ import annotations

from pathlib import Path

from gateway.config import settings
from gateway.quant.storage import QuantStorageGateway


class _Result:
    def __init__(self, data=None):
        self.data = data or []


class _TableQuery:
    def __init__(self, client: "_FakeSupabaseClient", name: str):
        self._client = client
        self._name = name
        self._payload = None

    def insert(self, payload):
        self._payload = payload
        return self

    def execute(self):
        self._client.mirrored.append((self._name, self._payload))
        return _Result([self._payload])


class _BucketProxy:
    def __init__(self, storage: "_FakeStorage", bucket: str):
        self._storage = storage
        self._bucket = bucket

    def upload(self, path, file, file_options=None):
        payload = file if isinstance(file, bytes) else file.read()
        self._storage.uploads.append(
            {
                "bucket": self._bucket,
                "path": path,
                "payload": payload,
                "file_options": dict(file_options or {}),
            }
        )
        return {"path": path}

    def get_public_url(self, path, options=None):
        return f"https://example.supabase.local/storage/v1/object/public/{self._bucket}/{path}"


class _FakeStorage:
    def __init__(self):
        self._buckets: list[str] = []
        self.uploads: list[dict] = []
        self.created: list[tuple[str, dict | None]] = []

    def list_buckets(self):
        return [{"id": bucket} for bucket in self._buckets]

    def create_bucket(self, bucket_id, name=None, options=None):
        if bucket_id not in self._buckets:
            self._buckets.append(bucket_id)
            self.created.append((bucket_id, dict(options or {})))
        return {"id": bucket_id}

    def from_(self, bucket):
        return _BucketProxy(self, bucket)


class _FakeSupabaseClient:
    def __init__(self):
        self.storage = _FakeStorage()
        self.mirrored: list[tuple[str, dict]] = []

    def table(self, name):
        return _TableQuery(self, name)


class _InMemoryClient:
    backend = "in_memory"

    def __init__(self):
        self.mirrored: list[tuple[str, dict]] = []

    def table(self, name):
        return _TableQuery(self, name)


def _configure_storage(monkeypatch):
    monkeypatch.setattr(settings, "R2_ACCOUNT_ID", "")
    monkeypatch.setattr(settings, "R2_ACCESS_KEY_ID", "")
    monkeypatch.setattr(settings, "R2_SECRET_ACCESS_KEY", "")
    monkeypatch.setattr(settings, "R2_BUCKET", "")
    monkeypatch.setattr(settings, "R2_ENDPOINT", "")
    monkeypatch.setattr(settings, "R2_PUBLIC_BASE_URL", "")
    monkeypatch.setattr(settings, "SUPABASE_STORAGE_BUCKET", "quant-artifacts")
    monkeypatch.setattr(settings, "SUPABASE_STORAGE_PUBLIC", True)
    monkeypatch.setattr(settings, "SUPABASE_STORAGE_PATH_PREFIX", "quant")


def test_quant_storage_falls_back_to_supabase_storage_when_r2_missing(tmp_path, monkeypatch):
    _configure_storage(monkeypatch)
    fake_client = _FakeSupabaseClient()
    gateway = QuantStorageGateway(get_client=lambda: fake_client)
    gateway.base_dir = tmp_path / "quant"
    gateway.base_dir.mkdir(parents=True, exist_ok=True)

    payload = {"generated_at": "2026-04-09T00:00:00Z", "value": 42}
    result = gateway.persist_record("research_runs", "research-001", payload)
    status = gateway.status()

    assert Path(result["local_path"]).exists()
    assert result["artifact_backend"] == "supabase_storage"
    assert result["artifact_uri"].startswith("https://example.supabase.local/")
    assert result["artifact_key"] == "quant/research_runs/research-001.json"
    assert result["supabase_mirrored"] is True
    assert fake_client.storage.created == [
        ("quant-artifacts", {"public": True, "allowed_mime_types": ["application/json"]})
    ]
    assert fake_client.storage.uploads[0]["path"] == "quant/research_runs/research-001.json"
    assert fake_client.mirrored[0][0] == "quant_run_registry"
    assert status["preferred_artifact_backend"] == "supabase_storage"
    assert status["supabase_storage_ready"] is True


def test_quant_storage_stays_local_when_only_in_memory_supabase_is_available(tmp_path, monkeypatch):
    _configure_storage(monkeypatch)
    memory_client = _InMemoryClient()
    gateway = QuantStorageGateway(get_client=lambda: memory_client)
    gateway.base_dir = tmp_path / "quant"
    gateway.base_dir.mkdir(parents=True, exist_ok=True)

    result = gateway.persist_record("executions", "execution-001", {"generated_at": "2026-04-09T00:00:00Z"})
    status = gateway.status()

    assert Path(result["local_path"]).exists()
    assert result["artifact_backend"] == "local"
    assert result["artifact_uri"] is None
    assert result["supabase_mirrored"] is True
    assert status["mode"] == "local_fallback"
    assert status["supabase_ready"] is False
    assert status["supabase_storage_ready"] is False
    assert status["preferred_artifact_backend"] == "local"
