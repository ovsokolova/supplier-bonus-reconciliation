"""Тесты адаптера docket (без реального OCR/LLM)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from supplier_bonus.extraction.docket_adapter import (
    CITED_FIELDS,
    SCHEMA_ID,
    build_field_rules,
    build_process_options,
    build_schema_spec,
)
from supplier_bonus.schemas import (
    BaseMetric,
    BonusTerms,
    BonusType,
    Tier,
)


def test_schema_spec_built() -> None:
    spec = build_schema_spec()
    assert spec.schema_id == SCHEMA_ID
    assert spec.model is BonusTerms
    assert spec.cited_fields == CITED_FIELDS
    assert "supplier_name" in spec.cited_fields
    assert "inn" in spec.cited_fields


def test_process_options_construct() -> None:
    opts = build_process_options()
    assert opts.schema_model is BonusTerms
    assert opts.classify is False
    assert opts.include_layout is False
    assert opts.review.enqueue is True
    assert opts.ocr.backend == "tesseract"
    assert opts.ocr.fallbacks == ["paddleocr"]


def test_field_rules_have_required_fields() -> None:
    rules = build_field_rules()
    fields = {r.field for r in rules}
    assert "supplier_name" in fields
    assert "inn.value" in fields
    assert "period" in fields


def test_bonus_terms_has_field_locations() -> None:
    terms = BonusTerms(
        supplier_name="ООО «Пример»",
        bonus_type=BonusType.MONETARY,
        base_metric=BaseMetric.PURCHASE_VOLUME,
        tiers=[Tier(threshold=1_000_000, rate=0.02)],
        period="2026-Q1",
    )
    assert hasattr(terms, "field_locations")
    assert terms.field_locations == {}


def test_bonus_terms_rejects_unsorted_tiers() -> None:
    with pytest.raises(ValidationError):
        BonusTerms(
            supplier_name="X",
            bonus_type=BonusType.MONETARY,
            base_metric=BaseMetric.PURCHASE_VOLUME,
            tiers=[
                Tier(threshold=5_000_000, rate=0.035),
                Tier(threshold=1_000_000, rate=0.02),
            ],
            period="2026-Q1",
        )
