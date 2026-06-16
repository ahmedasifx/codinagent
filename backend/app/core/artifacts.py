"""Artifact store — persists generated outputs (images, PDFs, videos, audio).

Local-disk implementation for dev behind a small interface so it can be swapped
for S3-compatible storage later without touching callers. Files are addressed by a
generated artifact id; metadata is persisted in the `artifacts` table when a DB is
configured (see app/models/artifact.py and app/api/artifacts.py).
"""

import os
import shutil
import uuid
from dataclasses import dataclass

from .config import get_settings


@dataclass
class StoredArtifact:
    id: str
    path: str
    mime: str
    kind: str  # image | pdf | video | html | audio


def _root() -> str:
    root = get_settings().artifact_dir
    os.makedirs(root, exist_ok=True)
    return root


def store_bytes(data: bytes, kind: str, mime: str, ext: str) -> StoredArtifact:
    art_id = uuid.uuid4().hex
    path = os.path.join(_root(), f"{art_id}.{ext.lstrip('.')}")
    with open(path, "wb") as fh:
        fh.write(data)
    return StoredArtifact(id=art_id, path=path, mime=mime, kind=kind)


def store_local_file(src_path: str, kind: str, mime: str) -> StoredArtifact:
    art_id = uuid.uuid4().hex
    ext = os.path.splitext(src_path)[1] or ""
    dst = os.path.join(_root(), f"{art_id}{ext}")
    shutil.copyfile(src_path, dst)
    return StoredArtifact(id=art_id, path=dst, mime=mime, kind=kind)


def resolve_path(art_id: str) -> str | None:
    root = _root()
    for name in os.listdir(root):
        if name.startswith(art_id):
            return os.path.join(root, name)
    return None
