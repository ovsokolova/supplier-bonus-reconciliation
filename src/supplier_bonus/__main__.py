"""CLI для supplier_bonus."""

from __future__ import annotations

import argparse
import sys


def main() -> int:
    parser = argparse.ArgumentParser(prog="supplier_bonus")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_extract = sub.add_parser("extract", help="Извлечь условия из PDF")
    p_extract.add_argument("source", help="Путь к PDF/Excel")

    p_reconcile = sub.add_parser("reconcile", help="Сверить договор и ERP")
    p_reconcile.add_argument("contracts", help="CSV с договорными условиями")
    p_reconcile.add_argument("actuals", help="CSV с фактическими данными")

    args = parser.parse_args()
    print(f"cmd={args.cmd}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
