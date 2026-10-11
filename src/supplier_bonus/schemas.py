"""Pydantic-схемы для бонусных условий и результатов сверки."""

from __future__ import annotations

from enum import StrEnum

from docket import CitedDocument
from pydantic import BaseModel, Field, field_validator


class BonusType(StrEnum):
    MONETARY = "monetary"
    GOODS = "goods"
    MIXED = "mixed"


class BaseMetric(StrEnum):
    PURCHASE_VOLUME = "purchase_volume"
    PAYMENT_AMOUNT = "payment_amount"
    QUANTITY = "quantity"


class Tier(BaseModel):
    threshold: float = Field(ge=0)
    rate: float = Field(ge=0, le=1)


class Inn(BaseModel):
    value: str = Field(pattern=r"^\d{10}$|^\d{12}$")
    kpp: str | None = Field(default=None, pattern=r"^\d{9}$")


class BonusTerms(CitedDocument):
    """Бонусные условия поставщика.

    Наследует docket.CitedDocument — получает field_locations
    (dict[str, Citation]) для привязки каждого поля к странице
    и цитате исходного документа.
    """

    supplier_name: str
    supplier_name_raw: str | None = None
    inn: Inn | None = None
    bonus_type: BonusType
    base_metric: BaseMetric
    tiers: list[Tier] = Field(default_factory=list)
    period: str = Field(pattern=r"^\d{4}-Q[1-4]$|^\d{4}-\d{2}$")
    currency: str = "RUB"
    tax_included: bool | None = None

    @field_validator("tiers")
    @classmethod
    def tiers_monotonic(cls, v: list[Tier]) -> list[Tier]:
        thresholds = [t.threshold for t in v]
        if thresholds != sorted(thresholds):
            raise ValueError("tiers должны быть отсортированы по threshold")
        return v


class MatchStatus(StrEnum):
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

    page: int | None = None
    quote: str | None = None
    status: str | None = None
    bbox: list[float] | None = None
    confidence: float | None = None
    located_by: str | None = None


class ReconciliationRow(BaseModel):
    supplier_name: str
    supplier_name_raw: str | None = None
    period: str
    expected: float | None = None
    actual: float | None = None
    diff: float | None = None
    similarity: float | None = None
    status: MatchStatus
    notes: str | None = None


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
