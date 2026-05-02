"""CSV file processor."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from pii_cleaner.config import CleanerConfig
from pii_cleaner.redactors.text_redactor import TextRedactor
from pii_cleaner.utils.hashing import hash_file

logger = logging.getLogger(__name__)


@dataclass
class CSVProcessResult:
    input_path: Path
    output_path: Path | None
    rows_processed: int
    fields_changed: int
    entities_by_type: dict[str, int]
    warnings: list[str]
    success: bool
    error: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None


class CSVProcessor:
    """Process CSV files to redact PII."""

    def __init__(self, config: CleanerConfig, redactor: TextRedactor):
        self.config = config
        self.redactor = redactor

    def process(
        self,
        input_path: Path,
        output_path: Path,
        dry_run: bool = False,
    ) -> CSVProcessResult:
        """Process a CSV file and write the redacted output."""
        warnings = []
        entities_by_type: dict[str, int] = {}
        fields_changed = 0
        rows_processed = 0

        try:
            input_hash = hash_file(input_path)
            df = pd.read_csv(input_path, dtype=str)
            rows_processed = len(df)
            result_df = df.copy()

            sensitive_cols = set(self.config.csv.sensitive_columns)

            for col in df.columns:
                if col in sensitive_cols:
                    for idx, val in df[col].items():
                        if pd.notna(val):
                            result_df.at[idx, col] = "[REDACTED]"
                            fields_changed += 1
                            entities_by_type["FULL_COLUMN_REDACTION"] = (
                                entities_by_type.get("FULL_COLUMN_REDACTION", 0) + 1
                            )
                else:
                    for idx, val in df[col].items():
                        if pd.notna(val) and isinstance(val, str):
                            res = self.redactor.redact(str(val))
                            if res.changed:
                                result_df.at[idx, col] = res.redacted
                                fields_changed += 1
                                for entity in res.entities:
                                    et = entity["entity_type"]
                                    entities_by_type[et] = entities_by_type.get(et, 0) + 1

            output_hash = None
            if not dry_run:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                result_df.to_csv(output_path, index=False)
                output_hash = hash_file(output_path)

            return CSVProcessResult(
                input_path=input_path,
                output_path=output_path if not dry_run else None,
                rows_processed=rows_processed,
                fields_changed=fields_changed,
                entities_by_type=entities_by_type,
                warnings=warnings,
                success=True,
                input_hash=input_hash,
                output_hash=output_hash,
            )

        except Exception as e:
            logger.error(f"Failed to process CSV {input_path}: {e}")
            return CSVProcessResult(
                input_path=input_path,
                output_path=None,
                rows_processed=rows_processed,
                fields_changed=fields_changed,
                entities_by_type=entities_by_type,
                warnings=warnings,
                success=False,
                error=str(e),
            )
