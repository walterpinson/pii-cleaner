"""Run report generation."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class FileResult:
    input_path: str
    output_paths: list[str]
    file_type: str
    success: bool
    rows_or_pages: int
    fields_changed: int
    entities_by_type: dict[str, int]
    warnings: list[str]
    error: str | None
    input_hash: str | None
    output_hash: str | None


@dataclass
class RunReport:
    run_id: str
    started_at: str
    completed_at: str
    dry_run: bool
    config_path: str | None
    files: list[FileResult] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return len(self.files)

    @property
    def successful_files(self) -> int:
        return sum(1 for f in self.files if f.success)

    @property
    def failed_files(self) -> int:
        return sum(1 for f in self.files if not f.success)

    @property
    def aggregate_entities(self) -> dict[str, int]:
        agg: dict[str, int] = {}
        for f in self.files:
            for k, v in f.entities_by_type.items():
                agg[k] = agg.get(k, 0) + v
        return agg

    def to_dict(self) -> dict:
        d = asdict(self)
        d["summary"] = {
            "total_files": self.total_files,
            "successful_files": self.successful_files,
            "failed_files": self.failed_files,
            "aggregate_entities": self.aggregate_entities,
        }
        return d

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2, default=str)


def load_report(path: Path) -> dict:
    """Load a saved run report."""
    with open(path) as f:
        return json.load(f)
