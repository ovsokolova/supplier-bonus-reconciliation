# OpenSpec: Автоматическая сверка бонусов поставщиков

## Структура пакета

```
openspec/
├── proposal.md
├── design.md
├── api-contract.md
├── tasks.md
├── specs/
│   ├── 01-extraction.md
│   ├── 02-reconciliation.md
│   └── 03-reporting.md
├── adr/
│   ├── ADR-001-docket-idp.md
│   ├── ADR-002-pandas-fuzzy.md
│   └── ADR-003-local-llm.md
└── assets/
```

## Ключевые решения

- Прослеживаемость: ссылка на источник для каждого
  извлечённого поля.
- Нечёткое сопоставление: нормализация ключей + rapidfuzz
  (порог 90) для снижения ложных missing_in_actuals.
- Конфиденциальность: LLM только локально (Ollama);
  внешние API — по согласованию с ИБ.
- Отчётность: Excel с листами «Список сверки»,
  «Сводка сверки», «Требует обработки».

## Порядок работы

1. proposal.md — проблема и границы PoC.
2. specs/ — требования по каждой возможности.
3. design.md и ADR — технические решения.
4. api-contract.md — интерфейсы модулей.
5. tasks.md — план внедрения.

## Диаграмма архитектуры

Основная схема — в design.md (Mermaid).
Если Mermaid недоступен, используйте:
- изображение assets/architecture.png
  (экспорт с mermaid.live);
- маркированный список потоков данных:
  1. Ввод: Договор (PDF/Excel).
  2. OCR + LLM (Ollama, локально).
  3. Структурированные условия.
  4. Нормализация + rapidfuzz.
  5. Сверка: pandas outer join (ERP CSV).
  6. Streamlit → Excel-отчёт → претензия.