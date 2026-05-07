"""PDF file processor using pdfplumber for extraction."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import pdfplumber

from pii_cleaner.config import CleanerConfig
from pii_cleaner.redactors.text_redactor import TextRedactor
from pii_cleaner.utils.hashing import hash_file

logger = logging.getLogger(__name__)


@dataclass
class PageResult:
    page_number: int
    original_text: str
    redacted_text: str
    entities: list[dict] = field(default_factory=list)


@dataclass
class PDFProcessResult:
    input_path: Path
    output_paths: list[Path]
    pages_processed: int
    entities_by_type: dict[str, int]
    warnings: list[str]
    success: bool
    error: str | None = None
    input_hash: str | None = None
    redaction_map: list[dict] = field(default_factory=list)


class PDFProcessor:
    """Process PDF files to redact PII."""

    def __init__(self, config: CleanerConfig, redactor: TextRedactor):
        self.config = config
        self.redactor = redactor

    def process(
        self,
        input_path: Path,
        output_dir: Path,
        dry_run: bool = False,
    ) -> PDFProcessResult:
        """Process a PDF file and write sanitized outputs."""
        warnings = []
        entities_by_type: dict[str, int] = {}
        page_results: list[PageResult] = []
        output_paths: list[Path] = []

        try:
            input_hash = hash_file(input_path)
            stem = input_path.stem

            with pdfplumber.open(input_path) as pdf:
                for page in pdf.pages:
                    page_num = page.page_number

                    text = page.extract_text() or ""

                    tables = page.extract_tables() or []
                    for table in tables:
                        for row in table:
                            if row:
                                text += "\n" + "\t".join(
                                    str(cell) if cell is not None else "" for cell in row
                                )

                    # Strip CID font-encoding artifacts produced by pdfplumber
                    # when it cannot decode embedded font glyphs (e.g. (cid:0)).
                    # Applied after all content — including tables — is assembled.
                    text = re.sub(r'\(cid:\d+\)', '', text)

                    if self.config.pdf.sensitive_labels:
                        text = self._redact_labeled_values(text, self.config.pdf.sensitive_labels)

                    result = self.redactor.redact(text)

                    for entity in result.entities:
                        et = entity["entity_type"]
                        entities_by_type[et] = entities_by_type.get(et, 0) + 1

                    page_results.append(PageResult(
                        page_number=page_num,
                        original_text=text,
                        redacted_text=result.redacted,
                        entities=result.entities,
                    ))

            if not dry_run:
                output_dir.mkdir(parents=True, exist_ok=True)
                fmt = self.config.pdf.output_formats

                if fmt.txt:
                    txt_path = output_dir / f"{stem}.txt"
                    self._write_txt(txt_path, page_results)
                    output_paths.append(txt_path)

                if fmt.md:
                    md_path = output_dir / f"{stem}.md"
                    self._write_md(md_path, page_results, input_path)
                    output_paths.append(md_path)

                if fmt.json_report:
                    json_path = output_dir / f"{stem}_redaction_map.json"
                    self._write_json(json_path, page_results, input_path)
                    output_paths.append(json_path)

            return PDFProcessResult(
                input_path=input_path,
                output_paths=output_paths,
                pages_processed=len(page_results),
                entities_by_type=entities_by_type,
                warnings=warnings,
                success=True,
                input_hash=input_hash,
                redaction_map=[
                    {"page": pr.page_number, "entities": pr.entities}
                    for pr in page_results
                ],
            )

        except Exception as e:
            logger.error(f"Failed to process PDF {input_path}: {e}")
            return PDFProcessResult(
                input_path=input_path,
                output_paths=[],
                pages_processed=0,
                entities_by_type=entities_by_type,
                warnings=warnings,
                success=False,
                error=str(e),
            )

    def _redact_labeled_values(self, text: str, labels: list[str]) -> str:
        """Redact values that follow any of the given field labels on the same line.

        Matches patterns like:
            Employee ID: 00123456
            Employee ID  00123456
            Employee ID - 00123456

        The label is kept; everything after the separator is replaced with [REDACTED].
        Matching is case-insensitive.
        """
        for label in labels:
            pattern = re.compile(
                r'(?i)(\b' + re.escape(label) + r'\b\s*[:\-]?\s*)(.+)',
                re.MULTILINE,
            )
            text = pattern.sub(lambda m: m.group(1) + "[REDACTED]", text)
        return text

    def _write_txt(self, path: Path, pages: list[PageResult]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for pr in pages:
                f.write(f"=== Page {pr.page_number} ===\n")
                f.write(pr.redacted_text)
                f.write("\n\n")

    def _write_md(self, path: Path, pages: list[PageResult], source: Path) -> None:
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Sanitized: {source.name}\n\n")
            f.write(
                "> **Note:** This document has been processed by pii-cleaner. "
                "All detected PII has been redacted.\n\n"
            )
            for pr in pages:
                f.write(f"## Page {pr.page_number}\n\n")
                f.write(pr.redacted_text)
                f.write("\n\n")

    def _write_json(self, path: Path, pages: list[PageResult], source: Path) -> None:
        report = {
            "source": str(source),
            "pages": [
                {
                    "page_number": pr.page_number,
                    "entities_detected": pr.entities,
                    "redacted_text_preview": pr.redacted_text[:200],
                }
                for pr in pages
            ],
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, default=str)
