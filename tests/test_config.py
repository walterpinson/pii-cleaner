"""Tests for configuration loading and validation."""
import pytest
from pathlib import Path
from pii_cleaner.config import load_config, validate_config, CleanerConfig


def test_default_config():
    cfg = load_config(None)
    assert isinstance(cfg, CleanerConfig)
    assert cfg.dry_run is False
    assert cfg.confidence_threshold == 0.5


def test_load_config_from_file(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
dry_run: true
confidence_threshold: 0.7
identities:
  - "John Doe"
custom_patterns:
  - name: "test_pattern"
    regex: "\\\\bTEST-[0-9]+\\\\b"
    action: "replace"
    replacement: "[TEST]"
""")
    cfg = load_config(config_file)
    assert cfg.dry_run is True
    assert cfg.confidence_threshold == 0.7
    assert "John Doe" in cfg.identities
    assert cfg.custom_patterns[0].name == "test_pattern"


def test_validate_config_valid(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
identities:
  - "Test Person"
financial_rules:
  account_number:
    preserve_last_n: 4
    mask_char: "X"
""")
    is_valid, errors = validate_config(config_file)
    assert is_valid is True
    assert errors == []


def test_validate_config_invalid_regex(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
custom_patterns:
  - name: "bad_pattern"
    regex: "[invalid("
    action: "replace"
    replacement: "[REDACTED]"
""")
    is_valid, errors = validate_config(config_file)
    assert is_valid is False
    assert len(errors) > 0


def test_config_not_found():
    with pytest.raises(FileNotFoundError):
        load_config(Path("/nonexistent/config.yaml"))
