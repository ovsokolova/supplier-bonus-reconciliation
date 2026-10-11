# ADR-001: docket-idp как базовый слой извлечения

**Статус**: принято

**Контекст**: нужно извлекать структурированные условия
из PDF-договоров, сканов и Excel; каждое поле должно быть
прослеживаемым до источника для ручной проверки.

**Решение**: принять docket-idp как базовый слой извлечения
документов и построить на нём специализированную
Pydantic-схему для бонусных условий.

**Обоснование**:

- ссылки на источник по каждому полю (страница, фрагмент,
  bounding box) удовлетворяют требованиям аудита;
- поддержка нескольких OCR-бэкендов
  (Tesseract / PaddleOCR) и vision-откат;
- программная валидация направляет непрошедшие поля
  в needs_review, а не пропускает молча;
- нет привязки к конкретному поставщику LLM.

## Проверка перед реализацией

- [ ] Проверить актуальность docket-idp на PyPI:
      pip index versions docket-idp
- [ ] Проверить дату последнего коммита на GitHub
- [ ] Проверить наличие русскоязычных моделей OCR
- [ ] Если библиотека не поддерживается — переключиться на:
      - unstructured (парсинг PDF/DOCX)
      - marker (PDF → Markdown с сохранением структуры)
      - docling (IBM, PDF/DOCX/PPTX, активно развивается)

**Последствия**:

- плюсы: прослеживаемость источников и очередь проверки;
- минусы: зависимость от docket-idp; при заброшенности
  библиотеки — переход на unstructured / marker / docling;
- нейтрально: дополнительная настройка Tesseract и LLM.

**Альтернативы**:

- собственный OCR + LLM: ссылки и валидацию
  пришлось бы делать с нуля;
- коммерческие IDP-сервисы: стоимость и требования
  к размещению данных неприемлемы для PoC.
## Интеграция

Используем публичный API docket 0.5.0.

### Схема извлечения

- `SchemaSpec(schema_id, model=BonusTerms, description, version,
  display_name, status, cited_fields)` — регистрирует схему;
- `register_schema(spec, replace_existing=False)` — идемпотентная
  регистрация;
- `cited_fields` перечисляет поля, для которых docket обязан
  вернуть цитату (страница + quote). Валидатор проверяет,
  что цитата действительно есть на указанной странице.

### Обработка документа

- `process_document(source, options, on_stage=None) -> DocumentResult`;
- `ProcessOptions(ocr=OcrOptions(...), schema_model=BonusTerms,
  classify=False, include_layout=False, escalate=True,
  review=ReviewOptions(...), llm=OllamaBackend(...))`;
- `on_stage(stage, payload)` — хуки acquire, classify,
  extract, validate для логирования.

### OCR-цепочка

- `OcrOptions(backend="tesseract", fallbacks=["paddleocr"],
  languages=["ru","en"], min_confidence=0.75, use_pdf_text=True,
  dpi=300, device="cpu")`;
- при провале валидации docket сам перечитывает документ
  vision-моделью (escalate=True).

### LLM

- `OllamaBackend(host, text_model, vision_model, think)` —
  локальный инференс (см. ADR-003);
- `OpenAICompatibleBackend(base_url, api_key, ...)` — только
  по согласованию с ИБ.

### Результат

- `DocumentResult.extracted` — dict;
- `DocumentResult.document` — типизированная схема
  (BonusTerms), если она зарегистрирована;
- `DocumentResult.field_sources: dict[str, SourceLocation]` —
  источник для каждого поля;
- `DocumentResult.highlights(page=None) -> list[(field, source,
  region)]` — тройки для отрисовки боксов поверх PDF;
- `DocumentResult.needs_review: bool` и
  `review_reasons: list[str]` — очередь проверки.

### Прослеживаемость

- LLM возвращает `field_locations: dict[str, Citation]`
  (page + quote);
- pipeline резолвит цитату в `SourceLocation` с bbox,
  confidence и status (verified | fuzzy | conflicting |
  unlocated);
- `Citation` — только page и quote, никакой геометрии от LLM;
- bbox и word_ids берутся из word boxes страницы.

### Дополнительно

- `verify(document, text, ...)` — валидирует внешне
  сгенерированный документ против исходного текста;
- `corroborate(result, purchase_order=..., transactions=...)` —
  подтверждает поля по PO или банковским транзакциям;
- `DocumentResult.complete` — все страницы дали текст;
- `DocumentResult.is_valid` — итог валидации.
