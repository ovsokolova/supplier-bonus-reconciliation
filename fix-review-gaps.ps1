# fix-review-gaps.ps1
# Запуск: pwsh -ExecutionPolicy Bypass -File .\fix-review-gaps.ps1

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

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

# ============================================================
# 1. CI workflow
# ============================================================
$ci = @'
name: CI

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: pyproject.toml
      - name: Install system deps
        run: |
          sudo apt-get update
          sudo apt-get install -y tesseract-ocr tesseract-ocr-rus
      - name: Install deps
        run: pip install -e ".[dev,extraction]"
      - name: Ruff lint
        run: ruff check src tests
      - name: Ruff format check
        run: ruff format --check src tests
      - name: Mypy
        run: mypy src
      - name: Pytest
        run: pytest -q
'@
Write-Utf8NoBom ".github\workflows\ci.yml" $ci

# ============================================================
# 2. __main__.py
# ============================================================
$main = @'
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
'@
Write-Utf8NoBom "src\supplier_bonus\__main__.py" $main

# ============================================================
# 3. config.py: ensure_dirs
# ============================================================
$configPath = "src\supplier_bonus\config.py"
$c = Get-Content $configPath -Raw -Encoding utf8

$ensureMethod = @'

    def ensure_dirs(self) -> None:
        """Создаёт каталоги, которые нужны приложению."""
        if self.review_documents_dir:
            Path(self.review_documents_dir).mkdir(parents=True, exist_ok=True)
        self.test_data_path.mkdir(parents=True, exist_ok=True)
'@

if ($c -notmatch 'def ensure_dirs') {
    $c = $c -replace '(def get_settings\(\) -> Settings:)', ($ensureMethod + "`r`n`r`n`$1")
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText(
        [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $configPath)),
        $c,
        $utf8NoBom
    )
    Write-Host "  ~ $configPath (добавлен ensure_dirs)" -ForegroundColor Cyan
}

# ============================================================
# 4. docket_adapter.py: сузить except
# ============================================================
$adapterPath = "src\supplier_bonus\extraction\docket_adapter.py"
$a = Get-Content $adapterPath -Raw -Encoding utf8

# 4.1 Заменить broad except в register_bonus_schema
$a = $a -replace `
    '(?s)    except Exception as exc:  # noqa: BLE001\r?\n        logger\.warning\("Schema %s: %s", SCHEMA_ID, exc\)', `
    "    except ValueError as exc:`r`n        logger.warning(`"Schema %s уже зарегистрирована: %s`", SCHEMA_ID, exc)"

# 4.2 Заменить broad except в extract_terms
$a = $a -replace `
    '(?s)            except Exception as exc:  # noqa: BLE001\r?\n                logger\.warning\("Пропуск документа: %s", exc\)', `
    "            except ValidationError as exc:`r`n                logger.warning(`"Пропуск документа (валидация): %s`", exc)"

# 4.3 Добавить импорт ValidationError
if ($a -notmatch 'from pydantic import ValidationError') {
    $a = $a -replace `
        'from supplier_bonus\.config import Settings, get_settings', `
        "from pydantic import ValidationError`r`n`r`nfrom supplier_bonus.config import Settings, get_settings"
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText(
    [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $adapterPath)),
    $a,
    $utf8NoBom
)
Write-Host "  ~ $adapterPath (сужены except)" -ForegroundColor Cyan

# ============================================================
# 5. tasks.md: обновить статусы
# ============================================================
$tasksPath = "openspec\changes\supplier-bonus-reconciliation\tasks.md"
$t = Get-Content $tasksPath -Raw -Encoding utf8

$t = $t -replace '- \[ \] 0\.3 \.gitignore \(уже есть\), pre-commit', '- [x] 0.3 .gitignore (уже есть), pre-commit'
$t = $t -replace '- \[ \] 0\.4 \.github/workflows/ci\.yml \(lint \+ pytest\)', '- [x] 0.4 .github/workflows/ci.yml (lint + pytest)'
$t = $t -replace '- \[ \] 2\.1 Outer join по ИНН с fallback на наименование', '- [x] 2.1 Outer join по ИНН с fallback на наименование'
$t = $t -replace '- \[ \] 2\.2 Нормализация ключей \+ поля \*_raw', '- [x] 2.2 Нормализация ключей + поля *_raw'
$t = $t -replace '- \[ \] 2\.3 rapidfuzz \(token_sort_ratio \+ WRatio\), порог 90', '- [x] 2.3 rapidfuzz (token_sort_ratio + WRatio), порог 90'
$t = $t -replace '- \[ \] 2\.5 Статусы: matched, matched_by_inn, matched_fuzzy,\s*\r?\n\s+amount_mismatch, missing_\*', '- [x] 2.5 Статусы: matched, matched_by_inn, matched_fuzzy, amount_mismatch, missing_*'

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText(
    [System.IO.Path]::GetFullPath((Join-Path (Get-Location) $tasksPath)),
    $t,
    $utf8NoBom
)
Write-Host "  ~ $tasksPath (обновлены статусы)" -ForegroundColor Cyan

# ============================================================
# 6. Проверки
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
pytest tests/unit -q 2>&1 | Select-Object -Last 15 | ForEach-Object { Write-Host "  $_" }

Write-Host ""
Write-Host "Готово. Дальше:" -ForegroundColor Green
Write-Host "  git add . ; git commit -m 'chore: CI, __main__, narrow excepts, ensure_dirs'" -ForegroundColor Green
Write-Host "  git push" -ForegroundColor Green