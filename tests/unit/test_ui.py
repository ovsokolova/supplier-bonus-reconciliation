"""Смоук-тесты UI (без запуска Streamlit-сервера)."""

from __future__ import annotations


def test_import_app() -> None:
    """app.py импортируется без ошибок."""
    import supplier_bonus.ui.app as app  # noqa: F401


def test_import_main() -> None:
    """main доступен через пакет."""
    from supplier_bonus.ui import main

    assert callable(main)


def test_status_labels_complete() -> None:
    """Все статусы имеют человекочитаемые метки."""
    from supplier_bonus.schemas import MatchStatus
    from supplier_bonus.ui.app import STATUS_LABELS

    for status in MatchStatus:
        assert status in STATUS_LABELS, f"Нет метки для {status}"


def test_status_colors_defined() -> None:
    """Все статусы имеют цвет."""
    from supplier_bonus.schemas import MatchStatus
    from supplier_bonus.ui.app import STATUS_COLORS

    for status in MatchStatus:
        assert status in STATUS_COLORS, f"Нет цвета для {status}"
