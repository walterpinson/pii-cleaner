"""File utility functions."""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {".csv", ".pdf"}


def is_supported(path: Path) -> bool:
    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def collect_files(
    directory: Path,
    recursive: bool = False,
    include_globs: list[str] | None = None,
    exclude_globs: list[str] | None = None,
) -> tuple[list[Path], list[Path]]:
    """Collect supported files from a directory."""
    include_globs = include_globs or ["*.csv", "*.pdf"]
    exclude_globs = exclude_globs or []

    pattern = "**/*" if recursive else "*"
    all_files = [p for p in directory.glob(pattern) if p.is_file()]

    supported = []
    skipped = []

    for f in all_files:
        name = f.name

        excluded = any(fnmatch.fnmatch(name, g) for g in exclude_globs)
        if excluded:
            skipped.append(f)
            continue

        included = any(fnmatch.fnmatch(name, g) for g in include_globs)
        if included and is_supported(f):
            supported.append(f)
        else:
            skipped.append(f)

    return sorted(supported), sorted(skipped)


def make_output_path(
    input_path: Path,
    input_base: Path,
    output_base: Path,
) -> Path:
    """Compute output path preserving relative structure."""
    try:
        rel = input_path.relative_to(input_base)
    except ValueError:
        rel = Path(input_path.name)
    return output_base / rel
