"""Экспорт результатов сверки и черновиков претензий в JSON.

Формат стабилен: изменения в модели требуют бампа SCHEMA_VERSION.
Используется для интеграции с внешними системами (1С, ERP,
аналитические пайплайны) и для сохранения артефактов.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from supplier_bonus.reporting.claim import ClaimDraft
from supplier_bonus.schemas import ReconciliationResult

logger = logging.getLogger(__name__)

SCHEMA_VERSION = "1.0"


def result_to_dict(result: ReconciliationResult) -> dict[str, Any]:
    """Сериализует ReconciliationResult в словарь.

    Возвращает стабильную структуру:
      {
        "schema_version": "1.0",
        "summary": {...},
        "rows": [{...}],
        "amount_tolerance": float,
        "fuzzy_threshold": int,
      }
    """
    return {
        "schema_version": SCHEMA_VERSION,
        "summary": result.summary.model_dump(mode="json"),
        "rows": [row.model_dump(mode="json") for row in result.rows],
        "amount_tolerance": result.amount_tolerance,
        "fuzzy_threshold": result.fuzzy_threshold,
    }


def result_to_json(
    result: ReconciliationResult,
    *,
    indent: int | None = 2,
) -> str:
    """Сериализует ReconciliationResult в JSON-строку.

    ensure_ascii=False сохраняет кириллицу читаемой.
    """
    payload = result_to_dict(result)
    text = json.dumps(payload, ensure_ascii=False, indent=indent)
    logger.info(
        "Экспорт результата: %d строк, %d байт",
        len(result.rows),
        len(text.encode("utf-8")),
    )
    return text


def claim_to_dict(draft: ClaimDraft) -> dict[str, Any]:
    """Сериализует ClaimDraft в словарь."""
    return {
        "schema_version": SCHEMA_VERSION,
        "supplier_name": draft.supplier_name,
        "period": draft.period,
        "total_amount": draft.total_amount,
        "rows_count": draft.rows_count,
        "disclaimer": draft.disclaimer,
        "text": draft.text,
    }


def claim_to_json(
    draft: ClaimDraft,
    *,
    indent: int | None = 2,
) -> str:
    """Сериализует ClaimDraft в JSON-строку."""
    payload = claim_to_dict(draft)
    text = json.dumps(payload, ensure_ascii=False, indent=indent)
    logger.info(
        "Экспорт претензии: %s, %s, %d байт",
        draft.supplier_name,
        draft.period,
        len(text.encode("utf-8")),
    )
    return text
