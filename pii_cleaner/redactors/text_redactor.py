"""Main text redactor using Presidio + financial masking + custom patterns."""

from __future__ import annotations

import re
import logging
from typing import Any

from presidio_analyzer import AnalyzerEngine, RecognizerRegistry
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from pii_cleaner.config import CleanerConfig, CustomPattern
from pii_cleaner.detectors.financial import apply_financial_masking
from pii_cleaner.detectors.custom import build_identity_recognizer, build_custom_pattern_recognizer
from pii_cleaner.redactors.financial_redactor import FinancialRedactor
from pii_cleaner.redactors.base import RedactionResult

logger = logging.getLogger(__name__)

DEFAULT_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "LOCATION",
    "CREDIT_CARD",
    "US_SSN",
    "US_BANK_NUMBER",
    "DATE_TIME",
    "NRP",
    "IP_ADDRESS",
    "URL",
]


class TextRedactor:
    """Orchestrates the full redaction pipeline for text."""

    def __init__(self, config: CleanerConfig):
        self.config = config
        self.financial_redactor = FinancialRedactor(config.financial_rules)
        self._analyzer: AnalyzerEngine | None = None
        self._anonymizer = AnonymizerEngine()
        self._custom_patterns = config.custom_patterns
        self._compiled_patterns: list[tuple[CustomPattern, re.Pattern]] = []
        self._setup_custom_patterns()

    def _get_analyzer(self) -> AnalyzerEngine:
        if self._analyzer is None:
            registry = RecognizerRegistry()
            registry.load_predefined_recognizers()

            identity_rec = build_identity_recognizer(
                self.config.identities,
                self.config.aliases,
            )
            if identity_rec:
                registry.add_recognizer(identity_rec)

            for pattern in self.config.custom_patterns:
                rec = build_custom_pattern_recognizer(pattern.name, pattern.regex)
                registry.add_recognizer(rec)

            self._analyzer = AnalyzerEngine(registry=registry)
        return self._analyzer

    def _setup_custom_patterns(self) -> None:
        for pattern in self._custom_patterns:
            try:
                compiled = re.compile(pattern.regex)
                self._compiled_patterns.append((pattern, compiled))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern.name}': {e}")

    def redact(self, text: str, language: str = "en") -> RedactionResult:
        """Redact PII from text using the full pipeline."""
        all_entities = []

        # Step 1: Financial masking
        fin_result = self.financial_redactor.redact_text(text)
        current_text = fin_result.redacted
        all_entities.extend(fin_result.entities)

        # Step 2: Presidio NER
        try:
            analyzer = self._get_analyzer()
            results = analyzer.analyze(
                text=current_text,
                language=language,
                score_threshold=self.config.confidence_threshold,
            )

            if results:
                operators = {}
                for result in results:
                    entity_type = result.entity_type
                    entity_cfg = self.config.entity_types.get(entity_type)

                    if entity_cfg and not entity_cfg.enabled:
                        continue

                    replacement = f"[{entity_type}]"
                    if entity_cfg:
                        replacement = entity_cfg.replacement.format(entity_type=entity_type)

                    operators[entity_type] = OperatorConfig("replace", {"new_value": replacement})

                    all_entities.append({
                        "entity_type": entity_type,
                        "start": result.start,
                        "end": result.end,
                        "score": result.score,
                        "text": current_text[result.start:result.end],
                    })

                if operators:
                    anonymized = self._anonymizer.anonymize(
                        text=current_text,
                        analyzer_results=results,
                        operators=operators,
                    )
                    current_text = anonymized.text
        except Exception as e:
            logger.warning(f"Presidio analysis failed: {e}")

        # Step 3: Custom pattern replacement
        for pattern_cfg, compiled in self._compiled_patterns:
            # Use default argument (p=pattern_cfg) to capture loop variable in closure
            def replace_fn(m: re.Match, p=pattern_cfg) -> str:
                all_entities.append({
                    "entity_type": p.name.upper(),
                    "start": m.start(),
                    "end": m.end(),
                    "text": m.group(0),
                    "custom": True,
                })
                if p.action == "replace":
                    return p.replacement
                elif p.action == "redact":
                    return "[REDACTED]"
                return m.group(0)

            current_text = compiled.sub(replace_fn, current_text)

        return RedactionResult(
            original=text,
            redacted=current_text,
            entities=all_entities,
            changed=text != current_text,
        )
