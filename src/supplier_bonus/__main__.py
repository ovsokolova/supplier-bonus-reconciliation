"""CLI для supplier_bonus."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from supplier_bonus.config import get_settings

logger = logging.getLogger(__name__)


def _cmd_extract(args: argparse.Namespace) -> int:
    """Извлекает бонусные условия из документа."""
    from supplier_bonus.extraction.docket_adapter import extract_terms

    get_settings(ensure_dirs=True)
    source = Path(args.source)
    if not source.exists():
        print(f"Файл не найден: {source}", file=sys.stderr)
        return 2

    try:
        terms = extract_terms(source)
    except Exception as exc:  # noqa: BLE001
        print(f"Ошибка извлечения: {exc}", file=sys.stderr)
        logger.exception("extract failed")
        return 3

    if not terms:
        print("Извлечение не дало результатов.", file=sys.stderr)
        return 1

    payload = [t.model_dump(mode="json") for t in terms]
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def _cmd_reconcile(args: argparse.Namespace) -> int:
    """Сверяет договорные условия с фактическими данными."""
    import pandas as pd

    from supplier_bonus.reconciliation.engine import MatchConfig, reconcile
    from supplier_bonus.reporting.excel import export_to_excel

    get_settings(ensure_dirs=True)

    contracts_path = Path(args.contracts)
    actuals_path = Path(args.actuals)
    if not contracts_path.exists():
        print(f"Файл не найден: {contracts_path}", file=sys.stderr)
        return 2
    if not actuals_path.exists():
        print(f"Файл не найден: {actuals_path}", file=sys.stderr)
        return 2

    try:
        contracts = pd.read_csv(contracts_path, dtype={"inn": str})
        actuals = pd.read_csv(actuals_path, dtype={"inn": str})
        contracts = contracts.fillna({"inn": ""})
        actuals = actuals.fillna({"inn": ""})
    except Exception as exc:  # noqa: BLE001
        print(f"Ошибка чтения CSV: {exc}", file=sys.stderr)
        return 3

    cfg = MatchConfig(
        amount_tolerance=args.tolerance,
        fuzzy_threshold=args.fuzzy_threshold,
    )
    result = reconcile(contracts, actuals, config=cfg)
    s = result.summary

    print(
        "Сверка завершена:\n"
        f"  matched={s.matched}\n"
        f"  matched_by_inn={s.matched_by_inn}\n"
        f"  matched_fuzzy={s.matched_fuzzy}\n"
        f"  matched_within_tolerance={s.matched_within_tolerance}\n"
        f"  amount_mismatch={s.amount_mismatch}\n"
        f"  missing_in_actuals={s.missing_in_actuals}\n"
        f"  missing_in_contract={s.missing_in_contract}\n"
        f"  period_offset={s.period_offset}"
    )

    if args.out:
        out = export_to_excel(result, args.out)
        print(f"Отчёт: {out}")

    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="supplier_bonus")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_extract = sub.add_parser("extract", help="Извлечь условия из PDF/Excel")
    p_extract.add_argument("source", help="Путь к PDF/Excel")
    p_extract.set_defaults(func=_cmd_extract)

    p_reconcile = sub.add_parser("reconcile", help="Сверить договор и ERP")
    p_reconcile.add_argument("contracts", help="CSV с договорными условиями")
    p_reconcile.add_argument("actuals", help="CSV с фактическими данными")
    p_reconcile.add_argument("--tolerance", type=float, default=1.0)
    p_reconcile.add_argument("--fuzzy-threshold", type=int, default=90)
    p_reconcile.add_argument("--out", help="Путь для Excel-отчёта")
    p_reconcile.set_defaults(func=_cmd_reconcile)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
