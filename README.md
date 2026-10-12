# Supplier Bonus Reconciliation

Автоматическая сверка взаиморасчётов и бонусов поставщиков.

## Что делает

1. Извлекает бонусные условия из PDF-договоров (OCR + LLM через `docket-idp`).
2. Сверяет их с фактическими данными ERP (CSV-выгрузка).
3. Помечает расхождения: `amount_mismatch`, `missing_in_*`, `matched_fuzzy`.
4. Экспортирует отчёт в Excel (три листа).
5. Формирует черновик претензионного письма для поставщика.

## Стек

- Python 3.11+
- Pydantic v2
- pandas + rapidfuzz
- docket-idp + Ollama
- Streamlit
- openpyxl

## Быстрый старт

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev,extraction,llm]"

python scripts/generate_fixtures.py --out data/examples

streamlit run src/supplier_bonus/ui/app.py
```

## CLI

```bash
python -m supplier_bonus extract data/examples/contracts/contract_01.pdf
python -m supplier_bonus reconcile contracts.csv actuals.csv --out report.xlsx
```

## Тесты

```bash
pytest tests -q --no-cov
```

**98 тестов, 79 % покрытия.** Ядра (`engine`, `normalize`, `schemas`, `reporting`, `config`) > 90 %.

## Структура

```
src/supplier_bonus/
├── schemas.py
├── config.py
├── extraction/
│   └── docket_adapter.py
├── reconciliation/
│   ├── normalize.py
│   └── engine.py
├── reporting/
│   ├── excel.py
│   └── claim.py
└── ui/
    └── app.py
```

## Документация

- Спецификация: `openspec/changes/supplier-bonus-reconciliation/`
- Отчёт о готовности PoC: `docs/POC_REPORT.md`
- Сценарий демонстрации: `docs/DEMO.md`

## Что не входит в PoC

- Интеграция с 1С/ERP в реальном времени.
- Отправка претензий с юридической силой.
- Мультипользовательский режим и роли.
- Подсветка источника в PDF.
