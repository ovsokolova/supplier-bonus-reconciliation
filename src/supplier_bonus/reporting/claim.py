"""Генератор черновика претензионного письма.

Формирует markdown-текст по выбранным расхождениям из
ReconciliationResult. Итоговый документ предназначен для
юридической проверки перед отправкой поставщику.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from supplier_bonus.schemas import (
    MatchStatus,
    ReconciliationResult,
    ReconciliationRow,
)

logger = logging.getLogger(__name__)

DISCLAIMER = "[ЧЕРНОВИК — требует юридической проверки]"

# Статусы, которые считаются расхождениями и попадают в претензию.
DISCREPANCY_STATUSES = {
    MatchStatus.AMOUNT_MISMATCH,
    MatchStatus.MISSING_IN_ACTUALS,
    MatchStatus.MISSING_IN_CONTRACT,
    MatchStatus.PERIOD_OFFSET,
    MatchStatus.NEEDS_REVIEW,
}


@dataclass(frozen=True)
class ClaimDraft:
    """Результат генерации черновика претензии."""

    text: str
    supplier_name: str
    period: str
    total_amount: float
    rows_count: int
    disclaimer: str = DISCLAIMER


def _select_discrepancies(
    result: ReconciliationResult,
    supplier_name: str,
    period: str,
) -> list[ReconciliationRow]:
    """Отбирает строки-расхождения по поставщику и периоду."""
    return [
        row
        for row in result.rows
        if row.status in DISCREPANCY_STATUSES
        and row.supplier_name == supplier_name
        and row.period == period
    ]


def _render_table(rows: list[ReconciliationRow]) -> str:
    """Markdown-таблица расхождений."""
    if not rows:
        return "_Расхождений не найдено._"
    lines = [
        "| Период | Ожидаемо, ₽ | Факт, ₽ | Отклонение, ₽ | Статус |",
        "|---|---:|---:|---:|---|",
    ]
    for row in rows:
        expected = f"{row.expected:,.2f}" if row.expected is not None else "—"
        actual = f"{row.actual:,.2f}" if row.actual is not None else "—"
        diff = f"{row.diff:,.2f}" if row.diff is not None else "—"
        lines.append(f"| {row.period} | {expected} | {actual} | {diff} | {row.status.value} |")
    return "\n".join(lines)


def _total_amount(rows: list[ReconciliationRow]) -> float:
    """Сумма расхождений по модулю отклонения.

    Для amount_mismatch — |diff|.
    Для missing_* — сумма ожидаемой или фактической (что есть).
    """
    total = 0.0
    for row in rows:
        if row.status is MatchStatus.AMOUNT_MISMATCH and row.diff is not None:
            total += abs(row.diff)
        elif row.status is MatchStatus.MISSING_IN_ACTUALS and row.expected is not None:
            total += abs(row.expected)
        elif row.status is MatchStatus.MISSING_IN_CONTRACT and row.actual is not None:
            total += abs(row.actual)
    return round(total, 2)


def build_claim(
    result: ReconciliationResult,
    *,
    supplier_name: str,
    period: str,
    contract_reference: str = "Приложение №5 к договору",
    today: date | None = None,
) -> ClaimDraft:
    """Формирует черновик претензии по поставщику и периоду.

    Если расхождений нет — возвращает ClaimDraft с пустым текстом
    и rows_count=0.
    """
    rows = _select_discrepancies(result, supplier_name, period)
    if not rows:
        logger.info("Претензия: расхождений нет (%s, %s)", supplier_name, period)
        return ClaimDraft(
            text="",
            supplier_name=supplier_name,
            period=period,
            total_amount=0.0,
            rows_count=0,
        )

    total = _total_amount(rows)
    d = today or date.today()
    table = _render_table(rows)

    text = f"""# Претензия по бонусам

**Поставщик:** {supplier_name}
**Период:** {period}
**Ссылка на договор:** {contract_reference}
**Дата формирования:** {d.isoformat()}

## Выявленные расхождения

{table}

**Итоговая сумма расхождения:** {total:,.2f} ₽

## Требование

Просим в течение 10 рабочих дней с момента получения настоящей
претензии:

- доплатить сумму расхождения **{total:,.2f} ₽** на расчётный счёт,
  либо
- предоставить письменные пояснения о причинах расхождения
  с приложением подтверждающих документов.

В случае неполучения ответа в указанный срок мы будем вынуждены
обратиться в арбитражный суд.

## Приложения

1. Копия договора и приложения №5.
2. Расчёт расхождений (таблица выше).
3. Выгрузка из учётной системы.

---

{DISCLAIMER}
"""
    logger.info(
        "Претензия сформирована: %s, %s, сумма %s",
        supplier_name,
        period,
        total,
    )
    return ClaimDraft(
        text=text,
        supplier_name=supplier_name,
        period=period,
        total_amount=total,
        rows_count=len(rows),
    )


def available_suppliers(result: ReconciliationResult) -> list[str]:
    """Список поставщиков с расхождениями."""
    seen: set[str] = set()
    for row in result.rows:
        if row.status in DISCREPANCY_STATUSES:
            seen.add(row.supplier_name)
    return sorted(seen)


def available_periods(
    result: ReconciliationResult,
    supplier_name: str,
) -> list[str]:
    """Список периодов с расхождениями по выбранному поставщику."""
    seen: set[str] = set()
    for row in result.rows:
        if row.status in DISCREPANCY_STATUSES and row.supplier_name == supplier_name:
            seen.add(row.period)
    return sorted(seen)
