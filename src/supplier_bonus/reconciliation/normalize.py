"""Нормализация наименований поставщиков и номенклатуры.

Приводит ключи к единому виду, чтобы «ООО «Пример»» и «Пример»
давали одинаковый ключ. Исходное значение сохраняется в *_raw.
"""

from __future__ import annotations

import re
import unicodedata

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

_JUNK_CHARS = re.compile(r"[\"'«»„“”‘’`.,;:!?()\[\]{}<>|/\\]+")
_MULTISPACE = re.compile(r"\s+")


def _strip_diacritics(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def normalize_name(name: str) -> str:
    """Приводит наименование к единому виду для сопоставления."""
    if not name:
        return ""
    s = name.strip().lower().replace("ё", "е")
    s = _strip_diacritics(s)
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
