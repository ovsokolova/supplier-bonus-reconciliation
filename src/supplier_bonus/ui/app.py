"""Streamlit-дашборд для сверки бонусов поставщиков.

Запуск:
    streamlit run src/supplier_bonus/ui/app.py

Возможности:
- загрузка CSV с договорными условиями и фактом;
- настройка допуска и порога fuzzy через sidebar;
- KPI-карточки (matched / mismatch / missing / fuzzy);
- таблица расхождений с цветовой подсветкой;
- экспорт в Excel (три листа).
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from supplier_bonus.reconciliation.engine import MatchConfig, reconcile
from supplier_bonus.reporting.excel import export_to_excel
from supplier_bonus.schemas import MatchStatus, ReconciliationResult

# ---------------------------------------------------------------------------
# Константы
# ---------------------------------------------------------------------------
FIXTURES = Path("data/examples")

STATUS_COLORS = {
    MatchStatus.MATCHED: "#C6EFCE",
    MatchStatus.MATCHED_BY_INN: "#C6EFCE",
    MatchStatus.MATCHED_WITHIN_TOLERANCE: "#C6EFCE",
    MatchStatus.MATCHED_FUZZY: "#FFEB9C",
    MatchStatus.AMOUNT_MISMATCH: "#FFC7CE",
    MatchStatus.MISSING_IN_ACTUALS: "#FFC7CE",
    MatchStatus.MISSING_IN_CONTRACT: "#FFC7CE",
    MatchStatus.PERIOD_OFFSET: "#FFC7CE",
    MatchStatus.NEEDS_REVIEW: "#FFEB9C",
}

STATUS_LABELS = {
    MatchStatus.MATCHED: "Совпало по имени",
    MatchStatus.MATCHED_BY_INN: "Совпало по ИНН",
    MatchStatus.MATCHED_WITHIN_TOLERANCE: "Совпало (в допуске)",
    MatchStatus.MATCHED_FUZZY: "Совпало нечётко",
    MatchStatus.AMOUNT_MISMATCH: "Расхождение суммы",
    MatchStatus.MISSING_IN_ACTUALS: "Нет в факте",
    MatchStatus.MISSING_IN_CONTRACT: "Нет в договоре",
    MatchStatus.PERIOD_OFFSET: "Смещение периода",
    MatchStatus.NEEDS_REVIEW: "Требует проверки",
}


# ---------------------------------------------------------------------------
# Загрузка данных
# ---------------------------------------------------------------------------
def _load_fixtures() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Загружает demo-набор из data/examples."""
    scenarios_path = FIXTURES / "scenarios.json"
    if not scenarios_path.exists():
        raise FileNotFoundError(
            "Фикстуры не найдены. Запустите: python scripts/generate_fixtures.py"
        )
    scenarios = json.loads(scenarios_path.read_text(encoding="utf-8"))["scenarios"]
    contracts_rows = []
    actuals_rows = []
    for fx in scenarios:
        inn = (fx["supplier"].get("inn") or "") if fx["supplier"] else ""
        contracts_rows.append(
            {
                "supplier_name": fx["supplier"]["name"],
                "inn": inn,
                "period": fx["period"],
                "amount": fx["expected_amount"],
                "scenario": fx["scenario"],
            }
        )
        csv = FIXTURES / "actuals" / f"{fx['contract_id']}_actual.csv"
        if csv.exists():
            df = pd.read_csv(csv, dtype={"inn": str}).fillna({"inn": ""})
            df["scenario"] = fx["scenario"]
            actuals_rows.append(df)
    actuals = (
        pd.concat(actuals_rows, ignore_index=True)
        if actuals_rows
        else pd.DataFrame(columns=["supplier_name", "inn", "period", "amount"])
    )
    return pd.DataFrame(contracts_rows), actuals


def _upload_csv(label: str, key: str) -> pd.DataFrame | None:
    f = st.file_uploader(label, type=["csv"], key=key)
    if f is None:
        return None
    try:
        return pd.read_csv(f, dtype={"inn": str}).fillna({"inn": ""})
    except Exception as exc:  # noqa: BLE001
        st.error(f"Не удалось прочитать CSV: {exc}")
        return None


