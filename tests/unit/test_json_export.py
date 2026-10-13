"""Тесты JSON-экспорта."""

from __future__ import annotations

import json

from supplier_bonus.reporting.claim import build_claim
from supplier_bonus.reporting.json_export import (
    SCHEMA_VERSION,
    claim_to_dict,
    claim_to_json,
    result_to_dict,
    result_to_json,
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
        ),
        rows=[
            ReconciliationRow(
                supplier_name="ООО «Ромашка»",
                period="2026-Q1",
                expected=100_000.0,
                actual=100_000.0,
                diff=0.0,
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
        ],
        amount_tolerance=1.0,
        fuzzy_threshold=90,
    )


def test_result_to_dict_has_schema_version() -> None:
    d = result_to_dict(_result())
    assert d["schema_version"] == SCHEMA_VERSION


def test_result_to_dict_contains_summary_and_rows() -> None:
    d = result_to_dict(_result())
    assert "summary" in d
    assert "rows" in d
    assert len(d["rows"]) == 3
    assert d["summary"]["amount_mismatch"] == 1


def test_result_to_json_is_valid_json() -> None:
    text = result_to_json(_result())
    parsed = json.loads(text)
    assert parsed["schema_version"] == SCHEMA_VERSION
    assert parsed["amount_tolerance"] == 1.0
    assert parsed["fuzzy_threshold"] == 90


def test_result_to_json_preserves_cyrillic() -> None:
    text = result_to_json(_result())
    # ensure_ascii=False — кириллица не должна быть \uXXXX
    assert "Ромашка" in text
    assert "\\u" not in text


def test_claim_to_dict_contains_disclaimer() -> None:
    draft = build_claim(
        _result(),
        supplier_name="ООО «Ромашка»",
        period="2026-Q1",
    )
    d = claim_to_dict(draft)
    assert d["schema_version"] == SCHEMA_VERSION
    assert "ЧЕРНОВИК" in d["disclaimer"]
    assert d["supplier_name"] == "ООО «Ромашка»"
    assert d["rows_count"] >= 1


def test_claim_to_json_is_valid_json() -> None:
    draft = build_claim(
        _result(),
        supplier_name="ООО «Ромашка»",
        period="2026-Q1",
    )
    text = claim_to_json(draft)
    parsed = json.loads(text)
    assert parsed["total_amount"] > 0
    assert parsed["period"] == "2026-Q1"
