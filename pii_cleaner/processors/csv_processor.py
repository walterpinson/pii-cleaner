"""CSV file processor."""

from __future__ import annotations

import csv
import io
import logging
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from pii_cleaner.config import CleanerConfig
from pii_cleaner.redactors.text_redactor import TextRedactor
from pii_cleaner.utils.hashing import hash_file
from pii_cleaner.utils.file_utils import split_csv_sections, AMOUNT_RE


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


    def _parse_section(self, section_text: str) -> pd.DataFrame:
        """Parse a CSV section without ever dropping rows.

        pandas drops rows whose field count exceeds the header's column count
        when on_bad_lines='skip'. Instead we use the csv module directly,
        treating the header's column count as authoritative: rows with too
        many fields are right-trimmed (handles trailing commas), rows with
        too few fields are right-padded with empty strings.
        """
        reader = csv.reader(io.StringIO(section_text))
        rows = list(reader)
        if not rows:
            return pd.DataFrame()
        header = rows[0]
        n_cols = len(header)
        data_rows = []
        for row in rows[1:]:
            if len(row) > n_cols:
                # Trailing commas produce extra empty fields — drop them.
                row = row[:n_cols]
            elif len(row) < n_cols:
                row = row + [""] * (n_cols - len(row))
            data_rows.append(row)
        return pd.DataFrame(data_rows, columns=header)

    def _process_dataframe(
        self, df: pd.DataFrame
    ) -> tuple[pd.DataFrame, int, dict[str, int]]:
        """Apply PII redaction to a dataframe."""
        result_df = df.copy()
        fields_changed = 0
        entities_by_type: dict[str, int] = {}
        sensitive_cols = set(self.config.csv.sensitive_columns)
        mask_cols = {c.lower() for c in self.config.csv.mask_columns}
        exclude_cols = {c.lower() for c in self.config.csv.exclude_columns}
        preserve_last_n = self.config.financial_rules.account_number.preserve_last_n
        mask_char = self.config.financial_rules.account_number.mask_char

        for col in df.columns:
            if col.lower() in exclude_cols:
                continue
            if col.lower() in mask_cols:
                for idx, val in df[col].items():
                    if pd.notna(val) and isinstance(val, str) and val.strip():
                        raw = val.strip()
                        # Mask the raw value as an opaque identifier — works for
                        # alphanumeric account numbers (e.g. "Z32359366") where
                        # digit-only extraction would drop non-numeric characters.
                        n_mask = max(0, len(raw) - preserve_last_n)
                        masked = mask_char * n_mask + raw[-preserve_last_n:]
                        if masked != raw:
                            result_df.at[idx, col] = masked
                            fields_changed += 1
                            entities_by_type["ACCOUNT_NUMBER"] = (
                                entities_by_type.get("ACCOUNT_NUMBER", 0) + 1
                            )
            elif col in sensitive_cols:
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
                        stripped = val.strip()
                        # Skip cells that are formatted financial amounts — Presidio/
                        # spaCy NER can misclassify numbers like "-40.00" as PERSON.
                        # The regex requires a decimal point and caps the integer part
                        # to 9 digits so card/account numbers (15-16 digits, no decimal)
                        # are still analyzed normally.
                        if AMOUNT_RE.match(stripped):
                            continue
                        res = self.redactor.redact(stripped)
                        if res.changed:
                            result_df.at[idx, col] = res.redacted
                            fields_changed += 1
                            for entity in res.entities:
                                et = entity["entity_type"]
                                entities_by_type[et] = entities_by_type.get(et, 0) + 1

        return result_df, fields_changed, entities_by_type

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
            # utf-8-sig strips the BOM that some apps (Excel, Fidelity) prepend
            raw_text = input_path.read_text(encoding="utf-8-sig", errors="replace")
            section_texts = split_csv_sections(raw_text)

            processed_section_csvs: list[str] = []
            for section_text in section_texts:
                try:
                    df = self._parse_section(section_text)
                except Exception as e:
                    # Unparseable section — preserve raw.
                    warnings.append(f"Skipped unparseable section: {e}")
                    processed_section_csvs.append(section_text)
                    continue
                if len(df.columns) == 0:
                    processed_section_csvs.append(section_text)
                    continue
                rows_processed += len(df)
                result_df, sec_fields, sec_entities = self._process_dataframe(df)
                fields_changed += sec_fields
                for k, v in sec_entities.items():
                    entities_by_type[k] = entities_by_type.get(k, 0) + v
                processed_section_csvs.append(result_df.to_csv(index=False).rstrip("\n"))

            output_hash = None
            if not dry_run:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text("\n\n".join(processed_section_csvs) + "\n")
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
