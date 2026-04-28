from __future__ import annotations

import io
import json
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from gateway.config import settings
from gateway.utils.logger import get_logger

logger = get_logger(__name__)


def _ensure_writable_dir(preferred: Path, fallback_name: str) -> Path:
    try:
        preferred.mkdir(parents=True, exist_ok=True)
        probe = preferred / f".write_probe.{uuid.uuid4().hex}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return preferred
    except OSError:
        fallback = Path(tempfile.gettempdir()) / fallback_name
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback


class R2ArtifactStore:
    def __init__(self) -> None:
        self.account_id = getattr(settings, "R2_ACCOUNT_ID", "")
        self.access_key_id = getattr(settings, "R2_ACCESS_KEY_ID", "")
        self.secret_access_key = getattr(settings, "R2_SECRET_ACCESS_KEY", "")
        self.bucket = getattr(settings, "R2_BUCKET", "")
        self.endpoint = getattr(settings, "R2_ENDPOINT", "") or (
            f"https://{self.account_id}.r2.cloudflarestorage.com" if self.account_id else ""
        )
        self.public_base_url = getattr(settings, "R2_PUBLIC_BASE_URL", "")

    def configured(self) -> bool:
        return bool(self.endpoint and self.access_key_id and self.secret_access_key and self.bucket)

    def upload_json(self, key: str, payload: dict[str, Any]) -> str | None:
        if not self.configured():
            return None

        try:
            import boto3
        except Exception as exc:
            logger.warning(f"R2 upload skipped because boto3 is unavailable: {exc}")
            return None

        try:
            client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name="auto",
            )
            buffer = io.BytesIO(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
            client.upload_fileobj(
                buffer,
                self.bucket,
                key,
                ExtraArgs={"ContentType": "application/json"},
            )
            if self.public_base_url:
                return f"{self.public_base_url.rstrip('/')}/{key}"
            return f"r2://{self.bucket}/{key}"
        except Exception as exc:
            logger.warning(f"Failed to upload artifact to R2: {exc}")
            return None

    def upload_file(self, key: str, path: Path, *, content_type: str = "application/octet-stream") -> str | None:
        if not self.configured():
            return None

        try:
            import boto3
        except Exception as exc:
            logger.warning(f"R2 upload skipped because boto3 is unavailable: {exc}")
            return None

        try:
            client = boto3.client(
                "s3",
                endpoint_url=self.endpoint,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
                region_name="auto",
            )
            with path.open("rb") as handle:
                client.upload_fileobj(
                    handle,
                    self.bucket,
                    key,
                    ExtraArgs={"ContentType": content_type},
                )
            if self.public_base_url:
                return f"{self.public_base_url.rstrip('/')}/{key}"
            return f"r2://{self.bucket}/{key}"
        except Exception as exc:
            logger.warning(f"Failed to upload file artifact to R2: {exc}")
            return None


class SupabaseStorageArtifactStore:
    def __init__(self, get_client: Callable[[], Any] | None = None) -> None:
        self._get_client = get_client
        self.bucket = getattr(settings, "SUPABASE_STORAGE_BUCKET", "quant-artifacts") or "quant-artifacts"
        self.path_prefix = (getattr(settings, "SUPABASE_STORAGE_PATH_PREFIX", "quant") or "").strip("/")
        self.public = bool(getattr(settings, "SUPABASE_STORAGE_PUBLIC", True))
        self._bucket_verified = False

    @staticmethod
    def _is_real_client(client: Any) -> bool:
        return client is not None and getattr(client, "backend", "") != "in_memory"

    def configured(self) -> bool:
        return bool(self._get_client is not None and self.bucket)

    def available(self, client: Any | None = None) -> bool:
        if not self.configured():
            return False

        resolved = client
        if resolved is None:
            try:
                resolved = self._get_client() if self._get_client is not None else None
            except Exception:
                return False

        return self._is_real_client(resolved) and hasattr(resolved, "storage")

    def upload_json(self, key: str, payload: dict[str, Any]) -> str | None:
        if not self.configured():
            return None

        try:
            client = self._get_client() if self._get_client is not None else None
        except Exception as exc:
            logger.warning(f"Supabase Storage upload skipped because client is unavailable: {exc}")
            return None

        if not self.available(client):
            return None

        object_key = self._normalize_key(key)

        try:
            self._ensure_bucket(client)
            client.storage.from_(self.bucket).upload(
                object_key,
                json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
                file_options={
                    "content-type": "application/json",
                    "cache-control": "3600",
                    "upsert": "true",
                },
            )
            return self._build_artifact_uri(client, object_key)
        except Exception as exc:
            logger.warning(f"Failed to upload artifact to Supabase Storage: {exc}")
            return None

    def upload_file(self, key: str, path: Path, *, content_type: str = "application/octet-stream") -> str | None:
        if not self.configured():
            return None

        try:
            client = self._get_client() if self._get_client is not None else None
        except Exception as exc:
            logger.warning(f"Supabase Storage upload skipped because client is unavailable: {exc}")
            return None

        if not self.available(client):
            return None

        object_key = f"{self.path_prefix}/{key}".strip("/") if self.path_prefix else key
        try:
            with path.open("rb") as handle:
                data = handle.read()
            client.storage.from_(self.bucket).upload(
                object_key,
                data,
                {
                    "content-type": content_type,
                    "x-upsert": "true",
                },
            )
            return self._build_artifact_uri(client, object_key)
        except Exception as exc:
            logger.warning(f"Failed to upload file artifact to Supabase Storage: {exc}")
            return None

    def _normalize_key(self, key: str) -> str:
        normalized = str(key or "").strip().lstrip("/")
        if self.path_prefix and not normalized.startswith(f"{self.path_prefix}/"):
            return f"{self.path_prefix}/{normalized}"
        return normalized

    def _ensure_bucket(self, client: Any) -> None:
        if self._bucket_verified:
            return

        storage = client.storage
        try:
            buckets = storage.list_buckets() or []
        except Exception as exc:
            raise RuntimeError(f"Unable to list Supabase Storage buckets: {exc}") from exc

        exists = any(self._bucket_id(item) == self.bucket for item in buckets)
        if not exists:
            try:
                storage.create_bucket(
                    self.bucket,
                    options={
                        "public": self.public,
                        "allowed_mime_types": ["application/json"],
                    },
                )
                logger.info(f"Created Supabase Storage bucket: {self.bucket}")
            except Exception as exc:
                message = str(exc).lower()
                if not any(token in message for token in ("already exists", "duplicate", "exists")):
                    raise

        self._bucket_verified = True

    @staticmethod
    def _bucket_id(bucket: Any) -> str:
        if isinstance(bucket, dict):
            return str(bucket.get("id") or bucket.get("name") or "")
        return str(getattr(bucket, "id", "") or getattr(bucket, "name", ""))

    def _build_artifact_uri(self, client: Any, object_key: str) -> str:
        if self.public:
            try:
                return client.storage.from_(self.bucket).get_public_url(object_key)
            except Exception as exc:
                logger.info(f"Falling back to supabase:// URI for {object_key}: {exc}")
        return f"supabase://{self.bucket}/{object_key}"


class QuantStorageGateway:
    def __init__(self, get_client: Callable[[], Any] | None = None) -> None:
        self._get_client = get_client
        self._file_lock = threading.RLock()
        self.base_dir = _ensure_writable_dir(
            Path(__file__).resolve().parents[2] / "storage" / "quant",
            "quant-esg-artifacts",
        )
        self.r2_store = R2ArtifactStore()
        self.supabase_storage_store = SupabaseStorageArtifactStore(get_client=get_client)

    def _resolve_client(self) -> Any | None:
        if self._get_client is None:
            return None
        try:
            return self._get_client()
        except Exception:
            return None

    @staticmethod
    def _is_real_supabase_client(client: Any) -> bool:
        return client is not None and getattr(client, "backend", "") != "in_memory"

    def _preferred_artifact_backend(self, supabase_storage_ready: bool) -> str:
        if self.r2_store.configured():
            return "r2"
        if supabase_storage_ready:
            return "supabase_storage"
        return "local"

    def status(self) -> dict[str, Any]:
        client = self._resolve_client()
        supabase_ready = self._is_real_supabase_client(client)
        supabase_storage_ready = self.supabase_storage_store.available(client)
        preferred_backend = self._preferred_artifact_backend(supabase_storage_ready)

        return {
            "artifact_dir": str(self.base_dir),
            "supabase_ready": supabase_ready,
            "supabase_storage_ready": supabase_storage_ready,
            "supabase_storage_bucket": self.supabase_storage_store.bucket,
            "r2_ready": self.r2_store.configured(),
            "preferred_artifact_backend": preferred_backend,
            "mode": "hybrid_cloud" if supabase_ready or self.r2_store.configured() or supabase_storage_ready else "local_fallback",
        }

    def persist_record(
        self,
        record_type: str,
        record_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        directory = _ensure_writable_dir(self.base_dir / record_type, f"quant-esg-artifacts/{record_type}")

        local_path = directory / f"{record_id}.json"
        self._atomic_write_json(local_path, payload)

        artifact_key = f"quant/{record_type}/{record_id}.json"
        artifact_uri = self.r2_store.upload_json(artifact_key, payload)
        artifact_backend = "r2" if artifact_uri else "local"
        if artifact_uri is None:
            artifact_uri = self.supabase_storage_store.upload_json(artifact_key, payload)
            if artifact_uri is not None:
                artifact_backend = "supabase_storage"
        mirror_ok = self._mirror_to_supabase(record_type, record_id, payload, artifact_uri)

        return {
            "record_type": record_type,
            "record_id": record_id,
            "local_path": str(local_path),
            "artifact_key": artifact_key,
            "artifact_uri": artifact_uri,
            "artifact_backend": artifact_backend,
            "supabase_mirrored": mirror_ok,
        }

    def _atomic_write_json(self, path: Path, payload: dict[str, Any]) -> None:
        tmp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        data = json.dumps(payload, ensure_ascii=False, indent=2)
        with self._file_lock:
            try:
                tmp_path.write_text(data, encoding="utf-8")
                tmp_path.replace(path)
            finally:
                if tmp_path.exists():
                    try:
                        tmp_path.unlink()
                    except OSError as exc:
                        logger.warning(f"Failed to remove temporary JSON file {tmp_path}: {exc}")

    def upload_artifact_file(
        self,
        key: str,
        path: Path,
        *,
        content_type: str = "application/octet-stream",
    ) -> dict[str, Any]:
        artifact_uri = self.r2_store.upload_file(key, path, content_type=content_type)
        artifact_backend = "r2" if artifact_uri else "local"
        if artifact_uri is None:
            artifact_uri = self.supabase_storage_store.upload_file(key, path, content_type=content_type)
            if artifact_uri is not None:
                artifact_backend = "supabase_storage"
        return {
            "artifact_key": key,
            "artifact_uri": artifact_uri,
            "artifact_backend": artifact_backend,
            "uploaded": artifact_uri is not None,
        }

    def load_record(self, record_type: str, record_id: str) -> dict[str, Any] | None:
        local_path = self.base_dir / record_type / f"{record_id}.json"
        if not local_path.exists():
            return None
        return json.loads(local_path.read_text(encoding="utf-8"))

    def list_records(self, record_type: str) -> list[dict[str, Any]]:
        directory = self.base_dir / record_type
        if not directory.exists():
            return []

        rows: list[dict[str, Any]] = []
        for path in sorted(directory.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                rows.append(json.loads(path.read_text(encoding="utf-8")))
            except Exception as exc:
                logger.warning(f"Failed to read {path}: {exc}")
        return rows

    def append_audit_event(
        self,
        *,
        category: str,
        action: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        audit_dir = _ensure_writable_dir(self.base_dir / "audit", "quant-esg-artifacts/audit")
        day_key = datetime.now(timezone.utc).strftime("%Y%m%d")
        local_path = audit_dir / f"audit-{day_key}.jsonl"
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "category": category,
            "action": action,
            "payload": payload,
        }
        try:
            with self._file_lock, local_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(event, ensure_ascii=False) + "\n")
        except OSError as exc:
            logger.warning(f"Failed to append audit event to {local_path}: {exc}")
            raise

        return {
            "local_path": str(local_path),
            "event": event,
        }

    def _mirror_to_supabase(
        self,
        record_type: str,
        record_id: str,
        payload: dict[str, Any],
        artifact_uri: str | None,
    ) -> bool:
        if self._get_client is None:
            return False

        try:
            client = self._get_client()
        except Exception as exc:
            logger.warning(f"Supabase mirror unavailable: {exc}")
            return False

        try:
            client.table("quant_run_registry").insert(
                {
                    "run_id": f"{record_type}:{record_id}",
                    "run_type": record_type,
                    "payload": payload,
                    "artifact_uri": artifact_uri,
                    "created_at": payload.get("generated_at") or payload.get("created_at"),
                }
            ).execute()
            return True
        except Exception as exc:
            logger.info(f"Supabase mirror skipped for {record_type}/{record_id}: {exc}")
            return False
