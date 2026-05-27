"""Pluggable file storage backend (Phase 11b / T-008).

Two implementations:

  * `LocalDiskStorage` — writes to a configured directory. The default
    for dev + tests. The `storage_uri` it returns is `file://<absolute
    path>`.
  * `S3Storage` — placeholder; the real S3 backend is wired in by
    setting `EDUZIM_ATTACHMENT_STORAGE_S3_*` env vars at boot. Not
    implemented in this revision; raises NotImplementedError.

Each implementation exposes the same interface:

    save(data: bytes, *, school_id, mime_type, suggested_name) -> str  # returns storage_uri
    delete(storage_uri: str) -> None
    open(storage_uri: str) -> bytes

The service uses `get_storage()` which reads `EDUZIM_ATTACHMENT_BACKEND`
from the environment to pick the implementation. Tests can monkey-patch
the module-level `_storage` to inject a fake.
"""
from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Protocol


class StorageBackend(Protocol):
    def save(
        self, data: bytes, *,
        school_id: uuid.UUID, mime_type: str, suggested_name: str,
    ) -> str: ...
    def delete(self, storage_uri: str) -> None: ...
    def open(self, storage_uri: str) -> bytes: ...


class LocalDiskStorage:
    """Writes to the configured directory under school-scoped subdirs.

    Files are stored as `<root>/<school_id>/<uuid>-<safe_filename>`.
    The school_id subdir means a `rm -rf <root>/<school_id>` is a
    clean wipe for the data-erasure path (Phase 9 / right-to-delete).
    """

    def __init__(self, root: str | os.PathLike):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _safe_name(self, suggested_name: str) -> str:
        # Drop any path components + cap length. We don't trust
        # client-supplied names.
        bare = os.path.basename(suggested_name).strip()
        bare = "".join(c for c in bare if c.isalnum() or c in "._-") or "file"
        return bare[:128]

    def save(self, data: bytes, *, school_id, mime_type, suggested_name) -> str:
        school_dir = self.root / str(school_id)
        school_dir.mkdir(parents=True, exist_ok=True)
        name = f"{uuid.uuid4()}-{self._safe_name(suggested_name)}"
        path = school_dir / name
        path.write_bytes(data)
        return f"file://{path.resolve()}"

    def delete(self, storage_uri: str) -> None:
        if not storage_uri.startswith("file://"):
            return
        path = Path(storage_uri[len("file://"):])
        try:
            path.unlink()
        except FileNotFoundError:
            pass

    def open(self, storage_uri: str) -> bytes:
        if not storage_uri.startswith("file://"):
            raise ValueError(
                f"LocalDiskStorage cannot read non-file URI: {storage_uri}"
            )
        path = Path(storage_uri[len("file://"):])
        return path.read_bytes()


class S3Storage:
    """Placeholder. Production wiring is a Phase 12 / infra-track task.
    Today this exists so the service layer can `isinstance` check
    against the protocol without needing both backends to be functional."""

    def __init__(self, bucket: str, region: str, prefix: str = "attachments"):
        self.bucket = bucket
        self.region = region
        self.prefix = prefix

    def save(self, *_a, **_kw) -> str:
        raise NotImplementedError(
            "S3Storage requires boto3 wiring + bucket policy review. "
            "Not enabled in this revision."
        )

    def delete(self, *_a, **_kw) -> None:
        raise NotImplementedError("S3Storage.delete: see save()")

    def open(self, *_a, **_kw) -> bytes:
        raise NotImplementedError("S3Storage.open: see save()")


_storage: StorageBackend | None = None


def get_storage() -> StorageBackend:
    """Module-level singleton — pick the backend once at first call."""
    global _storage
    if _storage is None:
        backend = os.environ.get("EDUZIM_ATTACHMENT_BACKEND", "local").lower()
        if backend == "s3":
            _storage = S3Storage(
                bucket=os.environ.get("EDUZIM_ATTACHMENT_S3_BUCKET", ""),
                region=os.environ.get("EDUZIM_ATTACHMENT_S3_REGION", ""),
            )
        else:
            root = os.environ.get(
                "EDUZIM_ATTACHMENT_LOCAL_ROOT",
                "/tmp/eduzim-attachments",
            )
            _storage = LocalDiskStorage(root)
    return _storage


def reset_storage_for_tests() -> None:
    """Clear the cached storage backend — call from test fixtures so
    a per-test temp directory can be re-picked from env."""
    global _storage
    _storage = None
