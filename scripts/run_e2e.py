"""End-to-end прогон: PDF → docket → reconcile → Excel.

Использование:
    python scripts/run_e2e.py --scenario exact_match --out output/
    python scripts/run_e2e.py --all --out output/

Требует запущенного Ollama (см. .env).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

from supplier_bonus.extraction.docket_adapter import extract_terms
from supplier_bonus.reconciliation.engine import MatchConfig, reconcile
from supplier_bonus.reporting.excel import export_to_excel
from supplier_bonus.reporting.json_export import result_to_json

FIXTURES = Path("data/examples")


def load_scenarios() -> list[dict]:
    return json.loads((FIXTURES / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]


def process_scenario(
    fx: dict,
    out_dir: Path,
    tolerance: float,
) -> dict:
    """Обрабатывает один сценарий. Возвращает summary."""
    pdf = FIXTURES / "contracts" / f"{fx['contract_id']}.pdf"
    csv = FIXTURES / "actuals" / f"{fx['contract_id']}_actual.csv"

    print(f"[{fx['contract_id']}] scenario={fx['scenario']}")
    print(f"  PDF:  {pdf}")
    print(f"  CSV:  {csv}")

    terms = extract_terms(pdf)
    if not terms:
        print(f"  ! извлечение не дало результатов")
        return {"scenario": fx["scenario"], "rows": 0, "error": "no terms"}

    t = terms[0]
    print(f"  извлечено: supplier={t.supplier_name}, period={t.period}")

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

    cfg = MatchConfig(amount_tolerance=tolerance)
    result = reconcile(contracts, actuals, config=cfg)

    # Сохраняем артефакты
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = fx["contract_id"]
    export_to_excel(result, out_dir / f"{stem}.xlsx")
    (out_dir / f"{stem}.json").write_text(result_to_json(result), encoding="utf-8")

    s = result.summary
    summary = {
        "contract_id": fx["contract_id"],
        "scenario": fx["scenario"],
        "matched_within_tolerance": s.matched_within_tolerance,
        "amount_mismatch": s.amount_mismatch,
        "missing_in_actuals": s.missing_in_actuals,
        "missing_in_contract": s.missing_in_contract,
        "rows": len(result.rows),
    }
    print(
        f"  результат: matched={s.matched_within_tolerance}, "
        f"mismatch={s.amount_mismatch}, "
        f"missing_actuals={s.missing_in_actuals}, "
        f"missing_contract={s.missing_in_contract}"
    )
    print(f"  артефакты: {out_dir / stem}.xlsx, {out_dir / stem}.json")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(prog="run_e2e")
    parser.add_argument("--scenario", help="Только один сценарий")
    parser.add_argument("--all", action="store_true", help="Все 20 сценариев")
    parser.add_argument("--out", default="output", type=Path)
    parser.add_argument("--tolerance", type=float, default=1.0)
    args = parser.parse_args()

    scenarios = load_scenarios()
    if args.scenario:
        scenarios = [s for s in scenarios if s["scenario"] == args.scenario]
        if not scenarios:
            print(f"Сценарий не найден: {args.scenario}", file=sys.stderr)
            return 2

    summaries = []
    for fx in scenarios:
        try:
            summary = process_scenario(fx, args.out, args.tolerance)
            summaries.append(summary)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! ошибка: {exc}", file=sys.stderr)
            summaries.append({"contract_id": fx["contract_id"], "error": str(exc)})

    print(f"\nОбработано: {len(summaries)}")
    (args.out / "summary.json").parent.mkdir(parents=True, exist_ok=True)
    (args.out / "summary.json").write_text(
        json.dumps(summaries, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Сводка: {args.out / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
