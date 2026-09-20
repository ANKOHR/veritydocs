from __future__ import annotations

import hashlib
import json
from pathlib import Path


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


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
