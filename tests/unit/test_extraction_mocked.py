"""Тесты extraction-адаптера с моками (без Ollama и docket)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from supplier_bonus.extraction.docket_adapter import (
    CITED_FIELDS,
    SCHEMA_ID,
    build_field_rules,
    build_process_options,
    build_schema_spec,
    extract_terms,
    to_field_sources,
)
from supplier_bonus.schemas import (
    BaseMetric,
    BonusTerms,
    BonusType,
    FieldSource,
    Tier,
)


def _sample_terms() -> BonusTerms:
    return BonusTerms(
        supplier_name="ООО «Пример»",
        bonus_type=BonusType.MONETARY,
        base_metric=BaseMetric.PURCHASE_VOLUME,
        tiers=[Tier(threshold=1_000_000, rate=0.02)],
        period="2026-Q1",
    )


def test_schema_spec_built() -> None:
    spec = build_schema_spec()
    assert spec.schema_id == SCHEMA_ID
    assert spec.model is BonusTerms
    assert spec.cited_fields == CITED_FIELDS
    assert "supplier_name" in spec.cited_fields


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


def test_extract_terms_uses_process_document() -> None:
    """process_document замокан, extract_terms возвращает BonusTerms."""
    fake_result = MagicMock()
    fake_result.document = _sample_terms()
    fake_result.extracted = None
    fake_result.field_sources = {}

    with patch(
        "supplier_bonus.extraction.docket_adapter.process_document",
        return_value=fake_result,
    ):
        terms = extract_terms("dummy.pdf")

    assert len(terms) == 1
    assert isinstance(terms[0], BonusTerms)
    assert terms[0].supplier_name == "ООО «Пример»"


def test_extract_terms_fallback_to_extracted_dict() -> None:
    """Если result.document == None, используется result.extracted."""
    fake_result = MagicMock()
    fake_result.document = None
    fake_result.extracted = {
        "supplier_name": "ООО «Ромашка»",
        "bonus_type": "monetary",
        "base_metric": "purchase_volume",
        "tiers": [{"threshold": 1_000_000, "rate": 0.02}],
        "period": "2026-Q1",
    }
    fake_result.field_sources = {}

    with patch(
        "supplier_bonus.extraction.docket_adapter.process_document",
        return_value=fake_result,
    ):
        terms = extract_terms("dummy.pdf")

    assert len(terms) == 1
    assert terms[0].supplier_name == "ООО «Ромашка»"


def test_extract_terms_handles_invalid_document() -> None:
    """Невалидный dict пропускается, возвращается пустой список."""
    fake_result = MagicMock()
    fake_result.document = None
    fake_result.extracted = {"period": "неверный-формат"}
    fake_result.field_sources = {}

    with patch(
        "supplier_bonus.extraction.docket_adapter.process_document",
        return_value=fake_result,
    ):
        terms = extract_terms("dummy.pdf")

    assert terms == []


def test_to_field_sources_maps_locations() -> None:
    loc = MagicMock()
    loc.page = 3
    loc.quote = "при объеме от 1 000 000 руб. — 2%"
    loc.status = "verified"
    loc.confidence = 0.95
    loc.located_by = "tesseract"

    fake_result = MagicMock()
    fake_result.field_sources = {"tiers": loc}

    sources = to_field_sources(fake_result)
    assert "tiers" in sources
    assert isinstance(sources["tiers"], FieldSource)
    assert sources["tiers"].page == 3
    assert sources["tiers"].status == "verified"
    assert sources["tiers"].confidence == 0.95


def test_to_field_sources_empty() -> None:
    fake_result = MagicMock()
    fake_result.field_sources = {}
    assert to_field_sources(fake_result) == {}
