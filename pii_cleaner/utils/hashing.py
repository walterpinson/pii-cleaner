"""File hashing utilities."""

from __future__ import annotations

import hashlib
from pathlib import Path


def hash_file(path: Path, algorithm: str = "sha256") -> str:
    """Compute a hash of a file's contents."""
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
