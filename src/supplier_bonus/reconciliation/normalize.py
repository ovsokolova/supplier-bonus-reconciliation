"""Нормализация наименований поставщиков и номенклатуры.

Приводит ключи к единому виду, чтобы «ООО «Пример»» и «Пример»
давали одинаковый ключ. Исходное значение сохраняется в *_raw.
"""

from __future__ import annotations

import re

_OPF_PATTERNS = (
    r"\bооо\b",
    r"\bоао\b",
    r"\bзао\b",
    r"\bпао\b",
    r"\bао\b",
    r"\bип\b",
    r"\bнко\b",
    r"\bгку\b",
    r"\bмуп\b",
    r"\bгуп\b",
    r"\bфгуп\b",
)

# Мусорные символы: кавычки, точки, запятые, скобки, дефис.
# Дефис заменяем на пробел, чтобы «Пример-Трейд» → «пример трейд».
_JUNK_CHARS = re.compile(r"[\"'«»„“”‘’`.,;:!?()\[\]{}<>|/\\-]+")
_MULTISPACE = re.compile(r"\s+")


def normalize_name(name: str) -> str:
    """Приводит наименование к единому виду для сопоставления.

    Шаги:
      1. Приведение к нижнему регистру.
      2. Замена «ё» на «е».
      3. Удаление ОПФ как отдельных слов.
      4. Удаление кавычек, точек, запятых, скобок, дефисов.
      5. Схлопывание пробелов.

    Кириллица не нормализуется через NFKD, потому что это ломает
    «й» (становится «и») и «ё». Для латиницы с диакритикой
    нормализация не критична в контексте PoC.
    """
    if not name:
        return ""
    s = name.strip().lower().replace("ё", "е")
    for pattern in _OPF_PATTERNS:
        s = re.sub(pattern, " ", s)
    s = _JUNK_CHARS.sub(" ", s)
    s = _MULTISPACE.sub(" ", s).strip()
    return s


def normalize_inn(inn: str | None) -> str | None:
    """Оставляет только цифры в ИНН. None, если длина не 10 и не 12."""
    if inn is None:
        return None
    digits = re.sub(r"\D", "", str(inn))
    if len(digits) not in (10, 12):
        return None
    return digits
