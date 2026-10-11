# Контракт API (API Contract)

На этапе PoC основные вызовы происходят внутри Streamlit;
ниже определены интерфейсы между ключевыми модулями.

## POST /extract/terms

**Описание**: извлечение бонусных условий из загруженных
договоров и Excel-файлов.

**Запрос**:

```json
{
  "files": ["contract_01.pdf", "appendix_a.xlsx"],
  "document_type": "bonus_agreement",
  "language": "ru"
}
```

**Ответ**:

```json
{
  "status": "succeeded | needs_review | failed",
  "terms": [
    {
      "supplier_name": "ООО «Пример»",
      "bonus_type": "monetary",
      "base_metric": "purchase_volume",
      "tiers": [
        {"threshold": 1000000, "rate": 0.02},
        {"threshold": 5000000, "rate": 0.035}
      ],
      "period": "2026-Q1",
      "currency": "RUB",
      "field_sources": {
        "tiers": {
          "page": 3,
          "quote": "при объеме от 1 000 000 руб. — 2%"
        }
      }
    }
  ],
  "review_reasons": []
}
```

## POST /reconcile

**Описание**: сопоставление извлечённых условий
с фактическими данными.

**Запрос**:

```json
{
  "terms": ["..."],
  "actuals": [
    {
      "supplier_name": "ООО «Пример»",
      "period": "2026-Q1",
      "purchase_volume": 3200000
    }
  ],
  "amount_tolerance": 1.0,
  "fuzzy_threshold": 90
}
```

**Ответ**:

```json
{
  "summary": {
    "matched": 5,
    "matched_fuzzy": 1,
    "amount_mismatch": 2,
    "missing_in_actuals": 1,
    "needs_review": 0
  },
  "rows": [
    {
      "supplier_name": "...",
      "period": "...",
      "expected": 64000,
      "actual": 64000,
      "status": "matched"
    },
    {
      "supplier_name": "...",
      "period": "...",
      "expected": 175000,
      "actual": 160000,
      "status": "amount_mismatch",
      "diff": 15000
    },
    {
      "supplier_name": "...",
      "supplier_name_raw": "...",
      "similarity": 94,
      "status": "matched_fuzzy"
    }
  ]
}
```

## POST /report/export

**Описание**: экспорт отчёта о расхождениях в Excel.

**Запрос**:

```json
{
  "reconciliation_result": {"...": "..."},
  "format": "xlsx",
  "sheets": [
    "Список сверки",
    "Сводка сверки",
    "Требует обработки"
  ]
}
```

**Ответ**: поток двоичного файла xlsx.

## POST /claim/draft

**Описание**: формирование черновика претензионного письма.

**Запрос**:

```json
{
  "supplier_name": "ООО «Пример»",
  "period": "2026-Q1",
  "discrepancies": ["..."],
  "contract_reference": "Приложение №5, п.3.2"
}
```

**Ответ**:

```json
{
  "draft_text": "Уважаемый... Согласно Приложению №5...",
  "disclaimer": "ЧЕРНОВИК — требует юридической проверки"
}
```