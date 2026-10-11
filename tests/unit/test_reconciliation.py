"""Тесты движка сверки."""

from __future__ import annotations

import pandas as pd

from supplier_bonus.reconciliation.engine import MatchConfig, reconcile
from supplier_bonus.reconciliation.normalize import normalize_inn, normalize_name
from supplier_bonus.schemas import MatchStatus


def test_normalize_name_removes_opf_and_junk() -> None:
    assert normalize_name("ООО «Пример»") == "пример"
    assert normalize_name("АО  Пример-Трейд") == "пример-трейд"
    assert normalize_name("ПАО   Ромашка,  инк.") == "ромашка инк"


def test_normalize_inn_keeps_only_digits() -> None:
    assert normalize_inn("7701234567") == "7701234567"
    assert normalize_inn("ИНН 770-123-45-67") == "7701234567"
    assert normalize_inn("123") is None
    assert normalize_inn(None) is None


def test_reconcile_exact_match() -> None:
    contracts = pd.DataFrame(
        [
            {
                "supplier_name": "ООО «Пример»",
                "inn": "7701234567",
                "period": "2026-Q1",
                "amount": 100_000.0,
            }
        ]
    )
    actuals = pd.DataFrame(
        [
            {
                "supplier_name": "ООО «Пример»",
                "inn": "7701234567",
                "period": "2026-Q1",
                "amount": 100_000.0,
            }
        ]
    )
    result = reconcile(contracts, actuals)
    assert result.summary.matched_by_inn == 1
    assert result.rows[0].status is MatchStatus.MATCHED_WITHIN_TOLERANCE


def test_reconcile_amount_mismatch() -> None:
    contracts = pd.DataFrame(
        [{"supplier_name": "X", "inn": None, "period": "2026-Q1", "amount": 100.0}]
    )
    actuals = pd.DataFrame(
        [{"supplier_name": "X", "inn": None, "period": "2026-Q1", "amount": 80.0}]
    )
    result = reconcile(contracts, actuals)
    assert result.summary.amount_mismatch == 1
    assert result.rows[0].diff == 20.0


def test_reconcile_missing_in_actuals() -> None:
    contracts = pd.DataFrame(
        [{"supplier_name": "Y", "inn": None, "period": "2026-Q1", "amount": 50.0}]
    )
    actuals = pd.DataFrame(columns=["supplier_name", "inn", "period", "amount"])
    result = reconcile(contracts, actuals)
    assert result.summary.missing_in_actuals == 1
    assert result.rows[0].status is MatchStatus.MISSING_IN_ACTUALS


def test_reconcile_fuzzy_fallback() -> None:
    contracts = pd.DataFrame(
        [
            {
                "supplier_name": "ООО «Пример»",
                "inn": None,
                "period": "2026-Q1",
                "amount": 100.0,
            }
        ]
    )
    actuals = pd.DataFrame(
        [
            {
                "supplier_name": "ООО «Пример-Трейд»",
                "inn": None,
                "period": "2026-Q1",
                "amount": 100.0,
            }
        ]
    )
    cfg = MatchConfig(fuzzy_threshold=80)
    result = reconcile(contracts, actuals, config=cfg)
    assert result.summary.matched_fuzzy == 1
    assert result.rows[0].similarity is not None
    assert result.rows[0].similarity >= 80


def test_reconcile_empty_inputs() -> None:
    result = reconcile(pd.DataFrame(), pd.DataFrame())
    assert result.rows == []
    assert result.summary.matched == 0
