"""Тесты генератора претензий."""

from __future__ import annotations

from datetime import date

from supplier_bonus.reporting.claim import (
    DISCLAIMER,
    available_periods,
    available_suppliers,
    build_claim,
)
from supplier_bonus.schemas import (
    MatchStatus,
    ReconciliationResult,
    ReconciliationRow,
    ReconciliationSummary,
)


def _result() -> ReconciliationResult:
    return ReconciliationResult(
        summary=ReconciliationSummary(
            matched_within_tolerance=1,
            amount_mismatch=1,
            missing_in_actuals=1,
            missing_in_contract=1,
        ),
        rows=[
            ReconciliationRow(
                supplier_name="ООО «Ромашка»",
                period="2026-Q1",
                expected=100_000.0,
                actual=100_000.0,
                status=MatchStatus.MATCHED_WITHIN_TOLERANCE,
            ),
            ReconciliationRow(
                supplier_name="ООО «Ромашка»",
                period="2026-Q1",
                expected=250_000.0,
                actual=200_000.0,
                diff=50_000.0,
                status=MatchStatus.AMOUNT_MISMATCH,
            ),
            ReconciliationRow(
                supplier_name="ООО «Ромашка»",
                period="2026-Q1",
                expected=75_000.0,
                actual=None,
                status=MatchStatus.MISSING_IN_ACTUALS,
            ),
            ReconciliationRow(
                supplier_name="ООО «Василёк»",
                period="2026-Q1",
                expected=None,
                actual=40_000.0,
                status=MatchStatus.MISSING_IN_CONTRACT,
            ),
            ReconciliationRow(
                supplier_name="ООО «Ромашка»",
                period="2026-Q2",
                expected=10_000.0,
                actual=10_000.0,
                status=MatchStatus.MATCHED_WITHIN_TOLERANCE,
            ),
        ],
        amount_tolerance=1.0,
        fuzzy_threshold=90,
    )


def test_claim_no_discrepancies() -> None:
    """Нет расхождений — пустой ClaimDraft."""
    draft = build_claim(
        _result(),
        supplier_name="ООО «НетТакого»",
        period="2026-Q1",
    )
    assert draft.rows_count == 0
    assert draft.text == ""
    assert draft.total_amount == 0.0


def test_claim_filters_by_supplier() -> None:
    draft = build_claim(
        _result(),
        supplier_name="ООО «Ромашка»",
        period="2026-Q1",
        today=date(2026, 5, 1),
    )
    assert draft.supplier_name == "ООО «Ромашка»"
    assert draft.rows_count == 2  # amount_mismatch + missing_in_actuals
    assert "ООО «Василёк»" not in draft.text


def test_claim_filters_by_period() -> None:
    draft = build_claim(
        _result(),
        supplier_name="ООО «Ромашка»",
        period="2026-Q2",
    )
    assert draft.rows_count == 0


def test_claim_includes_amount_mismatch() -> None:
    draft = build_claim(
        _result(),
        supplier_name="ООО «Ромашка»",
        period="2026-Q1",
        today=date(2026, 5, 1),
    )
    assert "amount_mismatch" in draft.text
    assert "missing_in_actuals" in draft.text
    assert "250,000.00" in draft.text
    assert "50,000.00" in draft.text


def test_claim_total_amount() -> None:
    """Итог: 50 000 (diff) + 75 000 (missing_in_actuals) = 125 000."""
    draft = build_claim(
        _result(),
        supplier_name="ООО «Ромашка»",
        period="2026-Q1",
    )
    assert draft.total_amount == 125_000.0


def test_claim_disclaimer_present() -> None:
    draft = build_claim(
        _result(),
        supplier_name="ООО «Ромашка»",
        period="2026-Q1",
    )
    assert DISCLAIMER in draft.text
    assert draft.disclaimer == DISCLAIMER


def test_available_suppliers() -> None:
    suppliers = available_suppliers(_result())
    assert "ООО «Ромашка»" in suppliers
    assert "ООО «Василёк»" in suppliers


def test_available_periods() -> None:
    periods = available_periods(_result(), "ООО «Ромашка»")
    assert periods == ["2026-Q1"]
