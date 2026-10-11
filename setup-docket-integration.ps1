# setup-docket-integration.ps1
# Запуск: pwsh -ExecutionPolicy Bypass -File .\setup-docket-integration.ps1
# Из корня репозитория D:\downloads\AI\supplier-bonus-reconciliation

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# --- Безопасная запись UTF-8 без BOM ---
function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter()] [AllowEmptyString()] [string] $Content = ""
    )
    if ($null -eq $Content) { $Content = "" }
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $full = [System.IO.Path]::GetFullPath(
        (Join-Path (Get-Location) $Path)
    )
    [System.IO.File]::WriteAllText($full, $Content, $utf8NoBom)
    Write-Host "  + $Path" -ForegroundColor Cyan
}

# --- Плейсхолдеры для тройных бэктиков ---
$F  = [char]0x60
$F3 = "$F$F$F"

# --- Корневые пути ---
$Chg = "openspec\changes\supplier-bonus-reconciliation"
$Src = "src\supplier_bonus"

# ============================================================
# 1. schemas.py
# ============================================================
$schemas = @'
"""Pydantic-схемы для бонусных условий и результатов сверки."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from docket import CitedDocument
from pydantic import BaseModel, Field, field_validator


class BonusType(str, Enum):
    MONETARY = "monetary"
    GOODS = "goods"
    MIXED = "mixed"


class BaseMetric(str, Enum):
    PURCHASE_VOLUME = "purchase_volume"
    PAYMENT_AMOUNT = "payment_amount"
    QUANTITY = "quantity"


class Tier(BaseModel):
    threshold: float = Field(ge=0)
    rate: float = Field(ge=0, le=1)


class Inn(BaseModel):
    value: str = Field(pattern=r"^\d{10}$|^\d{12}$")
    kpp: Optional[str] = Field(default=None, pattern=r"^\d{9}$")


class BonusTerms(CitedDocument):
    """Бонусные условия поставщика.

    Наследует docket.CitedDocument — получает field_locations
    (dict[str, Citation]) для привязки каждого поля к странице
    и цитате исходного документа.
    """

    supplier_name: str
    supplier_name_raw: Optional[str] = None
    inn: Optional[Inn] = None
    bonus_type: BonusType
    base_metric: BaseMetric
    tiers: list[Tier] = Field(default_factory=list)
    period: str = Field(pattern=r"^\d{4}-Q[1-4]$|^\d{4}-\d{2}$")
    currency: str = "RUB"
    tax_included: Optional[bool] = None

    @field_validator("tiers")
    @classmethod
    def tiers_monotonic(cls, v: list[Tier]) -> list[Tier]:
        thresholds = [t.threshold for t in v]
        if thresholds != sorted(thresholds):
            raise ValueError("tiers должны быть отсортированы по threshold")
        return v


class MatchStatus(str, Enum):
    MATCHED = "matched"
    MATCHED_BY_INN = "matched_by_inn"
    MATCHED_FUZZY = "matched_fuzzy"
    MATCHED_WITHIN_TOLERANCE = "matched_within_tolerance"
    AMOUNT_MISMATCH = "amount_mismatch"
    MISSING_IN_ACTUALS = "missing_in_actuals"
    MISSING_IN_CONTRACT = "missing_in_contract"
    PERIOD_OFFSET = "period_offset"
    NEEDS_REVIEW = "needs_review"


class FieldSource(BaseModel):
    """Доменное представление docket.SourceLocation для UI и отчётов."""

    page: Optional[int] = None
    quote: Optional[str] = None
    status: Optional[str] = None
    bbox: Optional[list[float]] = None
    confidence: Optional[float] = None
    located_by: Optional[str] = None


class ReconciliationRow(BaseModel):
    supplier_name: str
    supplier_name_raw: Optional[str] = None
    period: str
    expected: Optional[float] = None
    actual: Optional[float] = None
    diff: Optional[float] = None
    similarity: Optional[float] = None
    status: MatchStatus
    notes: Optional[str] = None


class ReconciliationSummary(BaseModel):
    matched: int = 0
    matched_by_inn: int = 0
    matched_fuzzy: int = 0
    matched_within_tolerance: int = 0
    amount_mismatch: int = 0
    missing_in_actuals: int = 0
    missing_in_contract: int = 0
    period_offset: int = 0
    needs_review: int = 0


class ReconciliationResult(BaseModel):
    summary: ReconciliationSummary
    rows: list[ReconciliationRow]
    amount_tolerance: float
    fuzzy_threshold: int
'@
Write-Utf8NoBom "$Src\schemas.py" $schemas

# ============================================================
# 2. config.py
# ============================================================
$config = @'
"""Конфигурация приложения. Читается из переменных окружения."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_list(name: str, default: str) -> list[str]:
    return [s.strip() for s in os.getenv(name, default).split(",") if s.strip()]


