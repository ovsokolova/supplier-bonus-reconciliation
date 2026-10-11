# update-all.ps1
# Запуск: pwsh -ExecutionPolicy Bypass -File .\update-all.ps1
# Из корня D:\downloads\AI\supplier-bonus-reconciliation

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

# --- Безопасная запись UTF-8 без BOM ---
function Write-Utf8NoBom {
    param(
        [Parameter(Mandatory)] [string] $Path,
        [Parameter()] [AllowEmptyString()] [string] $Content = ""
    )
    if ($null -eq $Content) { $Content = "" }
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $full = [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Path))
    [System.IO.File]::WriteAllText($full, $Content, $utf8NoBom)
    Write-Host "  + $Path" -ForegroundColor Cyan
}

$Src  = "src\supplier_bonus"
$Recon = "$Src\reconciliation"
$Tests = "tests\unit"
$Tasks = "openspec\changes\supplier-bonus-reconciliation\tasks.md"

# ============================================================
# 0. Диагностика
# ============================================================
Write-Host ""
Write-Host "=== Диагностика ===" -ForegroundColor Yellow
$hasEngine = Test-Path "$Recon\engine.py"
$hasNormalize = Test-Path "$Recon\normalize.py"
Write-Host "  engine.py:    $hasEngine"
Write-Host "  normalize.py: $hasNormalize"

# ============================================================
# 1. tasks.md → вернуть честные [ ]
# ============================================================
if (Test-Path $Tasks) {
    $t = Get-Content $Tasks -Raw -Encoding utf8
    $t = $t -replace '- \[x\] 2\.1 ', '- [ ] 2.1 '
    $t = $t -replace '- \[x\] 2\.2 ', '- [ ] 2.2 '
    $t = $t -replace '- \[x\] 2\.3 ', '- [ ] 2.3 '
    $t = $t -replace '- \[x\] 2\.5 ', '- [ ] 2.5 '
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText(
        [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $Tasks)),
        $t,
        $utf8NoBom
    )
    Write-Host "  ~ $Tasks (2.1–2.3, 2.5 → [ ])" -ForegroundColor Cyan
}

# ============================================================
# 2. normalize.py
# ============================================================
$normalize = @'
"""Нормализация наименований поставщиков и номенклатуры.

Приводит ключи к единому виду, чтобы «ООО «Пример»» и «Пример»
давали одинаковый ключ. Исходное значение сохраняется в *_raw.
"""

from __future__ import annotations

import re
import unicodedata

_OPF_PATTERNS = (
    r"\bооо\b",
    r"\bоао\b",
    r"\bзао\b",
    r"\bпао\b",
    r"\bао\b",
    r"\bип\b",
    r"\bнко\b",
    r"\bгку\b",
    r"\bмуп\b",
    r"\bгуп\b",
    r"\bфгуп\b",
)

_JUNK_CHARS = re.compile(r"[\"'«»„“”‘’`.,;:!?()\[\]{}<>|/\\]+")
_MULTISPACE = re.compile(r"\s+")


def _strip_diacritics(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in nfkd if not unicodedata.combining(ch))


def normalize_name(name: str) -> str:
    """Приводит наименование к единому виду для сопоставления."""
    if not name:
        return ""
    s = name.strip().lower().replace("ё", "е")
    s = _strip_diacritics(s)
    for pattern in _OPF_PATTERNS:
        s = re.sub(pattern, " ", s)
    s = _JUNK_CHARS.sub(" ", s)
    s = _MULTISPACE.sub(" ", s).strip()
    return s


def normalize_inn(inn: str | None) -> str | None:
    """Оставляет только цифры в ИНН. None, если длина не 10 и не 12."""
    if inn is None:
        return None
    digits = re.sub(r"\D", "", str(inn))
    if len(digits) not in (10, 12):
        return None
    return digits
'@
Write-Utf8NoBom "$Recon\normalize.py" $normalize

