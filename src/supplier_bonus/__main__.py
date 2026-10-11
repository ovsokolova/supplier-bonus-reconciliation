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

    terms = extract_terms(source)
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

    get_settings(ensure_dirs=True)

    contracts = pd.read_csv(args.contracts)
    actuals = pd.read_csv(args.actuals)
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
    p_reconcile.set_defaults(func=_cmd_reconcile)

    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
