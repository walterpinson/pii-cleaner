"""Custom Presidio recognizers built from config."""

from __future__ import annotations

import re
import logging
from presidio_analyzer import PatternRecognizer, Pattern

logger = logging.getLogger(__name__)


def build_identity_recognizer(identities: list[str], aliases: list[str]) -> PatternRecognizer | None:
    """Build a Presidio recognizer for specific people/org identities."""
    all_terms = identities + aliases
    if not all_terms:
        return None

    escaped = [re.escape(term) for term in all_terms]
    pattern_str = r'\b(' + '|'.join(escaped) + r')\b'

    patterns = [Pattern(name="identity", regex=pattern_str, score=1.0)]
    return PatternRecognizer(
        supported_entity="CONFIGURED_IDENTITY",
        patterns=patterns,
        name="ConfiguredIdentityRecognizer",
    )


def build_custom_pattern_recognizer(
    pattern_name: str,
    regex: str,
    score: float = 0.9,
) -> PatternRecognizer:
    """Build a Presidio recognizer from a custom regex pattern."""
    patterns = [Pattern(name=pattern_name, regex=regex, score=score)]
    return PatternRecognizer(
        supported_entity=pattern_name.upper(),
        patterns=patterns,
        name=f"CustomRecognizer_{pattern_name}",
    )
