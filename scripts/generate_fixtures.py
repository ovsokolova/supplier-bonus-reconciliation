"""Генератор синтетических фикстур для PoC.

Создаёт PDF-договоры с бонусными условиями и CSV с фактическими
данными ERP. Покрывает 10 сценариев сверки.

Запуск:
    python scripts/generate_fixtures.py --out data/examples
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import asdict, dataclass, field
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

random.seed(42)  # воспроизводимость

# --- Кириллица в PDF через DejaVuSans ---
def _register_cyrillic_font() -> str:
    """Регистрирует шрифт с кириллицей. Возвращает имя шрифта.

    Пытается найти DejaVuSans в стандартных местах. Если не найдёт —
    падает с понятной ошибкой.
    """
    candidates = [
        Path("C:/Windows/Fonts/DejaVuSans.ttf"),
        Path("C:/Windows/Fonts/Arial.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/Library/Fonts/Arial Unicode.ttf"),
    ]
    for path in candidates:
        if path.exists():
            pdfmetrics.registerFont(TTFont("Cyr", str(path)))
            return "Cyr"
    raise FileNotFoundError(
        "Не найден шрифт с кириллицей. Установите DejaVuSans или Arial."
    )


@dataclass
class Supplier:
    name: str
    inn: str | None
    kpp: str | None = None


@dataclass
class BonusTier:
    threshold: float
    rate: float


@dataclass
class ContractFixture:
    contract_id: str
    supplier: Supplier
    bonus_type: str  # monetary | goods | mixed
    base_metric: str
    tiers: list[BonusTier]
    period: str
    currency: str = "RUB"
    tax_included: bool = True
    scenario: str = "exact_match"
    # для сверки
    expected_amount: float = 0.0
    actual_amount: float = 0.0
    actual_name: str | None = None
    actual_period: str | None = None
    extra_actuals: list[dict] = field(default_factory=list)


# ============================================================
# Справочник поставщиков
# ============================================================
SUPPLIERS: list[Supplier] = [
    Supplier("ООО «Ромашка»", "7701234567", "770101001"),
    Supplier("ООО «Василёк»", "7702345678", "770201001"),
    Supplier("АО «Подсолнух»", "7703456789", "770301001"),
    Supplier("ПАО «Ландыш»", "7704567890", "770401001"),
    Supplier("ООО «Незабудка»", "7705678901", "770501001"),
    Supplier("ООО «Одуванчик»", "7706789012", "770601001"),
    Supplier("ООО «Клевер»", "7707890123", "770701001"),
    Supplier("ООО «Мимоза»", "7708901234", "770801001"),
    Supplier("ИП Сидоров И.И.", "770901234512", None),
    Supplier("ООО «Лилия»", "7710123456", "771001001"),
]


# ============================================================
# Сценарии
# ============================================================
def build_scenarios() -> list[ContractFixture]:
    """Собирает 20 договоров по 10 сценариям."""
    fixtures: list[ContractFixture] = []
    s = SUPPLIERS

    def tier_set(n: int) -> list[BonusTier]:
        if n == 1:
            return [BonusTier(1_000_000, 0.02)]
        if n == 2:
            return [BonusTier(1_000_000, 0.02), BonusTier(5_000_000, 0.035)]
        return [
            BonusTier(500_000, 0.01),
            BonusTier(2_000_000, 0.025),
            BonusTier(5_000_000, 0.04),
        ]

    # 1. exact_match + matched_by_inn (3 шт.)
    for i in range(3):
        sup = s[i]
        fixtures.append(
            ContractFixture(
                contract_id=f"contract_{len(fixtures)+1:02d}",
                supplier=sup,
                bonus_type="monetary",
                base_metric="purchase_volume",
                tiers=tier_set(2),
                period="2026-Q1",
                scenario="exact_match",
                expected_amount=100_000.0,
                actual_amount=100_000.0,
            )
        )

    # 2. amount_mismatch (2 шт.)
    for i in range(2):
        sup = s[3 + i]
        fixtures.append(
            ContractFixture(
                contract_id=f"contract_{len(fixtures)+1:02d}",
                supplier=sup,
                bonus_type="monetary",
                base_metric="payment_amount",
                tiers=tier_set(1),
                period="2026-Q1",
                scenario="amount_mismatch",
                expected_amount=250_000.0,
                actual_amount=200_000.0,   # недоплата 50 000
            )
        )

    # 3. missing_in_actuals (2 шт.)
    for i in range(2):
        sup = s[5 + i]
        fixtures.append(
            ContractFixture(
                contract_id=f"contract_{len(fixtures)+1:02d}",
                supplier=sup,
                bonus_type="monetary",
                base_metric="purchase_volume",
                tiers=tier_set(2),
                period="2026-Q1",
                scenario="missing_in_actuals",
                expected_amount=75_000.0,
                actual_amount=0.0,  # строки не будет в actuals
            )
        )

    # 4. missing_in_contract (2 шт.)
    for i in range(2):
        sup = s[7 + i]
        fixtures.append(
            ContractFixture(
                contract_id=f"contract_{len(fixtures)+1:02d}",
                supplier=sup,
                bonus_type="monetary",
                base_metric="quantity",
                tiers=tier_set(1),
                period="2026-Q1",
                scenario="missing_in_contract",
                expected_amount=0.0,
                actual_amount=120_000.0,
                extra_actuals=[{
                    "supplier_name": sup.name,
                    "inn": sup.inn or "",
                    "period": "2026-Q1",
                    "amount": 120_000.0,
                }],
            )
        )

    # 5. matched_fuzzy (2 шт.)
    for i in range(2):
        sup = s[9]
        fixtures.append(
            ContractFixture(
                contract_id=f"contract_{len(fixtures)+1:02d}",
                supplier=sup,
                bonus_type="monetary",
                base_metric="purchase_volume",
                tiers=tier_set(1),
                period="2026-Q1",
                scenario="matched_fuzzy",
                expected_amount=90_000.0,
                actual_amount=90_000.0,
                actual_name=f"{sup.name}-Трейд",
            )
        )

    # 6. matched без ИНН (2 шт.)
    for i in range(2):
        sup = Supplier(name=f"ООО «Без_ИНН_{i+1}»", inn=None)
        fixtures.append(
            ContractFixture(
                contract_id=f"contract_{len(fixtures)+1:02d}",
                supplier=sup,
                bonus_type="monetary",
                base_metric="purchase_volume",
                tiers=tier_set(1),
                period="2026-Q2",
                scenario="matched_no_inn",
                expected_amount=40_000.0,
                actual_amount=40_000.0,
            )
        )

    # 7. ступенчатый (3 tier) (2 шт.)
    for i in range(2):
        sup = s[(i + 1) % len(s)]
        fixtures.append(
            ContractFixture(
                contract_id=f"contract_{len(fixtures)+1:02d}",
                supplier=sup,
                bonus_type="monetary",
                base_metric="purchase_volume",
                tiers=tier_set(3),
                period="2026-Q1",
                scenario="tiered_3",
                expected_amount=180_000.0,
                actual_amount=180_000.0,
            )
        )

    # 8. товарный бонус (2 шт.)
    for i in range(2):
        sup = s[(i + 3) % len(s)]
        fixtures.append(
            ContractFixture(
                contract_id=f"contract_{len(fixtures)+1:02d}",
                supplier=sup,
                bonus_type="goods",
                base_metric="quantity",
                tiers=tier_set(2),
                period="2026-Q1",
                scenario="goods_bonus",
                expected_amount=50_000.0,
                actual_amount=50_000.0,
            )
        )

    # 9. НДС (2 шт.)
    for i in range(2):
        sup = s[(i + 5) % len(s)]
        fixtures.append(
            ContractFixture(
                contract_id=f"contract_{len(fixtures)+1:02d}",
                supplier=sup,
                bonus_type="monetary",
                base_metric="payment_amount",
                tiers=tier_set(1),
                period="2026-Q1",
                tax_included=(i == 0),
                scenario="tax_variants",
                expected_amount=60_000.0,
                actual_amount=60_000.0,
            )
        )

    # 10. смещение периода (1 шт.)
    sup = s[0]
    fixtures.append(
        ContractFixture(
            contract_id=f"contract_{len(fixtures)+1:02d}",
            supplier=sup,
            bonus_type="monetary",
            base_metric="purchase_volume",
            tiers=tier_set(1),
            period="2026-Q1",
            scenario="period_offset",
            expected_amount=30_000.0,
            actual_amount=30_000.0,
            actual_period="2026-Q2",  # смещение
        )
    )

    return fixtures


# ============================================================
# PDF
# ============================================================
def write_pdf(fx: ContractFixture, out_path: Path, font: str) -> None:
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Договор {fx.contract_id}",
    )
    styles = getSampleStyleSheet()
    h1 = styles["Heading1"]
    h1.fontName = font
    body = styles["BodyText"]
    body.fontName = font
    body.fontSize = 10

    story: list[object] = []
    story.append(Paragraph(f"Приложение №5 к договору {fx.contract_id}", h1))
    story.append(Spacer(1, 6 * mm))
    story.append(Paragraph(f"Поставщик: {fx.supplier.name}", body))
    if fx.supplier.inn:
        story.append(Paragraph(f"ИНН: {fx.supplier.inn}", body))
        if fx.supplier.kpp:
            story.append(Paragraph(f"КПП: {fx.supplier.kpp}", body))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(f"Период: {fx.period}", body))
    story.append(Paragraph(f"Валюта: {fx.currency}", body))
    tax = "с НДС" if fx.tax_included else "без НДС"
    story.append(Paragraph(f"Суммы указаны: {tax}", body))
    story.append(Spacer(1, 4 * mm))

    btype = {"monetary": "денежный", "goods": "товарный", "mixed": "смешанный"}[fx.bonus_type]
    story.append(Paragraph(f"Тип бонуса: {btype}", body))
    story.append(Paragraph(f"База расчёта: {fx.base_metric}", body))
    story.append(Spacer(1, 4 * mm))

    story.append(Paragraph("Ступени бонуса:", body))
    data = [["Порог, руб.", "Ставка"]]
    for t in fx.tiers:
        data.append([f"{t.threshold:,.0f}".replace(",", " "), f"{t.rate:.2%}"])
    table = Table(data, colWidths=[60 * mm, 40 * mm])
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), font),
                ("BACKGROUND", (0, 0), (-1, 0), "#DDDDDD"),
                ("GRID", (0, 0), (-1, -1), 0.5, "#888888"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 6 * mm))
    story.append(
        Paragraph(
            "Бонус начисляется по итогам периода на основании данных "
            "о фактическом объёме закупок / сумме оплат.",
            body,
        )
    )

    doc.build(story)


# ============================================================
# CSV с фактическими данными
# ============================================================
ACTUAL_FIELDS = ["supplier_name", "inn", "period", "amount"]


def write_actual_csv(fx: ContractFixture, out_path: Path) -> None:
    rows: list[dict] = []

    if fx.scenario == "missing_in_actuals":
        # Ничего не пишем — только заголовок.
        pass
    elif fx.scenario == "missing_in_contract":
        rows.extend(fx.extra_actuals)
    else:
        if fx.actual_amount > 0:
            rows.append(
                {
                    "supplier_name": fx.actual_name or fx.supplier.name,
                    "inn": fx.supplier.inn or "",
                    "period": fx.actual_period or fx.period,
                    "amount": fx.actual_amount,
                }
            )

    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=ACTUAL_FIELDS)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


# ============================================================
# scenarios.json
# ============================================================
def write_scenarios(fixtures: list[ContractFixture], out_path: Path) -> None:
    payload = {
        "generated_by": "scripts/generate_fixtures.py",
        "seed": 42,
        "scenarios": [asdict(fx) for fx in fixtures],
    }
    out_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ============================================================
# README
# ============================================================
def write_readme(out_dir: Path) -> None:
    readme = """# Синтетические фикстуры

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
"""
    (out_dir / "README.md").write_text(readme, encoding="utf-8")


# ============================================================
# main
# ============================================================
def main() -> int:
    parser = argparse.ArgumentParser(prog="generate_fixtures")
    parser.add_argument("--out", default="data/examples", type=Path)
    args = parser.parse_args()

    out: Path = args.out
    contracts_dir = out / "contracts"
    actuals_dir = out / "actuals"
    contracts_dir.mkdir(parents=True, exist_ok=True)
    actuals_dir.mkdir(parents=True, exist_ok=True)

    font = _register_cyrillic_font()
    fixtures = build_scenarios()

    for fx in fixtures:
        pdf_path = contracts_dir / f"{fx.contract_id}.pdf"
        csv_path = actuals_dir / f"{fx.contract_id}_actual.csv"
        write_pdf(fx, pdf_path, font)
        write_actual_csv(fx, csv_path)

    write_scenarios(fixtures, out / "scenarios.json")
    write_readme(out)

    print(f"Создано договоров: {len(fixtures)}")
    print(f"Директория: {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())