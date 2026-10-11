# Задачи (Tasks): план внедрения

Легенда: [ ] todo · [~] in progress · [x] done · [!] blocked
Приоритеты: P0 — критично для PoC · P1 — нужно для демо ·
P2 — желательно · P3 — после PoC

## 0. Bootstrap (P0)

- [ ] 0.1 pyproject.toml, .env.example, README.md
- [ ] 0.2 Структура: src/supplier_bonus/, tests/, data/examples/
- [x] 0.3 .gitignore (уже есть), pre-commit
- [x] 0.4 .github/workflows/ci.yml (lint + pytest)
- [ ] 0.5 Проверить зрелость docket-idp (см. ADR-001)

## 1. Извлечение (P0)

- [ ] 1.1 Pydantic-схема: BonusTerms, Tier, FieldSource, Inn
- [ ] 1.2 docket-idp: интеграция process_document
- [ ] 1.3 Tesseract + PaddleOCR fallback (см. NFR-1.7)
- [ ] 1.4 Ollama: qwen2.5:7b-instruct локально
- [ ] 1.5 Excel: обнаружение заголовков + подтверждение
- [ ] 1.6 needs_review очередь
- [ ] 1.7 Логи без содержимого

## 2. Сверка (P0)

- [ ] 2.1 Outer join по ИНН с fallback на наименование
- [ ] 2.2 Нормализация ключей + поля *_raw
- [ ] 2.3 rapidfuzz (token_sort_ratio + WRatio), порог 90
- [ ] 2.4 Допуск AMOUNT_TOLERANCE через конфиг (NFR-2.4)
- [ ] 2.5 Статусы: matched, matched_by_inn, matched_fuzzy, amount_mismatch, missing_*
- [ ] 2.6 Обработка множественных кандидатов
- [ ] 2.7 Сводная статистика

## 3. Отчётность (P1)

- [ ] 3.1 Excel: «Список сверки», «Сводка сверки»,
      «Требует обработки»
- [ ] 3.2 Черновик претензии с disclaimer
- [ ] 3.3 Экспорт в JSON (ReportJSON)

## 4. UI (P1)

- [ ] 4.1 Streamlit: загрузка PDF/Excel
- [ ] 4.2 Отображение извлечения + ссылки на источник
- [ ] 4.3 Дашборд: KPI + таблица расхождений

## 5. Тестовые данные (P0)

- [ ] 5.1 Генератор синтетических фикстур (см. ADR-004)
- [ ] 5.2 20 синтетических договоров в data/examples/
- [ ] 5.3 10 сценариев расхождений в data/examples/
- [ ] 5.4 Подключение реальных обезличенных данных
      через TEST_DATA_PATH

## 6. Валидация (P2)

- [ ] 6.1 Точность извлечения ≥ 85 %
- [ ] 6.2 Выявляемость расхождений 100 %
- [ ] 6.3 Время обработки ≤ 3 минут (GPU)
- [ ] 6.4 Ложные missing_in_actuals ≤ 5 %
      (≤1 % при ИНН)
- [ ] 6.5 WER OCR на русских сканах ≤ 15 % (NFR-1.7)

## 7. После PoC (P3)

- [ ] 7.1 Миграция Streamlit → FastAPI + React
- [ ] 7.2 Интеграция с 1С/ERP
- [ ] 7.3 Мультипользовательский режим