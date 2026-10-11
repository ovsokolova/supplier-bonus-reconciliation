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
