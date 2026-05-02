"""Tests for PDF processing."""
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from pii_cleaner.config import load_config
from pii_cleaner.redactors.text_redactor import TextRedactor
from pii_cleaner.processors.pdf_processor import PDFProcessor


@pytest.fixture
def config():
    return load_config(None)


@pytest.fixture
def processor(config):
    redactor = TextRedactor(config)
    return PDFProcessor(config, redactor)


def test_pdf_processor_produces_outputs(tmp_path, processor):
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    mock_page = MagicMock()
    mock_page.page_number = 1
    mock_page.extract_text.return_value = (
        "Account: 1234567890123456\n"
        "Card: 4111 1111 1111 9876\n"
        "John Doe, email: john@example.com"
    )
    mock_page.extract_tables.return_value = []

    mock_pdf = MagicMock()
    mock_pdf.__enter__ = lambda s: s
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = [mock_page]

    with patch("pdfplumber.open", return_value=mock_pdf):
        result = processor.process(pdf_path, tmp_path / "out", dry_run=False)

    assert result.success
    assert result.pages_processed == 1

    out_dir = tmp_path / "out"
    assert (out_dir / "test.txt").exists()
    assert (out_dir / "test.md").exists()
    assert (out_dir / "test_redaction_map.json").exists()


def test_pdf_dry_run_no_outputs(tmp_path, processor):
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    mock_page = MagicMock()
    mock_page.page_number = 1
    mock_page.extract_text.return_value = "Hello World 4111111111111234"
    mock_page.extract_tables.return_value = []

    mock_pdf = MagicMock()
    mock_pdf.__enter__ = lambda s: s
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = [mock_page]

    out_dir = tmp_path / "out"
    with patch("pdfplumber.open", return_value=mock_pdf):
        result = processor.process(pdf_path, out_dir, dry_run=True)

    assert result.output_paths == []
    assert not out_dir.exists()


def test_pdf_redacts_card_numbers(tmp_path, processor):
    pdf_path = tmp_path / "test.pdf"
    pdf_path.write_bytes(b"%PDF-1.4 fake")

    mock_page = MagicMock()
    mock_page.page_number = 1
    mock_page.extract_text.return_value = "Card: 4111 1111 1111 9876"
    mock_page.extract_tables.return_value = []

    mock_pdf = MagicMock()
    mock_pdf.__enter__ = lambda s: s
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = [mock_page]

    out_dir = tmp_path / "out"
    with patch("pdfplumber.open", return_value=mock_pdf):
        result = processor.process(pdf_path, out_dir, dry_run=False)

    txt_content = (out_dir / "test.txt").read_text()
    assert "4111 1111 1111 9876" not in txt_content
    assert "9876" in txt_content
