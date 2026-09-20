from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Protocol


class ObjectStore(Protocol):
    def put_bytes(self, key: str, value: bytes) -> str: ...

    def get_bytes(self, key: str) -> bytes: ...

    def put_json(self, key: str, value: object) -> str: ...

    def exists(self, key: str) -> bool: ...


class LocalObjectStore:
    """Local implementation of the object-store boundary used by the API and tests."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, key: str, value: bytes) -> str:
        target = self.root / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value)
        return key

    def get_bytes(self, key: str) -> bytes:
        return (self.root / key).read_bytes()

    def put_json(self, key: str, value: object) -> str:
        return self.put_bytes(key, json.dumps(value, indent=2, default=str).encode("utf-8"))

    def exists(self, key: str) -> bool:
        return (self.root / key).exists()


class StorageConfigurationError(RuntimeError):
    """Raised when the selected object-store backend is not configured."""


class S3ObjectStore:
    """S3-compatible object store used by the deployed API and worker."""

    def __init__(
        self,
        endpoint_url: str | None,
        bucket: str | None,
        access_key_id: str | None,
        secret_access_key: str | None,
        region: str,
        addressing_style: str = "path",
    ) -> None:
        missing = [
            name
            for name, value in {
                "S3_ENDPOINT_URL": endpoint_url,
                "S3_BUCKET": bucket,
                "S3_ACCESS_KEY_ID": access_key_id,
                "S3_SECRET_ACCESS_KEY": secret_access_key,
            }.items()
            if not value
        ]
        if missing:
            raise StorageConfigurationError(
                "S3 storage is selected but missing: " + ", ".join(missing)
            )
        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
            config=Config(s3={"addressing_style": addressing_style}),
        )

    def put_bytes(self, key: str, value: bytes) -> str:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=value)
        return key

    def get_bytes(self, key: str) -> bytes:
        response = self.client.get_object(Bucket=self.bucket, Key=key)
        return response["Body"].read()

    def put_json(self, key: str, value: object) -> str:
        return self.put_bytes(key, json.dumps(value, indent=2, default=str).encode("utf-8"))

    def exists(self, key: str) -> bool:
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
        except self.client.exceptions.ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return True


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
