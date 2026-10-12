"""Экспорт результатов сверки в Excel (openpyxl).

Три листа:
- «Список сверки» — построчно с полями и расхождениями;
- «Сводка сверки» — счётчики по статусам и допуску;
- «Требует обработки» — missing_*, amount_mismatch, matched_fuzzy.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.worksheet import Worksheet

from supplier_bonus.schemas import MatchStatus, ReconciliationResult

logger = logging.getLogger(__name__)

SHEET_ROWS = "Список сверки"
SHEET_SUMMARY = "Сводка сверки"
SHEET_ISSUES = "Требует обработки"

_STATUS_FILL = {
    MatchStatus.MATCHED: "C6EFCE",
    MatchStatus.MATCHED_BY_INN: "C6EFCE",
    MatchStatus.MATCHED_WITHIN_TOLERANCE: "C6EFCE",
    MatchStatus.MATCHED_FUZZY: "FFEB9C",
    MatchStatus.AMOUNT_MISMATCH: "FFC7CE",
    MatchStatus.MISSING_IN_ACTUALS: "FFC7CE",
    MatchStatus.MISSING_IN_CONTRACT: "FFC7CE",
    MatchStatus.PERIOD_OFFSET: "FFC7CE",
    MatchStatus.NEEDS_REVIEW: "FFEB9C",
}

_ISSUE_STATUSES = {
    MatchStatus.MISSING_IN_ACTUALS,
    MatchStatus.MISSING_IN_CONTRACT,
    MatchStatus.AMOUNT_MISMATCH,
    MatchStatus.MATCHED_FUZZY,
    MatchStatus.PERIOD_OFFSET,
    MatchStatus.NEEDS_REVIEW,
}

_HEADERS = [
    "Поставщик",
    "Исходное имя",
    "Период",
    "Ожидаемо",
    "Факт",
    "Отклонение",
    "Схожесть",
    "Статус",
]

_COLUMN_WIDTHS = {
    "A": 30,
    "B": 30,
    "C": 12,
    "D": 14,
    "E": 14,
    "F": 14,
    "G": 14,
    "H": 22,
    "I": 40,
}

_BOLD = Font(bold=True)
_WRAP = Alignment(wrap_text=True, vertical="top")


def _write_status(
    ws: Worksheet,
    row: int,
    col: int,
    status: MatchStatus,
) -> None:
    """Пишет статус с цветовой заливкой."""
    cell = ws.cell(row=row, column=col, value=status.value)
    color = _STATUS_FILL.get(status)
    if color:
        cell.fill = PatternFill("solid", fgColor=color)


def _write_header(ws: Worksheet) -> None:
    for idx, header in enumerate(_HEADERS, start=1):
        c = ws.cell(row=1, column=idx, value=header)
        c.font = _BOLD


def _set_widths(ws: Worksheet) -> None:
    for letter, width in _COLUMN_WIDTHS.items():
        ws.column_dimensions[letter].width = width


def export_to_excel(result: ReconciliationResult, path: str | Path) -> Path:
    """Сохраняет ReconciliationResult в xlsx (openpyxl)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()

    # --- Лист 1: Список сверки ---
    ws = wb.active
    ws.title = SHEET_ROWS
    _write_header(ws)
    for i, row in enumerate(result.rows, start=2):
        ws.cell(row=i, column=1, value=row.supplier_name)
        ws.cell(row=i, column=2, value=row.supplier_name_raw or "")
        ws.cell(row=i, column=3, value=row.period)
        ws.cell(row=i, column=4, value=row.expected or 0)
        ws.cell(row=i, column=5, value=row.actual or 0)
        ws.cell(row=i, column=6, value=row.diff or 0)
        ws.cell(row=i, column=7, value=row.similarity or 0)
        _write_status(ws, i, 8, row.status)
    _set_widths(ws)

    # --- Лист 2: Сводка сверки ---
    ws2 = wb.create_sheet(SHEET_SUMMARY)
    ws2.cell(row=1, column=1, value="Показатель").font = _BOLD
    ws2.cell(row=1, column=2, value="Значение").font = _BOLD
    s = result.summary
    summary_rows: list[tuple[str, Any]] = [
        ("matched", s.matched),
        ("matched_by_inn", s.matched_by_inn),
        ("matched_fuzzy", s.matched_fuzzy),
        ("matched_within_tolerance", s.matched_within_tolerance),
        ("amount_mismatch", s.amount_mismatch),
        ("missing_in_actuals", s.missing_in_actuals),
        ("missing_in_contract", s.missing_in_contract),
        ("period_offset", s.period_offset),
        ("needs_review", s.needs_review),
        ("amount_tolerance", result.amount_tolerance),
        ("fuzzy_threshold", result.fuzzy_threshold),
        ("total_rows", len(result.rows)),
    ]
    for i, (k, v) in enumerate(summary_rows, start=2):
        ws2.cell(row=i, column=1, value=k)
        ws2.cell(row=i, column=2, value=v)
    ws2.column_dimensions["A"].width = 32
    ws2.column_dimensions["B"].width = 14

    # --- Лист 3: Требует обработки ---
    ws3 = wb.create_sheet(SHEET_ISSUES)
    _write_header(ws3)
    r = 2
    for row in result.rows:
        if row.status not in _ISSUE_STATUSES:
            continue
        ws3.cell(row=r, column=1, value=row.supplier_name)
        ws3.cell(row=r, column=2, value=row.supplier_name_raw or "")
        ws3.cell(row=r, column=3, value=row.period)
        ws3.cell(row=r, column=4, value=row.expected or 0)
        ws3.cell(row=r, column=5, value=row.actual or 0)
        ws3.cell(row=r, column=6, value=row.diff or 0)
        ws3.cell(row=r, column=7, value=row.similarity or 0)
        _write_status(ws3, r, 8, row.status)
        if row.notes:
            c = ws3.cell(row=r, column=9, value=row.notes)
            c.alignment = _WRAP
        r += 1
    _set_widths(ws3)

    wb.save(path)
    logger.info("Отчёт сохранён: %s", path)
    return path
