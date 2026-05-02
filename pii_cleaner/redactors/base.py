"""Base redactor interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class RedactionResult:
    """Result of a redaction operation."""
    original: str
    redacted: str
    entities: list[dict] = field(default_factory=list)
    changed: bool = False

    def __post_init__(self):
        self.changed = self.original != self.redacted
