"""Financial redactor that applies deterministic masking."""

from __future__ import annotations

import logging

from pii_cleaner.detectors.financial import apply_financial_masking
from pii_cleaner.config import FinancialRules
from pii_cleaner.redactors.base import RedactionResult

logger = logging.getLogger(__name__)


class FinancialRedactor:
    """Applies deterministic masking for financial identifiers."""

    def __init__(self, rules: FinancialRules):
        self.rules = rules

    def redact_text(self, text: str) -> RedactionResult:
        """Redact financial identifiers from text."""
        masked, entities = apply_financial_masking(
            text,
            preserve_last_n_card=self.rules.card_number.preserve_last_n,
            preserve_last_n_account=self.rules.account_number.preserve_last_n,
            mask_char=self.rules.card_number.mask_char,
        )
        return RedactionResult(original=text, redacted=masked, entities=entities)
