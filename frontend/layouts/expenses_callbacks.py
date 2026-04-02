from __future__ import annotations

import os

import pandas as pd
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, html, no_update

from components.charts import category_pie_chart, monthly_trends_bar_chart
from api_client import (
    fetch_raw_expenses,
    fetch_yearly_data,
    fetch_budget_pacing,
    fetch_settlement,
    fetch_personal_totals,
    fetch_spending_per_person,
    update_expense,
    export_to_sheets,
)
from layouts.expenses_layout import _Ids

PAYER_1 = os.getenv('PAYER_1', 'Michael')
PAYER_2 = os.getenv('PAYER_2', 'Ori')


def register_expenses_callbacks(app: Dash) -> None:
    ids = _Ids()

    @app.callback(
        Output(ids.table, "data"),
        Output(ids.ids_store, "data"),
        Output(ids.reference_store, "data"),
        Input(ids.year_dropdown, "value"),
        Input(ids.month_tabs, "active_tab"),
        Input(ids.split_radio, "value"),
    )
    def _update_table(selected_year: int, active_month_str: str, split_value: str):
        if not selected_year or not active_month_str:
            return [], [], []

        month = int(active_month_str)
        split_value = split_value or "shared"

        if split_value == "shared":
            df_month = fetch_raw_expenses(selected_year, month, "shared")
        else:
            df_all_personal = fetch_raw_expenses(selected_year, month, "personal")
            if not df_all_personal.empty:
                df_month = df_all_personal[
                    df_all_personal["payer"].str.lower() == split_value.lower()
                ].reset_index(drop=True)
            else:
                df_month = df_all_personal

        if not df_month.empty and "date" in df_month.columns:
            df_month["date"] = df_month["date"].dt.strftime("%Y-%m-%d")

        records = df_month.to_dict("records")
        row_ids = [r.get("id") for r in records]
        return records, row_ids, records

    @app.callback(
        Output(ids.pie_graph, "figure"),
        Output(ids.trends_graph, "figure"),
        Output(ids.kpi_spent, "children"),
        Output(ids.kpi_pacing, "children"),
        Output(ids.kpi_pacing, "className"),
        Output(ids.kpi_average, "children"),
        Input(ids.year_dropdown, "value"),
        Input(ids.month_tabs, "active_tab"),
        Input(ids.split_radio, "value"),
        Input(ids.table, "data"),
    )
    def _update_fast_components(selected_year: int, active_month_str: str,
                                split_value: str, table_data: list[dict]):
        if not selected_year or not active_month_str:
            return {}, {}, "₪0", "₪0", "fw-bold", "₪0"

        split_value = split_value or "shared"
        month = int(active_month_str)
        is_person_view = split_value in (PAYER_1.lower(), PAYER_2.lower())

        if is_person_view:
            df_personal = fetch_yearly_data(selected_year, "personal")
            if not df_personal.empty:
                df_personal = df_personal[
                    df_personal["payer"].str.lower() == split_value.lower()
                ].copy()

            df_shared = fetch_yearly_data(selected_year, "shared")
            if not df_shared.empty:
                df_shared = df_shared.copy()
                df_shared["amount"] = df_shared["amount"] / 2.0

            yearly_df = pd.concat(
                [df for df in [df_personal, df_shared] if not df.empty],
                ignore_index=True,
            )
        else:
            yearly_df = fetch_yearly_data(selected_year, "shared")

        trend_summary = {}
        if not yearly_df.empty:
            yearly_df["month_num"] = yearly_df["date"].dt.strftime("%m")
            monthly_sums = yearly_df.groupby("month_num")["amount"].sum()
            trend_summary = monthly_sums.to_dict()

        trends_fig = monthly_trends_bar_chart(summary_dict=trend_summary, year=selected_year)

        if is_person_view:
            df_pie = yearly_df[yearly_df["date"].dt.month == month].copy() if not yearly_df.empty else pd.DataFrame()
        else:
            if table_data:
                df_pie = pd.DataFrame(table_data)
            else:
                df_pie = yearly_df[yearly_df["date"].dt.month == month] if not yearly_df.empty else pd.DataFrame()

        pie_fig = category_pie_chart(df=df_pie)

        month_str_padded = f"{month:02d}"
        if is_person_view:
            burdens = fetch_spending_per_person(selected_year, month)
            total_spent = float(burdens.get(split_value.capitalize(), 0.0))
        else:
            total_spent = float(trend_summary.get(month_str_padded, 0.0))
        text_spent = f"₪{total_spent:,.0f}"

        if is_person_view:
            text_pacing = "—"
            pacing_class = "text-muted fw-bold mb-0"
        else:
            pacing_data = fetch_budget_pacing(selected_year, month)
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

        non_zero_months = [float(v) for v in trend_summary.values() if float(v) > 0]
        avg_monthly = float(sum(non_zero_months) / len(non_zero_months)) if non_zero_months else 0.0
        text_average = f"₪{avg_monthly:,.0f}"

        return pie_fig, trends_fig, text_spent, text_pacing, pacing_class, text_average

    @app.callback(
        Output(ids.payer_summary_div, "children"),
        Input(ids.year_dropdown, "value"),
        Input(ids.month_tabs, "active_tab"),
        Input(ids.table, "data"),
    )
    def _update_payer_summary(selected_year: int, active_month_str: str, table_data: list[dict]):
        if not selected_year or not active_month_str:
            return ""

        month = int(active_month_str)
        df_shared = fetch_raw_expenses(selected_year, month, split="shared")
        personal_totals = fetch_personal_totals(selected_year, month)
        settlement = fetch_settlement(selected_year, month)

        if df_shared.empty and not personal_totals:
            return html.Div("No transactions this month.", className="text-muted")

        shared_paid: dict[str, float] = {}
        if not df_shared.empty:
            shared_paid = df_shared.groupby("payer")["amount"].sum().to_dict()

        payers = sorted(set(list(shared_paid.keys()) + list(personal_totals.keys())))

        cards = []
        for p in payers:
            paid_shared = shared_paid.get(p, 0.0)
            paid_personal = personal_totals.get(p, 0.0)
            total_shared_all = sum(shared_paid.values())
            fair_share = total_shared_all / 2.0
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
