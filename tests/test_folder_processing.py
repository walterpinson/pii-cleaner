"""Tests for folder processing."""
import pytest
from pathlib import Path
from pii_cleaner.utils.file_utils import collect_files, is_supported, make_output_path


def test_collect_files_finds_csv_and_pdf(tmp_path):
    (tmp_path / "a.csv").write_text("name\nJohn")
    (tmp_path / "b.pdf").write_bytes(b"%PDF")
    (tmp_path / "c.txt").write_text("text")

    supported, skipped = collect_files(tmp_path)
    supported_names = [f.name for f in supported]

    assert "a.csv" in supported_names
    assert "b.pdf" in supported_names
    assert len(skipped) > 0


def test_collect_files_recursive(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.csv").write_text("name\nJane")
    (tmp_path / "top.csv").write_text("name\nJohn")

    supported_flat, _ = collect_files(tmp_path, recursive=False)
    supported_rec, _ = collect_files(tmp_path, recursive=True)

    assert len(supported_rec) > len(supported_flat)
    names_rec = [f.name for f in supported_rec]
    assert "nested.csv" in names_rec


def test_unsupported_files_skipped(tmp_path):
    (tmp_path / "notes.txt").write_text("some text")
    (tmp_path / "data.xlsx").write_bytes(b"fake excel")
    (tmp_path / "good.csv").write_text("name\nJohn")

    supported, skipped = collect_files(tmp_path)
    skipped_names = [f.name for f in skipped]

    assert "notes.txt" in skipped_names
    assert "data.xlsx" in skipped_names
    assert "good.csv" not in skipped_names


def test_is_supported():
    assert is_supported(Path("file.csv")) is True
    assert is_supported(Path("file.PDF")) is True
    assert is_supported(Path("file.txt")) is False
    assert is_supported(Path("file.xlsx")) is False


def test_make_output_path():
    input_path = Path("/data/input/subdir/file.csv")
    input_base = Path("/data/input")
    output_base = Path("/data/output")

    result = make_output_path(input_path, input_base, output_base)
    assert result == Path("/data/output/subdir/file.csv")


def test_exclude_globs(tmp_path):
    (tmp_path / "keep.csv").write_text("name\nJohn")
    (tmp_path / "ignore.csv").write_text("name\nJane")

    supported, skipped = collect_files(tmp_path, exclude_globs=["ignore.csv"])
    supported_names = [f.name for f in supported]

    assert "keep.csv" in supported_names
    assert "ignore.csv" not in supported_names