# ============================================================
# 3. engine.py
# ============================================================
$engine = @'
"""Движок сверки: outer join по ИНН с fallback на fuzzy-сопоставление."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import pandas as pd
from rapidfuzz import fuzz, process

from supplier_bonus.reconciliation.normalize import normalize_inn, normalize_name
from supplier_bonus.schemas import (
    MatchStatus,
    ReconciliationResult,
    ReconciliationRow,
    ReconciliationSummary,
)

logger = logging.getLogger(__name__)

_FUZZY_SCORERS: tuple[tuple[object, float], ...] = (
    (fuzz.token_sort_ratio, 1.0),
    (fuzz.WRatio, 1.0),
)


@dataclass(frozen=True)
class MatchConfig:
    amount_tolerance: float = 1.0
    fuzzy_threshold: int = 90
    period_offset_months: int = 1


def _score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    total_weight = sum(w for _, w in _FUZZY_SCORERS)
    total = sum(scorer(a, b) * w for scorer, w in _FUZZY_SCORERS)
    return total / total_weight


def _best_match(
    needle: str,
    haystack: list[str],
    threshold: int,
) -> tuple[str, float] | None:
    if not haystack or not needle:
        return None
    result = process.extractOne(
        needle,
        haystack,
        scorer=lambda s1, s2, **_: _score(s1, s2),
    )
    if result is None:
        return None
    match, score, _ = result
    if score < threshold:
        return None
    return match, score


def _join_key(row: pd.Series, name_field: str, inn_field: str) -> str:
    inn = normalize_inn(row.get(inn_field))
    if inn:
        return f"inn:{inn}"
    return f"name:{normalize_name(str(row.get(name_field, '')))}"


def reconcile(
    contracts: pd.DataFrame,
    actuals: pd.DataFrame,
    *,
    config: MatchConfig | None = None,
    name_field: str = "supplier_name",
    inn_field: str = "inn",
    period_field: str = "period",
    amount_field: str = "amount",
) -> ReconciliationResult:
    """Сопоставляет договорные условия с фактическими данными."""
    cfg = config or MatchConfig()

    if contracts.empty and actuals.empty:
        return ReconciliationResult(
            summary=ReconciliationSummary(),
            rows=[],
            amount_tolerance=cfg.amount_tolerance,
            fuzzy_threshold=cfg.fuzzy_threshold,
        )

    contracts = contracts.copy()
    actuals = actuals.copy()
    contracts["_key"] = contracts.apply(
        lambda r: _join_key(r, name_field, inn_field), axis=1
    )
    actuals["_key"] = actuals.apply(
        lambda r: _join_key(r, name_field, inn_field), axis=1
    )

    merged = contracts.merge(
        actuals,
        on=["_key", period_field],
        how="outer",
        suffixes=("_contract", "_actual"),
        indicator=True,
    )

    rows: list[ReconciliationRow] = []
    summary = ReconciliationSummary()

    for _, row in merged.iterrows():
        name_c = row.get(f"{name_field}_contract")
        name_a = row.get(f"{name_field}_actual")
        period = row.get(period_field)
        amount_c = row.get(f"{amount_field}_contract")
        amount_a = row.get(f"{amount_field}_actual")
        inn_c = normalize_inn(row.get(f"{inn_field}_contract"))
        inn_a = normalize_inn(row.get(f"{inn_field}_actual"))

        if pd.notna(name_c) and pd.notna(name_a):
            if inn_c and inn_a and inn_c == inn_a:
                status = MatchStatus.MATCHED_BY_INN
                summary.matched_by_inn += 1
            else:
                status = MatchStatus.MATCHED
                summary.matched += 1

            diff = None
            if pd.notna(amount_c) and pd.notna(amount_a):
                diff = float(amount_c) - float(amount_a)
                if abs(diff) <= cfg.amount_tolerance:
                    status = MatchStatus.MATCHED_WITHIN_TOLERANCE
                    summary.matched_within_tolerance += 1
                else:
                    status = MatchStatus.AMOUNT_MISMATCH
                    summary.amount_mismatch += 1

            rows.append(
                ReconciliationRow(
                    supplier_name=str(name_c),
                    period=str(period),
                    expected=float(amount_c) if pd.notna(amount_c) else None,
                    actual=float(amount_a) if pd.notna(amount_a) else None,
                    diff=diff,
                    status=status,
                )
            )
            continue

        if pd.notna(name_c) and pd.isna(name_a):
            summary.missing_in_actuals += 1
            rows.append(
                ReconciliationRow(
                    supplier_name=str(name_c),
                    period=str(period),
                    expected=float(amount_c) if pd.notna(amount_c) else None,
                    actual=None,
                    status=MatchStatus.MISSING_IN_ACTUALS,
                )
            )
            continue

        if pd.isna(name_c) and pd.notna(name_a):
            summary.missing_in_contract += 1
            rows.append(
                ReconciliationRow(
                    supplier_name=str(name_a),
                    period=str(period),
                    expected=None,
                    actual=float(amount_a) if pd.notna(amount_a) else None,
                    status=MatchStatus.MISSING_IN_CONTRACT,
                )
            )

    if cfg.fuzzy_threshold > 0 and actuals.shape[0] > 0:
        actual_names = actuals[name_field].dropna().astype(str).tolist()
        normalized_actual = [normalize_name(n) for n in actual_names]
        for i, row in enumerate(rows):
            if row.status is not MatchStatus.MISSING_IN_ACTUALS:
                continue
            needle = normalize_name(row.supplier_name)
            best = _best_match(needle, normalized_actual, cfg.fuzzy_threshold)
            if best is None:
                continue
            matched_raw, score = best
            original = next(
                (n for n in actual_names if normalize_name(n) == matched_raw),
                matched_raw,
            )
            rows[i] = row.model_copy(
                update={
                    "status": MatchStatus.MATCHED_FUZZY,
                    "supplier_name_raw": original,
                    "similarity": round(score, 1),
                }
            )
            summary.matched_fuzzy += 1
            summary.missing_in_actuals -= 1

    return ReconciliationResult(
        summary=summary,
        rows=rows,
        amount_tolerance=cfg.amount_tolerance,
        fuzzy_threshold=cfg.fuzzy_threshold,
    )
'@
Write-Utf8NoBom "$Recon\engine.py" $engine

# ============================================================
# 4. tests/unit/test_reconciliation.py
# ============================================================
$testRecon = @'
"""Тесты движка сверки."""

from __future__ import annotations

import pandas as pd

from supplier_bonus.reconciliation.engine import MatchConfig, reconcile
from supplier_bonus.reconciliation.normalize import normalize_inn, normalize_name
from supplier_bonus.schemas import MatchStatus


def test_normalize_name_removes_opf_and_junk() -> None:
    assert normalize_name('ООО «Пример»') == "пример"
    assert normalize_name("АО  Пример-Трейд") == "пример-трейд"
    assert normalize_name("ПАО   Ромашка,  инк.") == "ромашка инк"


def test_normalize_inn_keeps_only_digits() -> None:
    assert normalize_inn("7701234567") == "7701234567"
    assert normalize_inn("ИНН 770-123-45-67") == "7701234567"
    assert normalize_inn("123") is None
    assert normalize_inn(None) is None


def test_reconcile_exact_match() -> None:
    contracts = pd.DataFrame(
        [
            {
                "supplier_name": "ООО «Пример»",
                "inn": "7701234567",
                "period": "2026-Q1",
                "amount": 100_000.0,
            }
        ]
    )
    actuals = pd.DataFrame(
        [
            {
                "supplier_name": "ООО «Пример»",
                "inn": "7701234567",
                "period": "2026-Q1",
                "amount": 100_000.0,
            }
        ]
    )
    result = reconcile(contracts, actuals)
    assert result.summary.matched_by_inn == 1
    assert result.rows[0].status is MatchStatus.MATCHED_WITHIN_TOLERANCE


def test_reconcile_amount_mismatch() -> None:
    contracts = pd.DataFrame(
        [{"supplier_name": "X", "inn": None, "period": "2026-Q1", "amount": 100.0}]
    )
    actuals = pd.DataFrame(
        [{"supplier_name": "X", "inn": None, "period": "2026-Q1", "amount": 80.0}]
    )
    result = reconcile(contracts, actuals)
    assert result.summary.amount_mismatch == 1
    assert result.rows[0].diff == 20.0


def test_reconcile_missing_in_actuals() -> None:
    contracts = pd.DataFrame(
        [{"supplier_name": "Y", "inn": None, "period": "2026-Q1", "amount": 50.0}]
    )
    actuals = pd.DataFrame(columns=["supplier_name", "inn", "period", "amount"])
    result = reconcile(contracts, actuals)
    assert result.summary.missing_in_actuals == 1
    assert result.rows[0].status is MatchStatus.MISSING_IN_ACTUALS


def test_reconcile_fuzzy_fallback() -> None:
    contracts = pd.DataFrame(
        [
            {
                "supplier_name": "ООО «Пример»",
                "inn": None,
                "period": "2026-Q1",
                "amount": 100.0,
            }
        ]
    )
    actuals = pd.DataFrame(
        [
            {
                "supplier_name": "ООО «Пример-Трейд»",
                "inn": None,
                "period": "2026-Q1",
                "amount": 100.0,
            }
        ]
    )
    cfg = MatchConfig(fuzzy_threshold=80)
    result = reconcile(contracts, actuals, config=cfg)
    assert result.summary.matched_fuzzy == 1
    assert result.rows[0].similarity is not None
    assert result.rows[0].similarity >= 80


def test_reconcile_empty_inputs() -> None:
    result = reconcile(pd.DataFrame(), pd.DataFrame())
    assert result.rows == []
    assert result.summary.matched == 0
'@
Write-Utf8NoBom "$Tests\test_reconciliation.py" $testRecon

# ============================================================
# 5. config.py: ensure_dirs + get_settings(ensure_dirs=False)
# ============================================================
$configPath = "$Src\config.py"
$c = Get-Content $configPath -Raw -Encoding utf8

if ($c -notmatch 'def ensure_dirs') {
    $ensureMethod = @'

    def ensure_dirs(self) -> None:
        """Создаёт каталоги, которые нужны приложению."""
        if self.review_documents_dir:
            Path(self.review_documents_dir).mkdir(parents=True, exist_ok=True)
        self.test_data_path.mkdir(parents=True, exist_ok=True)
'@
    $c = $c -replace '(def get_settings)', ($ensureMethod + "`r`n`r`n`$1")
}

if ($c -match '(?s)def get_settings\(\) -> Settings:\r?\n    return Settings\(\)') {
    $c = $c -replace `
        '(?s)def get_settings\(\) -> Settings:\r?\n    return Settings\(\)', `
        @'
def get_settings(*, ensure_dirs: bool = False) -> Settings:
    """Возвращает настройки. При ensure_dirs=True создаёт каталоги."""
    s = Settings()
    if ensure_dirs:
        s.ensure_dirs()
    return s
'@
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText(
    [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $configPath)),
    $c,
    $utf8NoBom
)
Write-Host "  ~ $configPath (ensure_dirs + флаг)" -ForegroundColor Cyan

# ============================================================
# 6. __main__.py: рабочий CLI
# ============================================================
$main = @'
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
'@
Write-Utf8NoBom "$Src\__main__.py" $main

# ============================================================
# 7. Уборка: egg-info, одноразовые .ps1
# ============================================================
# egg-info — убрать из индекса
$eggInfo = git ls-files 2>$null | Select-String 'egg-info'
if ($eggInfo) {
    git rm -r --cached "src\supplier_bonus_reconciliation.egg-info" 2>$null | Out-Null
    Write-Host "  - egg-info убран из индекса" -ForegroundColor DarkGray
}

# .gitignore
$gitignoreAdd = @'

# setuptools egg-info
*.egg-info/
'@
$giPath = ".gitignore"
$giContent = [System.IO.File]::ReadAllText(
    [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $giPath)),
    [System.Text.Encoding]::UTF8
)
if ($giContent -notmatch '\*\.egg-info/') {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText(
        [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $giPath)),
        $giContent + $gitignoreAdd,
        $utf8NoBom
    )
    Write-Host "  ~ .gitignore (+*.egg-info/)" -ForegroundColor Cyan
}

# Одноразовые скрипты
foreach ($s in @("fix-review-gaps.ps1","fix-adapter.ps1","fix-str-enum.ps1",
                 "add-reconciliation.ps1","setup-docket-integration.ps1",
                 "setup-bootstrap.ps1")) {
    if (Test-Path $s) {
        Remove-Item $s -Force
        Write-Host "  - $s" -ForegroundColor DarkGray
    }
}

# ============================================================
# 8. ПРОВЕРКИ
# ============================================================
Write-Host ""
Write-Host "=== ruff check ===" -ForegroundColor Yellow
ruff check src tests 2>&1 | ForEach-Object { Write-Host "  $_" }

Write-Host ""
Write-Host "=== ruff format ===" -ForegroundColor Yellow
ruff format src tests 2>&1 | ForEach-Object { Write-Host "  $_" }

Write-Host ""
Write-Host "=== mypy src ===" -ForegroundColor Yellow
mypy src 2>&1 | ForEach-Object { Write-Host "  $_" }

Write-Host ""
Write-Host "=== pytest ===" -ForegroundColor Yellow
pytest tests/unit -q 2>&1 | Select-Object -Last 20 | ForEach-Object { Write-Host "  $_" }

Write-Host ""
Write-Host "=== CLI --help ===" -ForegroundColor Yellow
python -m supplier_bonus --help 2>&1 | ForEach-Object { Write-Host "  $_" }

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host "Готово." -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Дальше — ВРУЧНУЮ, только если pytest показал '12 passed':" -ForegroundColor Yellow
Write-Host ""
Write-Host '  $t = "openspec\changes\supplier-bonus-reconciliation\tasks.md"' -ForegroundColor White
Write-Host '  $c = Get-Content $t -Raw -Encoding utf8' -ForegroundColor White
Write-Host '  $c = $c -replace "- \[ \] 2\.1 ", "- [x] 2.1 "' -ForegroundColor White
Write-Host '  $c = $c -replace "- \[ \] 2\.2 ", "- [x] 2.2 "' -ForegroundColor White
Write-Host '  $c = $c -replace "- \[ \] 2\.3 ", "- [x] 2.3 "' -ForegroundColor White
Write-Host '  $c = $c -replace "- \[ \] 2\.5 ", "- [x] 2.5 "' -ForegroundColor White
Write-Host '  $utf8 = New-Object System.Text.UTF8Encoding($false)' -ForegroundColor White
Write-Host '  [System.IO.File]::WriteAllText((Resolve-Path $t), $c, $utf8)' -ForegroundColor White
Write-Host ""
Write-Host "Затем:" -ForegroundColor Green
Write-Host "  git add ." -ForegroundColor Green
Write-Host "  git commit -m 'feat(reconciliation): engine + CLI + ensure_dirs'" -ForegroundColor Green
Write-Host "  git push" -ForegroundColor Green