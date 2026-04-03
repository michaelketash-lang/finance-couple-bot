from __future__ import annotations

import os

import pandas as pd
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, html, no_update

from components.charts import category_pie_chart, monthly_trends_bar_chart
from api_client import (
    fetch_dashboard_data,
    update_expense,
    export_to_sheets,
)
from layouts.expenses_layout import _Ids

PAYER_1 = os.getenv('PAYER_1', 'Michael')
PAYER_2 = os.getenv('PAYER_2', 'Ori')


def register_expenses_callbacks(app: Dash) -> None:
    ids = _Ids()

    # =========================================================================
    # MASTER CALLBACK
    # Triggered by year or month change — the only place that calls the API.
    # Fetches all data for the selected month in a single BFF round-trip and
    # writes it to the dashboard store. All rendering callbacks read from
    # the store, so they never make additional HTTP requests.
    # =========================================================================

    @app.callback(
        Output(ids.dashboard_store, "data"),
        Input(ids.year_dropdown, "value"),
        Input(ids.month_tabs, "active_tab"),
    )
    def _fetch_dashboard_data(selected_year: int, active_month_str: str):
        if not selected_year or not active_month_str:
            return {}
        return fetch_dashboard_data(selected_year, int(active_month_str))

    # =========================================================================
    # SLAVE CALLBACK 1 — TABLE
    # Reads raw expenses from the store and filters by the split radio.
    # No API call — pure in-memory filtering.
    # =========================================================================

    @app.callback(
        Output(ids.table, "data"),
        Output(ids.ids_store, "data"),
        Output(ids.reference_store, "data"),
        Input(ids.split_radio, "value"),
        Input(ids.dashboard_store, "data"),
    )
    def _render_table(split_value: str, store: dict):
        if not store:
            return [], [], []

        split_value = split_value or "shared"
        expenses = store.get("expenses", [])

        if split_value == "shared":
            rows = [r for r in expenses if r.get("split") == "shared"]
        else:
            rows = [
                r for r in expenses
                if r.get("split") == "personal"
                and r.get("payer", "").lower() == split_value.lower()
            ]

        row_ids = [r.get("id") for r in rows]
        return rows, row_ids, rows

    # =========================================================================
    # SLAVE CALLBACK 2 — CHARTS + KPIs
    # Builds pie chart, trends chart, and three KPI values entirely from the
    # store. No API calls.
    # =========================================================================

    @app.callback(
        Output(ids.pie_graph, "figure"),
        Output(ids.trends_graph, "figure"),
        Output(ids.kpi_spent, "children"),
        Output(ids.kpi_pacing, "children"),
        Output(ids.kpi_pacing, "className"),
        Output(ids.kpi_average, "children"),
        Input(ids.split_radio, "value"),
        Input(ids.month_tabs, "active_tab"),
        Input(ids.dashboard_store, "data"),
    )
    def _render_charts_and_kpis(split_value: str, active_month_str: str, store: dict):
        if not store or not active_month_str:
            return {}, {}, "₪0", "₪0", "fw-bold", "₪0"

        split_value = split_value or "shared"
        month = int(active_month_str)
        month_str_padded = f"{month:02d}"
        is_person_view = split_value in (PAYER_1.lower(), PAYER_2.lower())

        yearly_raw = store.get("yearly_raw", [])
        kpis = store.get("kpis", {})

        # --- Build yearly DataFrame from store ---
        if yearly_raw:
            df_year = pd.DataFrame(yearly_raw)
            df_year["date"] = pd.to_datetime(df_year["date"], errors="coerce")
            df_year["amount"] = pd.to_numeric(df_year["amount"], errors="coerce").fillna(0.0)
        else:
            df_year = pd.DataFrame(columns=["date", "merchant", "amount", "category", "payer", "split"])

        # --- Trend chart data: monthly totals for the selected view ---
        if is_person_view:
            # Personal rows for this payer + half of all shared rows
            df_personal = df_year[
                (df_year["split"] == "personal") &
                (df_year["payer"].str.lower() == split_value.lower())
            ].copy()
            df_shared = df_year[df_year["split"] == "shared"].copy()
            df_shared["amount"] = df_shared["amount"] / 2.0
            df_trend = pd.concat([df_personal, df_shared], ignore_index=True)
        else:
            df_trend = df_year[df_year["split"] == "shared"].copy()

        trend_summary: dict = {}
        if not df_trend.empty:
            df_trend["month_num"] = df_trend["date"].dt.strftime("%m")
            trend_summary = df_trend.groupby("month_num")["amount"].sum().to_dict()

        trends_fig = monthly_trends_bar_chart(summary_dict=trend_summary, year=store.get("year", 0))

        # --- Pie chart data: current month, same split/payer filter ---
        expenses = store.get("expenses", [])
        if expenses:
            df_month = pd.DataFrame(expenses)
            df_month["amount"] = pd.to_numeric(df_month["amount"], errors="coerce").fillna(0.0)
            if is_person_view:
                df_pie_personal = df_month[
                    (df_month["split"] == "personal") &
                    (df_month["payer"].str.lower() == split_value.lower())
                ].copy()
                df_pie_shared = df_month[df_month["split"] == "shared"].copy()
                df_pie_shared["amount"] = df_pie_shared["amount"] / 2.0
                df_pie = pd.concat([df_pie_personal, df_pie_shared], ignore_index=True)
            else:
                df_pie = df_month[df_month["split"] == "shared"].copy()
        else:
            df_pie = pd.DataFrame()

        pie_fig = category_pie_chart(df=df_pie)

        # --- KPI: Total Spent ---
        if is_person_view:
            per_person = store.get("payer_summary", {}).get("per_person", {})
            total_spent = float(per_person.get(split_value.capitalize(), 0.0))
        else:
            total_spent = float(kpis.get("total_spent", 0.0))
        text_spent = f"₪{total_spent:,.0f}"

        # --- KPI: Budget Pacing (shared view only) ---
        if is_person_view:
            text_pacing = "—"
            pacing_class = "text-muted fw-bold mb-0"
        else:
            pacing_data = kpis.get("budget_pacing", {})
            pacing_status = pacing_data.get("status", "On Track")
            pacing_amount = pacing_data.get("amount", 0.0)
            text_pacing = f"₪{pacing_amount:,.0f}"
            if pacing_status == "Over Budget":
                pacing_class = "text-danger fw-bold mb-0"
                text_pacing = f"{pacing_status} (₪{pacing_amount:,.0f})"
            elif pacing_status == "No Budget Set":
                pacing_class = "text-muted fw-bold mb-0"
                text_pacing = "No Budget"
            else:
                pacing_class = "text-info fw-bold mb-0"

        # --- KPI: Monthly Average (non-zero months only) ---
        non_zero = [float(v) for v in trend_summary.values() if float(v) > 0]
        avg_monthly = float(sum(non_zero) / len(non_zero)) if non_zero else 0.0
        text_average = f"₪{avg_monthly:,.0f}"

        return pie_fig, trends_fig, text_spent, text_pacing, pacing_class, text_average

    # =========================================================================
    # SLAVE CALLBACK 3 — PAYER SUMMARY CARDS
    # Reads pre-computed payer data from the store. No API call.
    # =========================================================================

    @app.callback(
        Output(ids.payer_summary_div, "children"),
        Input(ids.dashboard_store, "data"),
    )
    def _render_payer_summary(store: dict):
        if not store:
            return ""

        payer_summary = store.get("payer_summary", {})
        shared_payments = store.get("expenses", [])

        # Compute shared paid per payer from the raw expenses in the store
        shared_paid: dict[str, float] = {}
        for row in shared_payments:
            if row.get("split") == "shared":
                p = row.get("payer", "")
                shared_paid[p] = round(shared_paid.get(p, 0.0) + float(row.get("amount", 0)), 2)

        personal_totals: dict = payer_summary.get("personal_totals", {})
        settlement: dict = payer_summary.get("settlement", {})

        payers = sorted(set(list(shared_paid.keys()) + list(personal_totals.keys())))

        if not payers:
            return html.Div("No transactions this month.", className="text-muted")

        cards = []
        total_shared_all = sum(shared_paid.values())
        fair_share = total_shared_all / 2.0

        for p in payers:
            paid_shared = shared_paid.get(p, 0.0)
            paid_personal = personal_totals.get(p, 0.0)
            net_total = fair_share + paid_personal

            is_balanced = settlement.get("balanced", False)
            if is_balanced or settlement.get("amount", 0.0) == 0.0:
                settlement_line = html.Div("Settled ✓", className="fw-medium text-success")
            elif settlement.get("debtor") == p:
                settlement_line = html.Div(
                    f"Owes {settlement['creditor']}: ₪{settlement['amount']:,.0f}",
                    className="fw-medium text-danger",
                )
            else:
                settlement_line = html.Div(
                    f"{settlement.get('debtor', '?')} owes you: ₪{settlement['amount']:,.0f}",
                    className="fw-medium text-success",
                )

            card = dbc.Card(
                dbc.CardBody([
                    html.H6(f"{p}", className="fw-bold mb-3 text-dark"),
                    html.Div(
                        [html.Span("Shared paid:", className="text-muted me-2"),
                         html.Span(f"₪{paid_shared:,.0f}", className="fw-medium text-primary")],
                        className="d-flex justify-content-between mb-1",
                    ),
                    html.Div(
                        [html.Span("Personal:", className="text-muted me-2"),
                         html.Span(f"₪{paid_personal:,.0f}", className="fw-medium text-secondary")],
                        className="d-flex justify-content-between mb-1",
                    ),
                    html.Div(
                        [html.Span("Settlement:", className="text-muted me-2"), settlement_line],
                        className="d-flex justify-content-between mb-1",
                    ),
                    html.Hr(className="my-2"),
                    html.Div(
                        [html.Span("Net Total:", className="fw-bold text-dark me-2"),
                         html.Span(f"₪{net_total:,.0f}", className="fw-bold text-dark")],
                        className="d-flex justify-content-between",
                    ),
                ]),
                className="shadow-sm border-0 me-3 mb-2",
                style={"backgroundColor": "#f8f9fa", "minWidth": "240px"},
            )
            cards.append(card)

        return html.Div(cards, className="d-flex flex-wrap")

    # =========================================================================
    # INLINE EDIT — unchanged: fires only on table cell edits, calls API once.
    # =========================================================================

    @app.callback(
        Output(ids.edit_status, "children"),
        Output(ids.reference_store, "data", allow_duplicate=True),
        Input(ids.table, "data"),
        State(ids.reference_store, "data"),
        State(ids.ids_store, "data"),
        prevent_initial_call=True,
    )
    def _save_inline_edit(current_data: list[dict], reference_data: list[dict], row_ids: list):
        if not current_data or not reference_data or not row_ids:
            return no_update, no_update

        if len(current_data) != len(reference_data):
            return no_update, current_data

        changed_indices = [
            i for i, (curr, ref) in enumerate(zip(current_data, reference_data))
            if curr != ref
        ]

        if len(changed_indices) != 1:
            return no_update, current_data

        row_index = changed_indices[0]
        expense_id = row_ids[row_index]

        if not expense_id:
            return "Could not save: ID not found.", no_update

        row = current_data[row_index]
        success = update_expense(
            expense_id=int(expense_id),
            merchant=row.get("merchant", ""),
            amount=float(row.get("amount", 0)),
            category=row.get("category", ""),
            payer=row.get("payer", ""),
        )

        if success:
            updated_reference = list(reference_data)
            updated_reference[row_index] = row
            return f"✓ {row.get('merchant', 'Row')} updated", updated_reference

        return "Failed to save — check the server logs.", no_update

    # =========================================================================
    # EXPORT — unchanged: fires only on button click.
    # =========================================================================

    @app.callback(
        Output("export-status", "children"),
        Output("export-status", "style"),
        Input(ids.export_btn, "n_clicks"),
        State(ids.year_dropdown, "value"),
        State(ids.month_tabs, "active_tab"),
        State(ids.split_radio, "value"),
        prevent_initial_call=True,
    )
    def _export_to_sheets(n_clicks, year, active_month, split):
        if not n_clicks:
            return no_update, no_update

        result = export_to_sheets(year=year, month=int(active_month), split=split or "shared")

        if "error" in result:
            return f"Export failed: {result['error']}", {"fontSize": "0.875rem", "color": "red"}

        url = result.get("url", "")
        tab = result.get("tab", "")
        rows = result.get("rows", 0)
        link = html.A(f"Open Sheet ({rows} rows → {tab})", href=url, target="_blank",
                      className="ms-1 text-success fw-medium")
        return ["✓ Exported! ", link], {"fontSize": "0.875rem"}
