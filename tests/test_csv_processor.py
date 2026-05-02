"""Tests for CSV processing."""
import pytest
from pathlib import Path
import pandas as pd
from pii_cleaner.config import load_config
from pii_cleaner.redactors.text_redactor import TextRedactor
from pii_cleaner.processors.csv_processor import CSVProcessor


@pytest.fixture
def sample_csv(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text(
        "name,account_number,card_number,email,amount\n"
        "John Doe,1234567890,4111111111111234,john@example.com,100.00\n"
        "Jane Smith,9876543210,5555555555554444,jane@example.com,200.00\n"
    )
    return csv_file


@pytest.fixture
def config():
    return load_config(None)


@pytest.fixture
def processor(config):
    redactor = TextRedactor(config)
    return CSVProcessor(config, redactor)


def test_csv_processing_masks_card_numbers(sample_csv, processor, tmp_path):
    output = tmp_path / "output.csv"
    result = processor.process(sample_csv, output, dry_run=False)
    assert result.success
    df = pd.read_csv(output, dtype=str)
    for card in df["card_number"]:
        assert "4111111111111234" not in str(card)
        assert "5555555555554444" not in str(card)


def test_csv_processing_masks_account_numbers(sample_csv, processor, tmp_path):
    output = tmp_path / "output.csv"
    result = processor.process(sample_csv, output, dry_run=False)
    df = pd.read_csv(output, dtype=str)
    for acct in df["account_number"]:
        # Account number must be masked: either starts with X (masked) or original digits are gone
        acct_str = str(acct)
        assert acct_str.startswith("X") or "1234567890" not in acct_str


def test_csv_preserves_row_count(sample_csv, processor, tmp_path):
    output = tmp_path / "output.csv"
    result = processor.process(sample_csv, output, dry_run=False)
    original_df = pd.read_csv(sample_csv)
    result_df = pd.read_csv(output)
    assert len(original_df) == len(result_df)


def test_csv_preserves_headers(sample_csv, processor, tmp_path):
    output = tmp_path / "output.csv"
    result = processor.process(sample_csv, output, dry_run=False)
    original_df = pd.read_csv(sample_csv)
    result_df = pd.read_csv(output)
    assert list(original_df.columns) == list(result_df.columns)


def test_dry_run_does_not_write(sample_csv, processor, tmp_path):
    output = tmp_path / "output.csv"
    result = processor.process(sample_csv, output, dry_run=True)
    assert result.output_path is None
    assert not output.exists()


def test_full_column_redaction(tmp_path):
    csv_file = tmp_path / "test.csv"
    csv_file.write_text("name,ssn\nJohn,123-45-6789\nJane,987-65-4321\n")

    config_file = tmp_path / "config.yaml"
    config_file.write_text("csv:\n  sensitive_columns:\n    - ssn\n")
    cfg = load_config(config_file)

    redactor = TextRedactor(cfg)
    proc = CSVProcessor(cfg, redactor)
    output = tmp_path / "output.csv"
    result = proc.process(csv_file, output, dry_run=False)

    df = pd.read_csv(output, dtype=str)
    for val in df["ssn"]:
        assert val == "[REDACTED]"


def test_mixed_column_redacts_only_pii(processor, tmp_path):
    """Mixed-content columns should only redact PII substrings, not whole value."""
    csv_file = tmp_path / "mixed.csv"
    csv_file.write_text("description\nPayment to 4111111111111234 on Jan 15\nCoffee shop purchase\n")
    output = tmp_path / "output.csv"
    result = processor.process(csv_file, output, dry_run=False)
    df = pd.read_csv(output, dtype=str)
    assert "4111111111111234" not in df["description"].iloc[0]
    assert "Coffee shop purchase" == df["description"].iloc[1]
