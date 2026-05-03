"""Configuration management for pii-cleaner."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FinancialRule(BaseModel):
    preserve_last_n: int = 4
    mask_char: str = "X"


class FinancialRules(BaseModel):
    account_number: FinancialRule = Field(default_factory=FinancialRule)
    card_number: FinancialRule = Field(default_factory=FinancialRule)
    routing_number: FinancialRule = Field(default_factory=FinancialRule)


class CustomPattern(BaseModel):
    name: str
    regex: str
    action: str = "replace"
    replacement: str = "[REDACTED]"


class EntityConfig(BaseModel):
    enabled: bool = True
    replacement: str = "[{entity_type}]"
    mask_char: str = "X"
    confidence_threshold: float = 0.5


class OutputFormats(BaseModel):
    txt: bool = True
    md: bool = True
    json_report: bool = True
    pdf: bool = False


class CSVConfig(BaseModel):
    sensitive_columns: list[str] = Field(default_factory=list)
    mask_columns: list[str] = Field(default_factory=list)
    exclude_columns: list[str] = Field(default_factory=list)
    preserve_headers: bool = True
    chunk_size: int = 10000


class PDFConfig(BaseModel):
    extract_tables: bool = True
    output_formats: OutputFormats = Field(default_factory=OutputFormats)


class CleanerConfig(BaseModel):
    dry_run: bool = False
    create_audit_report: bool = True
    retain_row_count: bool = True
    retain_schema: bool = True
    output_dir: str | None = None
    include_globs: list[str] = Field(default_factory=lambda: ["*.csv", "*.pdf"])
    exclude_globs: list[str] = Field(default_factory=lambda: ["*.clean.*"])
    confidence_threshold: float = 0.5

    entity_types: dict[str, EntityConfig] = Field(default_factory=dict)
    financial_rules: FinancialRules = Field(default_factory=FinancialRules)

    identities: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)
    whitelist: list[str] = Field(default_factory=list)
    custom_patterns: list[CustomPattern] = Field(default_factory=list)

    csv: CSVConfig = Field(default_factory=CSVConfig)
    pdf: PDFConfig = Field(default_factory=PDFConfig)


DEFAULT_CONFIG = CleanerConfig()


_DEFAULT_CONFIG_NAMES = ["config.yaml", "config.yml", ".pii-cleaner.yaml", ".pii-cleaner.yml"]


def load_config(config_path: Path | None) -> CleanerConfig:
    """Load configuration from a YAML file.

    If no path is given, searches for a config file in the current working
    directory using conventional names before falling back to defaults.
    """
    if config_path is None:
        for name in _DEFAULT_CONFIG_NAMES:
            candidate = Path.cwd() / name
            if candidate.exists():
                logger.debug(f"Auto-discovered config: {candidate}")
                config_path = candidate
                break
        else:
            logger.debug("No config file found, using defaults.")
            return CleanerConfig()

    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    try:
        return CleanerConfig(**raw)
    except Exception as e:
        raise ValueError(f"Invalid config file: {e}") from e


def validate_config(config_path: Path) -> tuple[bool, list[str]]:
    """Validate a config file and return (is_valid, list_of_errors)."""
    errors = []
    try:
        config = load_config(config_path)
        for pattern in config.custom_patterns:
            try:
                re.compile(pattern.regex)
            except re.error as e:
                errors.append(f"Invalid regex in pattern '{pattern.name}': {e}")

        if config.financial_rules.account_number.preserve_last_n < 1:
            errors.append("financial_rules.account_number.preserve_last_n must be >= 1")
        if config.financial_rules.card_number.preserve_last_n < 1:
            errors.append("financial_rules.card_number.preserve_last_n must be >= 1")

        return len(errors) == 0, errors
    except Exception as e:
        return False, [str(e)]
