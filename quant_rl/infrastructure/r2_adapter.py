from __future__ import annotations

from pathlib import Path


class R2ArtifactAdapter:
    def __init__(
        self,
        endpoint_url: str | None,
        access_key_id: str | None,
        secret_access_key: str | None,
        bucket: str | None,
        prefix: str,
    ) -> None:
        self.endpoint_url = endpoint_url
        self.access_key_id = access_key_id
        self.secret_access_key = secret_access_key
        self.bucket = bucket
        self.prefix = prefix
        self._client = None

    @property
    def enabled(self) -> bool:
        return all([self.endpoint_url, self.access_key_id, self.secret_access_key, self.bucket])

    def _ensure_client(self):
        if not self.enabled:
            return None
        if self._client is None:
            import boto3

            self._client = boto3.client(
                "s3",
                endpoint_url=self.endpoint_url,
                aws_access_key_id=self.access_key_id,
                aws_secret_access_key=self.secret_access_key,
            )
        return self._client

    def upload_file(self, local_path: str | Path, remote_key: str) -> str | None:
        client = self._ensure_client()
        if client is None:
            return None
        local_path = Path(local_path)
        key = f"{self.prefix.rstrip('/')}/{remote_key.lstrip('/')}"
        client.upload_file(str(local_path), self.bucket, key)
        return f"s3://{self.bucket}/{key}"
