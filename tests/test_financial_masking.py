"""Tests for financial number masking."""
import pytest
from pii_cleaner.detectors.financial import (
    mask_card_number,
    mask_account_number,
    apply_financial_masking,
)


class TestCardNumberMasking:
    def test_16_digit_no_separator(self):
        assert mask_card_number("1234567890123456") == "XXXXXXXXXXXX3456"

    def test_16_digit_space_separated(self):
        assert mask_card_number("4111 1111 1111 1234") == "XXXX XXXX XXXX 1234"

    def test_16_digit_dash_separated(self):
        assert mask_card_number("1234-5678-9012-3456") == "XXXX-XXXX-XXXX-3456"

    def test_preserve_last_4_only(self):
        result = mask_card_number("4111111111111234")
        assert result.endswith("1234")
        assert len(result) == 16

    def test_already_masked_unchanged(self):
        already = "XXXX XXXX XXXX 1234"
        assert mask_card_number(already) == already

    def test_already_masked_hash_unchanged(self):
        already = "#### #### #### 9876"
        assert mask_card_number(already) == already

    def test_custom_mask_char(self):
        assert mask_card_number("4111111111111234", mask_char="#") == "############1234"

    def test_custom_preserve_n(self):
        result = mask_card_number("4111111111111234", preserve_last_n=6)
        assert result.endswith("111234")


class TestAccountNumberMasking:
    def test_12_digit(self):
        assert mask_account_number("000123456789") == "XXXXXXXX6789"

    def test_16_digit(self):
        assert mask_account_number("1234567890123456") == "XXXXXXXXXXXX3456"

    def test_preserve_last_4(self):
        result = mask_account_number("123456789012")
        assert result.endswith("9012")

    def test_custom_mask_char(self):
        result = mask_account_number("000123456789", mask_char="#")
        assert result == "########6789"

    def test_short_number_not_masked(self):
        result = mask_account_number("1234")
        assert result == "1234"


class TestApplyFinancialMasking:
    def test_card_in_text(self):
        text = "Card: 4111111111111234 was charged."
        result, subs = apply_financial_masking(text)
        assert "XXXXXXXXXXXX1234" in result
        assert len(subs) > 0

    def test_already_masked_card_unchanged(self):
        text = "Card ending XXXX XXXX XXXX 1234 was charged."
        result, subs = apply_financial_masking(text)
        assert "XXXX XXXX XXXX 1234" in result

    def test_account_in_text(self):
        text = "Account 000123456789 has a balance."
        result, subs = apply_financial_masking(text)
        assert "XXXXXXXX6789" in result

    def test_returns_substitutions_list(self):
        text = "Card 4111111111111234 and account 123456789012."
        result, subs = apply_financial_masking(text)
        assert isinstance(subs, list)
        assert len(subs) >= 1
