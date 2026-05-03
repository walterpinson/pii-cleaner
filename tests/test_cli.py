"""Tests for CLI commands."""
import pytest
from pathlib import Path
from typer.testing import CliRunner
from pii_cleaner.cli import app


runner = CliRunner()


@pytest.fixture
def sample_csv(tmp_path):
    f = tmp_path / "test.csv"
    f.write_text("name,card\nJohn Doe,4111111111111234\n")
    return f


def test_redact_file_dry_run(sample_csv, tmp_path):
    output = tmp_path / "output.csv"
    result = runner.invoke(app, [
        "redact", "file",
        str(sample_csv),
        "--output", str(output),
    ])
    assert result.exit_code == 0
    assert not output.exists()


def test_redact_file_apply(sample_csv, tmp_path):
    output = tmp_path / "output.csv"
    result = runner.invoke(app, [
        "redact", "file",
        str(sample_csv),
        "--output", str(output),
        "--apply",
    ])
    assert result.exit_code == 0
    assert output.exists()


def test_redact_file_nonexistent():
    result = runner.invoke(app, ["redact", "file", "/nonexistent/file.csv"])
    assert result.exit_code != 0


def test_validate_config_valid(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("dry_run: false\n")
    result = runner.invoke(app, ["validate-config", str(config_file)])
    assert result.exit_code == 0


def test_validate_config_invalid(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "custom_patterns:\n"
        "  - name: bad\n"
        "    regex: '[invalid('\n"
        "    action: replace\n"
        "    replacement: X\n"
    )
    result = runner.invoke(app, ["validate-config", str(config_file)])
    assert result.exit_code != 0


def test_redact_folder_dry_run(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "a.csv").write_text("name\nJohn\n")
    (input_dir / "b.csv").write_text("name\nJane\n")
    output_dir = tmp_path / "output"

    result = runner.invoke(app, [
        "redact", "folder",
        str(input_dir),
        "--output", str(output_dir),
    ])
    assert result.exit_code == 0
    assert not output_dir.exists()


def test_redact_folder_apply(tmp_path):
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    (input_dir / "a.csv").write_text("name\nJohn\n")
    output_dir = tmp_path / "output"

    result = runner.invoke(app, [
        "redact", "folder",
        str(input_dir),
        "--output", str(output_dir),
        "--apply",
    ])
    assert result.exit_code == 0
    assert (output_dir / "a.clean.csv").exists()


def test_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "pii-cleaner" in result.output.lower() or "version" in result.output.lower()
