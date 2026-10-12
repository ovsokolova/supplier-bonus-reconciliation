"""Интеграционный тест: reconcile на синтетических фикстурах."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from supplier_bonus.reconciliation.engine import reconcile

FIXTURES = Path("data/examples")
SCENARIOS = FIXTURES / "scenarios.json"

pytestmark = pytest.mark.skipif(
    not SCENARIOS.exists(),
    reason="Фикстуры не сгенерированы: python scripts/generate_fixtures.py",
)


def _load_scenarios() -> list[dict]:
    return json.loads(SCENARIOS.read_text(encoding="utf-8"))["scenarios"]


def _contracts_df(fx: dict) -> pd.DataFrame:
    inn = (fx["supplier"].get("inn") or "") if fx["supplier"] else ""
    return pd.DataFrame(
        [
            {
                "supplier_name": fx["supplier"]["name"],
                "inn": inn,
                "period": fx["period"],
                "amount": fx["expected_amount"],
            }
        ]
    )


def _actuals_df(contract_id: str) -> pd.DataFrame:
    csv = FIXTURES / "actuals" / f"{contract_id}_actual.csv"
    return pd.read_csv(csv, dtype={"inn": str}).fillna({"inn": ""})


def test_all_20_scenarios_present() -> None:
    assert len(_load_scenarios()) == 20


def test_scenarios_cover_10_types() -> None:
    types = {s["scenario"] for s in _load_scenarios()}
    expected = {
        "exact_match",
        "amount_mismatch",
        "missing_in_actuals",
        "missing_in_contract",
        "matched_fuzzy",
        "matched_no_inn",
        "tiered_3",
        "goods_bonus",
        "tax_variants",
        "period_offset",
    }
    assert types == expected


@pytest.mark.parametrize("idx", range(20))
def test_scenario_runs_without_error(idx: int) -> None:
    """Каждый сценарий проходит через reconcile без исключений."""
    fx = _load_scenarios()[idx]
    contracts = _contracts_df(fx)
    actuals = _actuals_df(fx["contract_id"])
    result = reconcile(contracts, actuals)
    assert len(result.rows) >= 1
    assert result.amount_tolerance == 1.0
    assert result.fuzzy_threshold == 90


@pytest.mark.parametrize(
    ("idx", "expected_field"),
    [
        # exact_match: строки совпадают
        (0, "matched_within_tolerance"),
        (1, "matched_within_tolerance"),
        (2, "matched_within_tolerance"),
        # amount_mismatch
        (3, "amount_mismatch"),
        (4, "amount_mismatch"),
        # missing_in_actuals
        (5, "missing_in_actuals"),
        (6, "missing_in_actuals"),
        # tiered_3, goods_bonus, tax_variants: суммы совпадают
        (11, "matched_within_tolerance"),
        (12, "matched_within_tolerance"),
        (13, "matched_within_tolerance"),
        (14, "matched_within_tolerance"),
        (15, "matched_within_tolerance"),
        (16, "matched_within_tolerance"),
        (17, "matched_within_tolerance"),
        (18, "matched_within_tolerance"),
    ],
)
def test_scenario_summary_field(idx: int, expected_field: str) -> None:
    fx = _load_scenarios()[idx]
    contracts = _contracts_df(fx)
    actuals = _actuals_df(fx["contract_id"])
    result = reconcile(contracts, actuals)
    assert getattr(result.summary, expected_field) >= 1
