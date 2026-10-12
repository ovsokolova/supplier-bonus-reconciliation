"""Адаптер между docket.process_document и доменной моделью BonusTerms."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from docket import (
    DocumentResult,
    FieldRule,
    LLMBackend,
    OcrOptions,
    OllamaBackend,
    OpenAICompatibleBackend,
    ProcessOptions,
    ReviewOptions,
    SchemaSpec,
    process_document,
    register_schema,
)
from pydantic import ValidationError

from supplier_bonus.config import Settings, get_settings
from supplier_bonus.schemas import BonusTerms, FieldSource

logger = logging.getLogger(__name__)

SCHEMA_ID = "supplier_bonus_terms"
SCHEMA_VERSION = "1.0"

CITED_FIELDS: tuple[str, ...] = (
    "supplier_name",
    "inn",
    "bonus_type",
    "base_metric",
    "tiers",
    "period",
)


def build_schema_spec() -> SchemaSpec:
    """Собирает SchemaSpec для бонусных условий."""
    return SchemaSpec(
        schema_id=SCHEMA_ID,
        model=BonusTerms,
        description=(
            "Бонусные условия поставщика: наименование, ИНН, тип бонуса, "
            "база расчёта, ступени, период, валюта, признак НДС."
        ),
        version=SCHEMA_VERSION,
        display_name="Supplier Bonus Terms",
        status="experimental",
        cited_fields=CITED_FIELDS,
    )


def register_bonus_schema(*, replace_existing: bool = False) -> SchemaSpec:
    """Регистрирует схему. Идемпотентно при replace_existing=False."""
    spec = build_schema_spec()
    try:
        register_schema(spec, replace_existing=replace_existing)
        logger.info("Schema %s зарегистрирована", SCHEMA_ID)
    except ValueError as exc:
        logger.warning("Schema %s уже зарегистрирована: %s", SCHEMA_ID, exc)
    return spec


def _build_llm(settings: Settings) -> LLMBackend | None:
    """Создаёт LLM-бэкенд по настройкам."""
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        return OllamaBackend(
            host=settings.ollama_base_url,
            text_model=settings.llm_model,
            vision_model=settings.llm_vision_model,
        )
    if provider in {"openai", "openai-compatible"}:
        return OpenAICompatibleBackend(
            base_url=settings.openai_base_url,
            api_key=settings.openai_api_key,
            text_model=settings.llm_model,
            vision_model=settings.llm_vision_model,
        )
    logger.warning("Неизвестный LLM_PROVIDER=%s, используется Ollama", provider)
    return OllamaBackend(
        host=settings.ollama_base_url,
        text_model=settings.llm_model,
        vision_model=settings.llm_vision_model,
    )


def build_process_options(settings: Settings | None = None) -> ProcessOptions:
    """Собирает ProcessOptions из конфигурации."""
    s = settings or get_settings()

    ocr = OcrOptions(
        backend=s.ocr_primary,
        fallbacks=[s.ocr_fallback] if s.ocr_fallback else None,
        languages=s.ocr_languages,
        min_confidence=s.ocr_confidence_threshold,
        use_pdf_text=True,
        dpi=300,
        device=s.ocr_device,
    )

    review = ReviewOptions(
        enqueue=True,
        min_classification_confidence=0.75,
        documents_dir=(Path(s.review_documents_dir) if s.review_documents_dir else None),
    )

    return ProcessOptions(
        ocr=ocr,
        schema_model=BonusTerms,
        schema_version=SCHEMA_VERSION,
        classify=False,
        include_layout=False,
        escalate=True,
        review=review,
        llm=_build_llm(s),
    )


def extract_terms(
    source: str | Path,
    *,
    options: ProcessOptions | None = None,
    settings: Settings | None = None,
) -> list[BonusTerms]:
    """Извлекает бонусные условия из документа."""
    register_bonus_schema()
    if options is None:
        options = build_process_options(settings)

    logger.info("Извлечение: %s", source)
    result: DocumentResult = process_document(source, options)

    terms: list[BonusTerms] = []
    for doc in _iter_documents(result):
        if isinstance(doc, BonusTerms):
            terms.append(doc)
        else:
            try:
                terms.append(BonusTerms.model_validate(doc))
            except ValidationError as exc:
                logger.warning("Пропуск документа (валидация): %s", exc)

    if not terms:
        logger.warning("Извлечение не дало результатов для %s", source)

    return terms


def _iter_documents(result: DocumentResult) -> Sequence[object]:
    """Достаёт из DocumentResult список документов."""
    typed = result.document
    if typed is not None:
        return [typed]
    if result.extracted:
        return [result.extracted]
    return []


def to_field_sources(result: DocumentResult) -> dict[str, FieldSource]:
    """Конвертирует SourceLocation -> доменный FieldSource.

    Геометрия (bbox) не переносится: в PoC она не используется.
    docket.BoundingBox — pydantic-модель, итерируется как (key, value),
    а не как (x0, y0, x1, y1). Вернёмся к конвертации в задаче 4.2
    (подсветка источника в UI).
    """
    out: dict[str, FieldSource] = {}
    for field_path, location in (result.field_sources or {}).items():
        out[field_path] = FieldSource(
            page=location.page,
            quote=location.quote,
            status=location.status,
            confidence=location.confidence,
            located_by=location.located_by,
        )
    return out


def build_field_rules() -> list[FieldRule]:
    """Правила извлечения из текстового слоя (vendor templates)."""
    return [
        FieldRule(field="supplier_name", label="Поставщик", value="Поставщик"),
        FieldRule(field="inn.value", label="ИНН", value="ИНН"),
        FieldRule(field="period", label="Период", value="Период"),
    ]
