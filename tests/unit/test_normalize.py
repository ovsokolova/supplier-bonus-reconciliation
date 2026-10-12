"""Тесты нормализации."""

from __future__ import annotations

import pytest

from supplier_bonus.reconciliation.normalize import normalize_inn, normalize_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("ООО «Пример»", "пример"),
        ("АО  Пример-Трейд", "пример трейд"),
        ("ПАО   Ромашка,  инк.", "ромашка инк"),
        ("ИП Сидоров И.И.", "сидоров и и"),
        ("", ""),
        ("  ", ""),
        ("ООО", ""),
        ("Ёжик", "ежик"),
        ("Пример", "пример"),
        ("Трейд", "трейд"),
    ],
)
def test_normalize_name(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("7701234567", "7701234567"),
        ("ИНН 770-123-45-67", "7701234567"),
        ("770123456789", "770123456789"),
        ("123", None),
        ("", None),
        (None, None),
    ],
)
def test_normalize_inn(raw: str | None, expected: str | None) -> None:
    assert normalize_inn(raw) == expected
