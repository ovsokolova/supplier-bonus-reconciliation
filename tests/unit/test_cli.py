"""Тесты CLI (без запуска внешних процессов)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from supplier_bonus.__main__ import _cmd_extract, _cmd_reconcile, main


def _write_csv(path: Path, rows: list[dict]) -> None:
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False, encoding="utf-8")


def test_main_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main(["--help"])
    out = capsys.readouterr().out
    assert "extract" in out
    assert "reconcile" in out


def test_main_no_args_exits(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit):
        main([])


def test_cmd_reconcile_missing_contracts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = argparse.Namespace(
        contracts=str(tmp_path / "nonexistent.csv"),
        actuals=str(tmp_path / "actuals.csv"),
        tolerance=1.0,
        fuzzy_threshold=90,
        out=None,
    )
    _write_csv(
        tmp_path / "actuals.csv", [{"supplier_name": "X", "inn": "", "period": "Q1", "amount": 1.0}]
    )
    rc = _cmd_reconcile(args)
    err = capsys.readouterr().err
    assert rc == 2
    assert "не найден" in err.lower()


def test_cmd_reconcile_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    contracts = tmp_path / "contracts.csv"
    actuals = tmp_path / "actuals.csv"
    _write_csv(
        contracts,
        [{"supplier_name": "X", "inn": "7701234567", "period": "Q1", "amount": 100.0}],
    )
    _write_csv(
        actuals,
        [{"supplier_name": "X", "inn": "7701234567", "period": "Q1", "amount": 100.0}],
    )
    args = argparse.Namespace(
        contracts=str(contracts),
        actuals=str(actuals),
        tolerance=1.0,
        fuzzy_threshold=90,
        out=None,
    )
    rc = _cmd_reconcile(args)
    out = capsys.readouterr().out
    assert rc == 0
    assert "Сверка завершена" in out
    assert "matched_within_tolerance=1" in out


def test_cmd_reconcile_export_excel(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    contracts = tmp_path / "contracts.csv"
    actuals = tmp_path / "actuals.csv"
    out_xlsx = tmp_path / "report.xlsx"
    _write_csv(
        contracts,
        [{"supplier_name": "X", "inn": "", "period": "Q1", "amount": 100.0}],
    )
    _write_csv(
        actuals,
        [{"supplier_name": "X", "inn": "", "period": "Q1", "amount": 80.0}],
    )
    args = argparse.Namespace(
        contracts=str(contracts),
        actuals=str(actuals),
        tolerance=1.0,
        fuzzy_threshold=90,
        out=str(out_xlsx),
    )
    rc = _cmd_reconcile(args)
    out = capsys.readouterr().out
    assert rc == 0
    assert out_xlsx.exists()
    assert "Отчёт:" in out


def test_cmd_extract_missing_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    args = argparse.Namespace(source=str(tmp_path / "missing.pdf"))
    rc = _cmd_extract(args)
    err = capsys.readouterr().err
    assert rc == 2
    assert "не найден" in err.lower()


def test_cmd_extract_success(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """Мокаем extract_terms — возвращает два BonusTerms."""
    from supplier_bonus.schemas import (
        BaseMetric,
        BonusTerms,
        BonusType,
        Tier,
    )

    pdf = tmp_path / "contract.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    terms = [
        BonusTerms(
            supplier_name="ООО «Пример»",
            bonus_type=BonusType.MONETARY,
            base_metric=BaseMetric.PURCHASE_VOLUME,
            tiers=[Tier(threshold=1_000_000, rate=0.02)],
            period="2026-Q1",
        )
    ]

    with patch(
        "supplier_bonus.extraction.docket_adapter.extract_terms",
        return_value=terms,
    ):
        args = argparse.Namespace(source=str(pdf))
        rc = _cmd_extract(args)

    out = capsys.readouterr().out
    assert rc == 0
    payload = json.loads(out)
    assert len(payload) == 1
    assert payload[0]["supplier_name"] == "ООО «Пример»"


def test_cmd_extract_no_results(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pdf = tmp_path / "contract.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    with patch(
        "supplier_bonus.extraction.docket_adapter.extract_terms",
        return_value=[],
    ):
        args = argparse.Namespace(source=str(pdf))
        rc = _cmd_extract(args)

    err = capsys.readouterr().err
    assert rc == 1
    assert "не дало результатов" in err.lower()


def test_cmd_extract_exception(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pdf = tmp_path / "contract.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    with patch(
        "supplier_bonus.extraction.docket_adapter.extract_terms",
        side_effect=RuntimeError("LLM unavailable"),
    ):
        args = argparse.Namespace(source=str(pdf))
        rc = _cmd_extract(args)

    err = capsys.readouterr().err
    assert rc == 3
    assert "ошибка извлечения" in err.lower()
