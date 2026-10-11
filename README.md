# Supplier Bonus Reconciliation

Автоматическая сверка взаиморасчётов и бонусов поставщиков.

- Спецификация: openspec/changes/supplier-bonus-reconciliation/
- Предложение: proposal.md
- Проектирование: design.md
- Задачи: tasks.md

## Установка

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev,extraction,llm]"
```

## Запуск UI

```bash
streamlit run src/supplier_bonus/ui/app.py
```

## Тесты

```bash
pytest
```