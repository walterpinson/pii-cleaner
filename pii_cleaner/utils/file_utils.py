"""File utility functions."""

from __future__ import annotations

import fnmatch
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# Matches formatted financial amounts: requires a decimal point and caps the
# integer part to 9 digits, so card/account numbers (15-16 digits, no decimal)
# are NOT matched and still pass through to PII analysis.
# Matches: -40.00  1,234.56  $100.00  -1,234,567.89  15.5%
# Does not match: 4111111111111234  1234567890  john@example.com
AMOUNT_RE = re.compile(r'^-?\$?\d{1,9}(?:,\d{3})*\.\d+%?$')

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


def clean_path(path: Path) -> Path:
    """Return path with '.clean' inserted before the suffix.

    Examples:
        sales.csv  -> sales.clean.csv
        report.pdf -> report.clean.pdf
    """
    return path.parent / f"{path.stem}.clean{path.suffix}"


def peer_clean_dir(directory: Path) -> Path:
    """Return the peer *_clean directory for a given directory path.

    The returned path is a sibling of *directory*, not a child of it.

    Examples:
        /data/bank           -> /data/bank_clean
        /home/user/exports   -> /home/user/exports_clean
    """
    return directory.parent / f"{directory.name}_clean"


def split_csv_sections(raw_text: str) -> list[str]:
    """Split raw CSV text into sections separated by blank lines."""
    sections = []
    current_lines: list[str] = []
    for line in raw_text.splitlines():
        if line.strip() == "":
            if current_lines:
                sections.append("\n".join(current_lines))
                current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append("\n".join(current_lines))
    return sections
