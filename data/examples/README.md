# Синтетические фикстуры

Сгенерировано `scripts/generate_fixtures.py`. Не редактировать вручную.

## Структура

- `contracts/contract_NN.pdf` — договоры с бонусными условиями.
- `actuals/contract_NN_actual.csv` — фактические данные ERP.
- `scenarios.json` — ожидаемые результаты сверки для интеграционных тестов.
- `suppliers.csv` — справочник поставщиков.

## Сценарии

| Сценарий | Что проверяет |
|---|---|
| exact_match | matched_by_inn + matched_within_tolerance |
| amount_mismatch | amount_mismatch |
| missing_in_actuals | missing_in_actuals |
| missing_in_contract | missing_in_contract |
| matched_fuzzy | matched_fuzzy (Пример / Пример-Трейд) |
| matched_no_inn | matched без ИНН |
| tiered_3 | 3 ступени в PDF |
| goods_bonus | bonus_type = goods |
| tax_variants | tax_included True/False |
| period_offset | смещение периода |

## Использование

В интеграционном тесте:
1. Загрузить PDF через `docket_adapter.extract_terms`.
2. Загрузить CSV через pandas.
3. Вызвать `reconcile(contracts, actuals)`.
4. Сравнить `summary` с ожидаемым из `scenarios.json`.
