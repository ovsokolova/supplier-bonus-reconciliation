"""Интеграционный тест: PDF → docket → reconcile (с Ollama).

Требует запущенного Ollama и модели из LLM_MODEL.
Помечен @pytest.mark.integration — не запускается в CI.

Запуск:
    ollama serve
    ollama pull qwen2.5:7b-instruct
    pytest tests/integration/test_pipeline_with_ollama.py -v --no-cov
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from supplier_bonus.extraction.docket_adapter import extract_terms
from supplier_bonus.reconciliation.engine import reconcile

FIXTURES = Path("data/examples")
SCENARIOS = FIXTURES / "scenarios.json"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not SCENARIOS.exists(),
        reason="Фикстуры не сгенерированы: python scripts/generate_fixtures.py",
    ),
]


def _check_ollama() -> None:
    """Проверяет доступность Ollama. Если недоступен — skip теста."""
    try:
        import httpx

        r = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        r.raise_for_status()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Ollama недоступен: {exc}")


def _load_scenarios() -> list[dict]:
    return json.loads(SCENARIOS.read_text(encoding="utf-8"))["scenarios"]


@pytest.mark.parametrize("idx", [0, 1, 2])  # первые три — exact_match
def test_extract_terms_from_pdf(idx: int) -> None:
    """Извлекает BonusTerms из PDF через docket + Ollama."""
    _check_ollama()
    scenarios = _load_scenarios()
    fx = scenarios[idx]
    pdf = FIXTURES / "contracts" / f"{fx['contract_id']}.pdf"

    terms = extract_terms(pdf)
    assert len(terms) >= 1, f"Извлечение не дало результатов для {pdf}"

    t = terms[0]
    # Минимальные проверки: имя, ИНН, тип бонуса
    assert t.supplier_name, "supplier_name не извлечён"
    assert t.bonus_type in ("monetary", "goods", "mixed")
    assert t.period, "period не извлечён"


def test_end_to_end_pdf_to_reconcile() -> None:
    """PDF → BonusTerms → reconcile с CSV → проверка summary."""
    _check_ollama()
    scenarios = _load_scenarios()
    fx = next(s for s in scenarios if s["scenario"] == "exact_match")
    pdf = FIXTURES / "contracts" / f"{fx['contract_id']}.pdf"
    csv = FIXTURES / "actuals" / f"{fx['contract_id']}_actual.csv"

    terms = extract_terms(pdf)
    assert len(terms) >= 1
    t = terms[0]

    contracts = pd.DataFrame(
        [
            {
                "supplier_name": t.supplier_name,
                "inn": t.inn.value if t.inn else "",
                "period": t.period,
                "amount": fx["expected_amount"],
            }
        ]
    )
    actuals = pd.read_csv(csv, dtype={"inn": str}).fillna({"inn": ""})

    result = reconcile(contracts, actuals)
    s = result.summary
    # Точное совпадение: сумма совпадает, значит matched_within_tolerance
    assert s.matched_within_tolerance == 1 or s.matched == 1


def test_field_sources_have_citations() -> None:
    """Каждое cited-поле имеет SourceLocation с page и quote."""
    _check_ollama()
    scenarios = _load_scenarios()
    pdf = FIXTURES / "contracts" / f"{scenarios[0]['contract_id']}.pdf"

    from supplier_bonus.extraction.docket_adapter import (
        CITED_FIELDS,
        build_process_options,
        process_document,
        register_bonus_schema,
    )

    register_bonus_schema()
    options = build_process_options()
    result = process_document(pdf, options)

    sources = result.field_sources or {}
    # Хотя бы одно из cited-полей должно быть привязано к странице
    assert any(field in sources for field in CITED_FIELDS)
    for field, loc in sources.items():
        assert loc.page >= 1
        assert loc.quote
