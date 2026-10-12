"""Движок сверки: outer join по ИНН с fallback на fuzzy-сопоставление."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import pandas as pd
from rapidfuzz import fuzz

from supplier_bonus.reconciliation.normalize import normalize_inn, normalize_name
from supplier_bonus.schemas import (
    MatchStatus,
    ReconciliationResult,
    ReconciliationRow,
    ReconciliationSummary,
)

logger = logging.getLogger(__name__)

_FUZZY_SCORERS: tuple[tuple[Callable[[str, str], float], float], ...] = (
    (fuzz.token_sort_ratio, 1.0),
    (fuzz.token_set_ratio, 1.0),
)


@dataclass(frozen=True)
class MatchConfig:
    amount_tolerance: float = 1.0
    fuzzy_threshold: int = 90
    period_offset_months: int = 1


def _score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    total_weight = sum(w for _, w in _FUZZY_SCORERS)
    total = sum(scorer(a, b) * w for scorer, w in _FUZZY_SCORERS)
    return total / total_weight


def _best_match(
    needle: str,
    haystack: list[str],
    threshold: int,
) -> tuple[str, float] | None:
    """Возвращает лучшего кандидата из haystack или None."""
    if not haystack or not needle:
        return None
    best_candidate: str | None = None
    best_score = 0.0
    for candidate in haystack:
        score = _score(needle, candidate)
        if score > best_score:
            best_score = score
            best_candidate = candidate
    if best_candidate is None or best_score < threshold:
        return None
    return best_candidate, best_score


def _join_key(row: pd.Series, name_field: str, inn_field: str) -> str:
    inn = normalize_inn(row.get(inn_field))
    if inn:
        return f"inn:{inn}"
    return f"name:{normalize_name(str(row.get(name_field, '')))}"


def reconcile(
    contracts: pd.DataFrame,
    actuals: pd.DataFrame,
    *,
    config: MatchConfig | None = None,
    name_field: str = "supplier_name",
    inn_field: str = "inn",
    period_field: str = "period",
    amount_field: str = "amount",
) -> ReconciliationResult:
    """Сопоставляет договорные условия с фактическими данными."""
    cfg = config or MatchConfig()

    if contracts.empty and actuals.empty:
        return ReconciliationResult(
            summary=ReconciliationSummary(),
            rows=[],
            amount_tolerance=cfg.amount_tolerance,
            fuzzy_threshold=cfg.fuzzy_threshold,
        )

    contracts = contracts.copy()
    actuals = actuals.copy()
    contracts["_key"] = contracts.apply(lambda r: _join_key(r, name_field, inn_field), axis=1)
    actuals["_key"] = actuals.apply(lambda r: _join_key(r, name_field, inn_field), axis=1)

    merged = contracts.merge(
        actuals,
        on=["_key", period_field],
        how="outer",
        suffixes=("_contract", "_actual"),
        indicator=True,
    )

    rows: list[ReconciliationRow] = []
    summary = ReconciliationSummary()

    for row in merged.itertuples(index=False):
        # itertuples быстрее iterrows, но доступ к полям — через ._asdict()
        # или getattr. Используем getattr с fallback.
        name_c = getattr(row, f"{name_field}_contract", None)
        name_a = getattr(row, f"{name_field}_actual", None)
        period = getattr(row, period_field, None)
        amount_c = getattr(row, f"{amount_field}_contract", None)
        amount_a = getattr(row, f"{amount_field}_actual", None)

        has_name_c = name_c is not None and pd.notna(name_c)
        has_name_a = name_a is not None and pd.notna(name_a)
        has_amount_c = isinstance(amount_c, (int, float)) and pd.notna(amount_c)
        has_amount_a = isinstance(amount_a, (int, float)) and pd.notna(amount_a)

        if has_name_c and has_name_a:
            diff: float | None = None
            if has_amount_c and has_amount_a:
                diff = float(cast(float, amount_c)) - float(cast(float, amount_a))
                if abs(diff) <= cfg.amount_tolerance:
                    status = MatchStatus.MATCHED_WITHIN_TOLERANCE
                    summary.matched_within_tolerance += 1
                else:
                    status = MatchStatus.AMOUNT_MISMATCH
                    summary.amount_mismatch += 1
            else:
                status = MatchStatus.MATCHED
                summary.matched += 1

            rows.append(
                ReconciliationRow(
                    supplier_name=str(name_c),
                    period=str(period),
                    expected=float(cast(float, amount_c)) if has_amount_c else None,
                    actual=float(cast(float, amount_a)) if has_amount_a else None,
                    diff=diff,
                    status=status,
                )
            )
            continue

        if has_name_c and not has_name_a:
            summary.missing_in_actuals += 1
            rows.append(
                ReconciliationRow(
                    supplier_name=str(name_c),
                    period=str(period),
                    expected=float(cast(float, amount_c)) if has_amount_c else None,
                    actual=None,
                    status=MatchStatus.MISSING_IN_ACTUALS,
                )
            )
            continue

        if not has_name_c and has_name_a:
            summary.missing_in_contract += 1
            rows.append(
                ReconciliationRow(
                    supplier_name=str(name_a),
                    period=str(period),
                    expected=None,
                    actual=float(cast(float, amount_a)) if has_amount_a else None,
                    status=MatchStatus.MISSING_IN_CONTRACT,
                )
            )

    # Fuzzy-fallback для строк missing_in_actuals.
    if cfg.fuzzy_threshold > 0 and actuals.shape[0] > 0:
        actual_names = actuals[name_field].dropna().astype(str).tolist()
        normalized_actual = [normalize_name(n) for n in actual_names]
        for i, row in enumerate(rows):
            if row.status is not MatchStatus.MISSING_IN_ACTUALS:
                continue
            needle = normalize_name(row.supplier_name)
            best = _best_match(needle, normalized_actual, cfg.fuzzy_threshold)
            if best is None:
                continue
            matched_raw, score = best
            original = next(
                (n for n in actual_names if normalize_name(n) == matched_raw),
                matched_raw,
            )
            rows[i] = row.model_copy(
                update={
                    "status": MatchStatus.MATCHED_FUZZY,
                    "supplier_name_raw": original,
                    "similarity": round(score, 1),
                }
            )
            summary.matched_fuzzy += 1
            summary.missing_in_actuals -= 1

    return ReconciliationResult(
        summary=summary,
        rows=rows,
        amount_tolerance=cfg.amount_tolerance,
        fuzzy_threshold=cfg.fuzzy_threshold,
    )
