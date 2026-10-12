# Отчёт о готовности PoC: Supplier Bonus Reconciliation

**Версия:** 0.1.0
**Дата:** 2026-10-12
**Статус:** PoC готов к демонстрации

## Цель

Автоматизировать сверку бонусов поставщиков: извлекать условия из PDF-договоров,
сверять с фактическими данными ERP, помечать расхождения, формировать отчёт
и черновик претензии.

## Реализовано

### 1. Извлечение (`extraction/docket_adapter.py`)

- `docket.process_document` с `SchemaSpec(cited_fields)`.
- Каждое поле сопровождается ссылкой на источник (страница, цитата).
- `OcrOptions(backend="tesseract", fallbacks=["paddleocr"])`.
- `OllamaBackend` для локального инференса.
- Покрытие: 92 % (с моками). Реальный OCR/LLM не тестирован в CI.

### 2. Сверка (`reconciliation/`)

- `normalize_name`: удаление ОПФ, кавычек, знаков; сохранение `й`, `ё`.
- `normalize_inn`: только цифры, длина 10/12.
- `engine.reconcile`: outer join по ИНН → имя; rapidfuzz (`token_sort` + `token_set`); настраиваемый допуск.
- 9 статусов: matched, matched_by_inn, matched_fuzzy, matched_within_tolerance, amount_mismatch, missing_in_actuals, missing_in_contract, period_offset, needs_review.
- Покрытие: 94 %.

### 3. Отчётность (`reporting/`)

- `excel.py`: три листа («Список сверки», «Сводка сверки», «Требует обработки»).
- `claim.py`: markdown-претензия с таблицей, итогом, требованием, disclaimer.
- Покрытие: 97 %.

### 4. UI (`ui/app.py`)

- Загрузка CSV + демо-фикстуры.
- KPI-карточки, таблица с подсветкой, фильтр по статусам.
- Экспорт в Excel.
- Секция «Черновик претензии».

### 5. Фикстуры (`scripts/generate_fixtures.py`)

- 20 PDF-договоров, 20 CSV, `scenarios.json`.
- 10 сценариев: exact_match, amount_mismatch, missing_in_*, matched_fuzzy,
  matched_no_inn, tiered_3, goods_bonus, tax_variants, period_offset.

## Метрики

| Метрика | Значение |
|---|---|
| Тестов | 98 |
| Покрытие | 79 % |
| Ядра > 90 % | engine, normalize, schemas, reporting, config |
| ruff | clean |
| mypy | clean |
| CI | зелёный |

## Не проверено

- Реальный OCR/LLM-пайплайн (нужен Ollama).
- Подсветка источника в PDF (требует конвертации BoundingBox).
- Валидация на реальных договорах.

## Следующие шаги

1. Интеграция с Ollama — end-to-end тест с PDF + LLM.
2. Валидация на 20+ реальных договорах.
3. Подсветка источника в UI.
4. Миграция Streamlit → FastAPI + React.