@dataclass(frozen=True)
class Settings:
    # LLM
    llm_provider: str = os.getenv("LLM_PROVIDER", "ollama")
    llm_model: str = os.getenv("LLM_MODEL", "qwen2.5:7b-instruct")
    llm_vision_model: str | None = os.getenv("LLM_VISION_MODEL") or None

    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    openai_base_url: str | None = os.getenv("OPENAI_BASE_URL") or None
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY") or None

    # OCR
    ocr_primary: str = os.getenv("OCR_PRIMARY", "tesseract")
    ocr_fallback: str = os.getenv("OCR_FALLBACK", "paddleocr")
    ocr_confidence_threshold: float = float(
        os.getenv("OCR_CONFIDENCE_THRESHOLD", "0.75")
    )
    ocr_languages: list[str] = field(
        default_factory=lambda: _env_list("OCR_LANGUAGES", "ru,en")
    )
    ocr_device: str = os.getenv("OCR_DEVICE", "cpu")

    # Сверка
    amount_tolerance: float = float(os.getenv("AMOUNT_TOLERANCE", "1.0"))
    fuzzy_threshold: int = int(os.getenv("FUZZY_THRESHOLD", "90"))

    # Review queue
    review_documents_dir: str | None = (
        os.getenv("REVIEW_DOCUMENTS_DIR") or "./data/review"
    )

    # Данные
    test_data_path: Path = Path(os.getenv("TEST_DATA_PATH", "./data/examples"))


def get_settings() -> Settings:
    return Settings()
'@
Write-Utf8NoBom "$Src\config.py" $config