# ---------------------------------------------------------------------------
# Рендер
# ---------------------------------------------------------------------------
def _render_kpis(result: ReconciliationResult) -> None:
    s = result.summary
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Совпало", s.matched + s.matched_by_inn + s.matched_within_tolerance)
    col2.metric("Нечётко", s.matched_fuzzy)
    col3.metric("Расхождение", s.amount_mismatch)
    col4.metric("Пропуски", s.missing_in_actuals + s.missing_in_contract)

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("matched", s.matched)
    col6.metric("by_inn", s.matched_by_inn)
    col7.metric("within_tol", s.matched_within_tolerance)
    col8.metric("needs_review", s.needs_review)


def _render_table(result: ReconciliationResult, selected_statuses: list[MatchStatus]) -> None:
    rows = [
        {
            "Поставщик": r.supplier_name,
            "Исходное имя": r.supplier_name_raw or "",
            "Период": r.period,
            "Ожидаемо": r.expected,
            "Факт": r.actual,
            "Отклонение": r.diff,
            "Схожесть": r.similarity,
            "Статус": STATUS_LABELS.get(r.status, r.status.value),
            "_status": r.status,
        }
        for r in result.rows
        if r.status in selected_statuses
    ]
    if not rows:
        st.info("Нет строк, соответствующих фильтру.")
        return
    df = pd.DataFrame(rows)

    def _color(row: pd.Series) -> list[str]:
        color = STATUS_COLORS.get(row["_status"], "")
        return [f"background-color: {color}" if color else ""] * len(row)

    styled = df.drop(columns=["_status"]).style.apply(_color, axis=1)
    st.dataframe(styled, use_container_width=True, height=420)


def _render_export(result: ReconciliationResult) -> None:
    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        export_to_excel(result, tmp_path)
        data = tmp_path.read_bytes()
        st.download_button(
            "Скачать Excel",
            data=data,
            file_name="reconciliation.xlsx",
            mime=("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        )
    finally:
        tmp_path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Точка входа
# ---------------------------------------------------------------------------
def main() -> None:
    st.set_page_config(page_title="Сверка бонусов поставщиков", layout="wide")
    st.title("Сверка бонусов поставщиков")

    st.sidebar.header("Параметры сверки")
    amount_tolerance = st.sidebar.number_input(
        "Допуск по сумме, ₽", min_value=0.0, value=1.0, step=0.5
    )
    fuzzy_threshold = st.sidebar.slider("Порог fuzzy", min_value=0, max_value=100, value=90, step=5)

    st.sidebar.header("Источник данных")
    use_fixtures = st.sidebar.button("Загрузить демо-фикстуры")

    if "contracts" not in st.session_state:
        st.session_state.contracts = None
        st.session_state.actuals = None

    if use_fixtures:
        try:
            st.session_state.contracts, st.session_state.actuals = _load_fixtures()
            st.sidebar.success("Демо-фикстуры загружены.")
        except FileNotFoundError as exc:
            st.sidebar.error(str(exc))

    st.subheader("Договорные условия")
    contracts_upload = _upload_csv("CSV с договорными условиями", "contracts")
    if contracts_upload is not None:
        st.session_state.contracts = contracts_upload
    if st.session_state.contracts is not None:
        st.caption(f"Строк: {len(st.session_state.contracts)}")
        st.dataframe(st.session_state.contracts.head(10), use_container_width=True)

    st.subheader("Фактические данные")
    actuals_upload = _upload_csv("CSV с фактическими данными", "actuals")
    if actuals_upload is not None:
        st.session_state.actuals = actuals_upload
    if st.session_state.actuals is not None:
        st.caption(f"Строк: {len(st.session_state.actuals)}")
        st.dataframe(st.session_state.actuals.head(10), use_container_width=True)

    if st.session_state.contracts is None or st.session_state.actuals is None:
        st.info("Загрузите оба файла или нажмите «Загрузить демо-фикстуры».")
        return

    if not st.button("Запустить сверку", type="primary"):
        return

    cfg = MatchConfig(
        amount_tolerance=amount_tolerance,
        fuzzy_threshold=fuzzy_threshold,
    )
    result = reconcile(
        st.session_state.contracts,
        st.session_state.actuals,
        config=cfg,
    )

    st.header("Результаты")
    _render_kpis(result)

    st.subheader("Фильтр по статусам")
    all_statuses = sorted({r.status for r in result.rows}, key=lambda s: s.value)
    selected = st.multiselect(
        "Статусы",
        options=all_statuses,
        default=all_statuses,
        format_func=lambda s: STATUS_LABELS.get(s, s.value),
    )
    _render_table(result, selected)

    st.subheader("Экспорт")
    _render_export(result)


if __name__ == "__main__":
    main()
