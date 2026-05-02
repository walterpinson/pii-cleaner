"""Financial identifier detection and masking."""

from __future__ import annotations

import re
import logging

logger = logging.getLogger(__name__)

CARD_NUMBER_PATTERN = re.compile(
    r'\b'
    r'(\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}'
    r'|\d{4}[-\s]?\d{6}[-\s]?\d{5}'
    r')'
    r'\b'
)

# Matches US bank account numbers which typically range from 8-17 digits
ACCOUNT_NUMBER_PATTERN = re.compile(
    r'\b(\d{8,17})\b'
)

ALREADY_MASKED_PATTERN = re.compile(
    r'\b[X#*]{4}[-\s]?[X#*]{4}[-\s]?[X#*]{4}[-\s]?\d{4}\b',
    re.IGNORECASE
)

ROUTING_NUMBER_PATTERN = re.compile(
    r'\b(\d{9})\b'
)


def _mask_number_preserve_last_n(
    number_str: str,
    preserve_last_n: int,
    mask_char: str,
    separators: str = "",
) -> str:
    digits = re.sub(r'[^0-9]', '', number_str)
    if len(digits) <= preserve_last_n:
        return number_str

    n_to_mask = len(digits) - preserve_last_n
    masked_digits = mask_char * n_to_mask + digits[-preserve_last_n:]

    if not re.search(r'[-\s]', number_str):
        return masked_digits

    result = []
    digit_idx = 0
    for char in number_str:
        if char.isdigit():
            result.append(masked_digits[digit_idx])
            digit_idx += 1
        else:
            result.append(char)
    return ''.join(result)


def mask_card_number(
    card_str: str,
    preserve_last_n: int = 4,
    mask_char: str = "X",
) -> str:
    """Mask a card number, preserving only the last preserve_last_n digits."""
    if ALREADY_MASKED_PATTERN.match(card_str.strip()):
        return card_str
    return _mask_number_preserve_last_n(card_str, preserve_last_n, mask_char)


def mask_account_number(
    acct_str: str,
    preserve_last_n: int = 4,
    mask_char: str = "X",
) -> str:
    """Mask an account number, preserving only the last preserve_last_n digits."""
    return _mask_number_preserve_last_n(acct_str, preserve_last_n, mask_char)


def apply_financial_masking(
    text: str,
    preserve_last_n_card: int = 4,
    preserve_last_n_account: int = 4,
    mask_char: str = "X",
) -> tuple[str, list[dict]]:
    """Apply deterministic financial masking to a text string."""
    substitutions = []
    result = text

    def replace_card(m: re.Match) -> str:
        original = m.group(0)
        if ALREADY_MASKED_PATTERN.match(original.strip()):
            return original
        masked = mask_card_number(original, preserve_last_n_card, mask_char)
        if masked != original:
            substitutions.append({
                "original": original,
                "masked": masked,
                "entity_type": "CARD_NUMBER",
                "start": m.start(),
                "end": m.end(),
            })
        return masked

    result = CARD_NUMBER_PATTERN.sub(replace_card, result)

    def replace_account(m: re.Match) -> str:
        original = m.group(0)
        if any(c == mask_char for c in original):
            return original
        digits = re.sub(r'[^0-9]', '', original)
        if len(digits) == 9:
            return original
        masked = mask_account_number(original, preserve_last_n_account, mask_char)
        if masked != original:
            substitutions.append({
                "original": original,
                "masked": masked,
                "entity_type": "ACCOUNT_NUMBER",
                "start": m.start(),
                "end": m.end(),
            })
        return masked

    result = ACCOUNT_NUMBER_PATTERN.sub(replace_account, result)

    return result, substitutions