# ============================================================
# 3. docket_adapter.py
# ============================================================
$adapter = @'
"""Адаптер между docket.process_document и доменной моделью BonusTerms."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Sequence

from docket import (
    DocumentResult,
    FieldRule,
    LLMBackend,
    OllamaBackend,
    OpenAICompatibleBackend,
    OcrOptions,
    ProcessOptions,
    ReviewOptions,
    SchemaSpec,
    process_document,
    register_schema,
)

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
    except Exception as exc:  # noqa: BLE001
        logger.warning("Schema %s: %s", SCHEMA_ID, exc)
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
        documents_dir=(
            Path(s.review_documents_dir) if s.review_documents_dir else None
        ),
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
            except Exception as exc:  # noqa: BLE001
                logger.warning("Пропуск документа: %s", exc)

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
    """Конвертирует SourceLocation -> доменный FieldSource."""
    out: dict[str, FieldSource] = {}
    for field_path, location in (result.field_sources or {}).items():
        out[field_path] = FieldSource(
            page=location.page,
            quote=location.quote,
            status=location.status,
            bbox=list(location.bbox) if location.bbox is not None else None,
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
'@
Write-Utf8NoBom "$Src\extraction\docket_adapter.py" $adapter

# ============================================================
# 4. .env.example
# ============================================================
$envExample = @'
# LLM
LLM_PROVIDER=ollama
LLM_MODEL=qwen2.5:7b-instruct
LLM_VISION_MODEL=qwen2.5-vl:7b
OLLAMA_BASE_URL=http://localhost:11434

# OPENAI_BASE_URL=
# OPENAI_API_KEY=

# OCR
OCR_PRIMARY=tesseract
OCR_FALLBACK=paddleocr
OCR_CONFIDENCE_THRESHOLD=0.75
OCR_LANGUAGES=ru,en
OCR_DEVICE=cpu

# Сверка
AMOUNT_TOLERANCE=1.0
FUZZY_THRESHOLD=90

# Review queue
REVIEW_DOCUMENTS_DIR=./data/review

# Данные
TEST_DATA_PATH=./data/examples
'@
Write-Utf8NoBom ".env.example" $envExample

# ============================================================
# 5. tests/unit/test_extraction_adapter.py
# ============================================================
$testAdapter = @'
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
'@
Write-Utf8NoBom "tests\unit\test_extraction_adapter.py" $testAdapter

# ============================================================
# 6. ADR-001 — добавить раздел "Интеграция"
# ============================================================
$adr1Path = "$Chg\adr\ADR-001-docket-idp.md"
if (Test-Path $adr1Path) {
    $integration = @'

## Интеграция

Используем публичный API docket 0.5.0.

### Схема извлечения

- `SchemaSpec(schema_id, model=BonusTerms, description, version,
  display_name, status, cited_fields)` — регистрирует схему;
- `register_schema(spec, replace_existing=False)` — идемпотентная
  регистрация;
- `cited_fields` перечисляет поля, для которых docket обязан
  вернуть цитату (страница + quote). Валидатор проверяет,
  что цитата действительно есть на указанной странице.

### Обработка документа

- `process_document(source, options, on_stage=None) -> DocumentResult`;
- `ProcessOptions(ocr=OcrOptions(...), schema_model=BonusTerms,
  classify=False, include_layout=False, escalate=True,
  review=ReviewOptions(...), llm=OllamaBackend(...))`;
- `on_stage(stage, payload)` — хуки acquire, classify,
  extract, validate для логирования.

### OCR-цепочка

- `OcrOptions(backend="tesseract", fallbacks=["paddleocr"],
  languages=["ru","en"], min_confidence=0.75, use_pdf_text=True,
  dpi=300, device="cpu")`;
- при провале валидации docket сам перечитывает документ
  vision-моделью (escalate=True).

### LLM

- `OllamaBackend(host, text_model, vision_model, think)` —
  локальный инференс (см. ADR-003);
- `OpenAICompatibleBackend(base_url, api_key, ...)` — только
  по согласованию с ИБ.

### Результат

- `DocumentResult.extracted` — dict;
- `DocumentResult.document` — типизированная схема
  (BonusTerms), если она зарегистрирована;
- `DocumentResult.field_sources: dict[str, SourceLocation]` —
  источник для каждого поля;
- `DocumentResult.highlights(page=None) -> list[(field, source,
  region)]` — тройки для отрисовки боксов поверх PDF;
- `DocumentResult.needs_review: bool` и
  `review_reasons: list[str]` — очередь проверки.

### Прослеживаемость

- LLM возвращает `field_locations: dict[str, Citation]`
  (page + quote);
- pipeline резолвит цитату в `SourceLocation` с bbox,
  confidence и status (verified | fuzzy | conflicting |
  unlocated);
- `Citation` — только page и quote, никакой геометрии от LLM;
- bbox и word_ids берутся из word boxes страницы.

### Дополнительно

- `verify(document, text, ...)` — валидирует внешне
  сгенерированный документ против исходного текста;
- `corroborate(result, purchase_order=..., transactions=...)` —
  подтверждает поля по PO или банковским транзакциям;
- `DocumentResult.complete` — все страницы дали текст;
- `DocumentResult.is_valid` — итог валидации.
'@
    Add-Content -Path $adr1Path -Value $integration -Encoding utf8
    Write-Host "  ~ $adr1Path (добавлен раздел Интеграция)" -ForegroundColor Cyan
}

# ============================================================
# 7. design.md — добавить блок про docket API
# ============================================================
$designPath = "$Chg\design.md"
if (Test-Path $designPath) {
    $designExtra = @'

### Интеграция с docket

1. `register_bonus_schema()` — SchemaSpec с cited_fields.
2. `build_process_options()` — OcrOptions + ReviewOptions +
   OllamaBackend.
3. `process_document(source, options)` -> DocumentResult.
4. `result.document` -> BonusTerms (типизированная схема).
5. `result.field_sources` -> SourceLocation по каждому полю.
6. `result.needs_review` -> очередь проверки.
7. `result.highlights()` -> боксы для UI.
'@
    Add-Content -Path $designPath -Value $designExtra -Encoding utf8
    Write-Host "  ~ $designPath (добавлен блок про docket API)" -ForegroundColor Cyan
}

# ============================================================
# 8. Проверка импортов
# ============================================================
Write-Host ""
Write-Host "=== Проверка импортов ===" -ForegroundColor Yellow

$checks = @(
    "from supplier_bonus.schemas import BonusTerms, ReconciliationResult; print('schemas OK')",
    "from supplier_bonus.config import get_settings; print('config OK')",
    "from supplier_bonus.extraction.docket_adapter import build_schema_spec, build_process_options; print('adapter OK')"
)

foreach ($code in $checks) {
    try {
        $out = python -c $code 2>&1
        Write-Host "  $out" -ForegroundColor Green
    } catch {
        Write-Host "  FAIL: $code" -ForegroundColor Red
        Write-Host "  $_" -ForegroundColor Red
    }
}

# ============================================================
# 9. Запуск тестов
# ============================================================
Write-Host ""
Write-Host "=== Запуск тестов ===" -ForegroundColor Yellow
try {
    pytest "tests\unit\test_extraction_adapter.py" -v 2>&1 |
        Select-Object -Last 20 |
        ForEach-Object { Write-Host "  $_" }
} catch {
    Write-Host "  pytest не установлен или упал" -ForegroundColor Yellow
}

# ============================================================
# 10. ИТОГ
# ============================================================
Write-Host ""
Write-Host "=== Проверка файлов ===" -ForegroundColor Yellow
$expected = @(
    "$Src\schemas.py",
    "$Src\config.py",
    "$Src\extraction\docket_adapter.py",
    ".env.example",
    "tests\unit\test_extraction_adapter.py",
    "$Chg\adr\ADR-001-docket-idp.md",
    "$Chg\design.md"
)
$ok = 0
foreach ($f in $expected) {
    if (Test-Path $f) {
        $lines = (Get-Content $f -Encoding utf8).Count
        Write-Host ("  OK  {0,-60} {1,4} строк" -f $f, $lines) -ForegroundColor Green
        $ok++
    } else {
        Write-Host "  MISSING  $f" -ForegroundColor Red
    }
}
Write-Host ""
Write-Host ("Итог: {0} из {1} файлов обновлено." -f $ok, $expected.Count) -ForegroundColor Yellow
Write-Host ""
Write-Host "Дальше:" -ForegroundColor Green
Write-Host "  1. Проверить тесты: pytest tests/unit/test_extraction_adapter.py -v" -ForegroundColor Green
Write-Host "  2. Прогнать линтеры: ruff check src tests ; mypy src" -ForegroundColor Green
Write-Host "  3. git add . ; git commit -m 'feat(extraction): integrate docket API v0.5.0'" -ForegroundColor Green
Write-Host "  4. git push" -ForegroundColor Green