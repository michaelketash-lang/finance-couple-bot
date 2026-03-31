from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import calendar

import pandas as pd
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, dcc, html

from components.charts import category_pie_chart, monthly_trends_bar_chart, \
    CATEGORIES
from components.tables import expenses_datatable
from api_client import fetch_raw_expenses, fetch_yearly_data, \
    fetch_budget_pacing, fetch_settlement, fetch_personal_totals


@dataclass(frozen=True)
class _Ids:
    # Controls
    split_radio: str = "expenses-split-radio"
    year_dropdown: str = "expenses-year-dropdown"
    month_tabs: str = "expenses-month-tabs"
    export_btn: str = "expenses-export-btn"
    # KPI Cards
    kpi_spent: str = "expenses-kpi-spent"
    kpi_average: str = "expenses-kpi-average"
    kpi_pacing: str = "expenses-kpi-pacing"
    # Charts
    pie_graph: str = "expenses-category-pie"
    trends_graph: str = "expenses-monthly-trends"
    # Data & Table
    table: str = "expenses-table"
    edits_store: str = "expenses-edits-store"
    # Payer Summary
    payer_summary_div: str = "expenses-payer-summary"


# --- UI Construction Functions ---

def _create_kpi_card(title: str, id: str, color: str) -> dbc.Card:
    return dbc.Card(
        [
            dbc.CardHeader(title, className="fw-bold text-uppercase",
                           style={"fontSize": "0.8rem", "color": "#718096"}),
            dbc.CardBody(
                [
                    html.H3("₪0", id=id,
                            className=f"text-{color} fw-bold mb-0"),
                ],
                className="py-3",
            ),
        ],
        className="bg-white rounded shadow-sm h-100",
        style={"borderTop": f"4px solid var(--bs-{color})"}
    )


def _month_tabs_children() -> list[dbc.Tab]:
    children: list[dbc.Tab] = []
    for m in range(1, 13):
        label = calendar.month_abbr[m]
        children.append(
            dbc.Tab(label=label, tab_id=str(m), className="fw-medium"))
    return children


# --- Main Layout Function ---

def get_expenses_layout() -> dbc.Container:
    ids = _Ids()
    current_year = datetime.today().year
    current_month = str(datetime.today().month)
    default_split = "shared"

    years_options = [{"label": str(y), "value": y} for y in
                     range(2023, current_year + 2)]

    return dbc.Container(
        fluid=True,
        children=[
            dcc.Store(id=ids.edits_store, data={}, storage_type="memory"),

            # --- ROW 1: CONTROLS ---
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(
                                [
                                    html.Span("Expense Type:",
                                              className="fw-bold me-3 text-muted"),
                                    dbc.RadioItems(
                                        id=ids.split_radio,
                                        options=[
                                            {"label": "Shared",
                                             "value": "shared"},
                                            {"label": "Personal",
                                             "value": "personal"},
                                        ],
                                        value=default_split,
                                        inline=True,
                                        className="mb-0 me-4 fw-medium",
                                    ),
                                    html.Span("Year:",
                                              className="fw-bold me-2 text-muted"),
                                    dcc.Dropdown(
                                        id=ids.year_dropdown,
                                        options=years_options,
                                        value=current_year,
                                        clearable=False,
                                        style={"width": "130px"},
                                        className="me-auto"
                                    ),
                                    dbc.Button(
                                        [html.I(
                                            className="fas fa-file-export me-2"),
                                         "Export to Sheets"],
                                        id=ids.export_btn,
                                        color="primary",
                                    ),
                                ],
                                className="d-flex align-items-center bg-white p-3 rounded shadow-sm w-100",
                            )
                        ],
                        xs=12,
                    )
                ],
                className="mb-4",
            ),

            # --- ROW 2: 12 MONTHS TABS ---
            dbc.Row(
                [
                    dbc.Col(
                        dbc.Tabs(
                            children=_month_tabs_children(),
                            id=ids.month_tabs,
                            active_tab=current_month,
                        )
                    )
                ],
                className="mb-4",
            ),

            # --- ROW 3: KPI CARDS ---
            dbc.Row(
                [
                    dbc.Col(_create_kpi_card("Total Spent", ids.kpi_spent,
                                             "primary"), md=4, xs=12,
                            className="mb-4 mb-md-0"),
                    dbc.Col(_create_kpi_card("Budget Pacing", ids.kpi_pacing,
                                             "info"), md=4, xs=12,
                            className="mb-4 mb-md-0"),
                    dbc.Col(_create_kpi_card("Monthly Average", ids.kpi_average,
                                             "secondary"), md=4, xs=12),
                ],
                className="mb-4",
            ),

            # --- ROW 4: CHARTS ---
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                dcc.Graph(
                                    id=ids.pie_graph,
                                    config={"displayModeBar": False},
                                )
                            ],
                            className="bg-white p-3 rounded shadow-sm h-100",
                        ),
                        md=6,
                        xs=12,
                        className="mb-4 mb-md-0",
                    ),
                    dbc.Col(
                        html.Div(
                            [
                                dcc.Graph(
                                    id=ids.trends_graph,
                                    config={"displayModeBar": False},
                                )
                            ],
                            className="bg-white p-3 rounded shadow-sm h-100",
                        ),
                        md=6,
                        xs=12,
                    ),
                ],
                className="mb-4",
            ),

            # --- ROW 5: TRANSACTIONS TABLE & PAYER SUMMARY ---
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.H5("Transactions",
                                        className="mb-3 fw-bold text-muted"),
                                expenses_datatable(
                                    data=[],
                                    categories=CATEGORIES,
                                    table_id=ids.table,
                                    style_header={'backgroundColor': '#f8f9fa',
                                                  'fontWeight': 'bold'},
                                    style_data_conditional=[
                                        {'if': {'row_index': 'odd'},
                                         'backgroundColor': '#f2f2f2'}],
                                ),

                                # NEW: Payer Summary Section
                                html.Hr(className="my-4"),
                                html.H6("Monthly Totals by Payer",
                                        className="mb-3 fw-bold text-muted"),
                                html.Div(id=ids.payer_summary_div)
                            ],
                            className="bg-white p-4 rounded shadow-sm",
                        ),
                        xs=12
                    )
                ]
            ),
        ],
    )


def register_expenses_callbacks(app: Dash) -> None:
    ids = _Ids()

    # Callback 1: Update Table
    @app.callback(
        Output(ids.table, "data"),
        Input(ids.year_dropdown, "value"),
        Input(ids.month_tabs, "active_tab"),
        Input(ids.split_radio, "value"),
    )
    def _update_table(selected_year: int, active_month_str: str,
                      split_value: str):
        if not selected_year or not active_month_str:
            return []

        month = int(active_month_str)
        split_value = split_value or "shared"

        df_month = fetch_raw_expenses(selected_year, month, split_value)
        if not df_month.empty and "date" in df_month.columns:
            df_month["date"] = df_month["date"].dt.strftime("%Y-%m-%d")

        return df_month.to_dict("records")

    # Callback 2: Update Charts and KPIs using Pandas aggregation
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
            return go.Figure(), go.Figure(), "₪0", "₪0", "fw-bold", "₪0"

        split_value = split_value or "shared"
        month = int(active_month_str)

        # 1. Fetch entire year in one fast call
        yearly_df = fetch_yearly_data(selected_year, split_value)

        # 2. Monthly Trend Data Aggregation
        trend_summary = {}
        if not yearly_df.empty:
            yearly_df['month_num'] = yearly_df['date'].dt.strftime('%m')
            monthly_sums = yearly_df.groupby('month_num')['amount'].sum()
            trend_summary = monthly_sums.to_dict()  # e.g., {'01': 500, '02': 1200}

        trends_fig = monthly_trends_bar_chart(summary_dict=trend_summary,
                                              year=selected_year)

        # 3. Pie Chart Data (Use table data if available, else filter yearly_df for the month)
        if table_data:
            df_pie = pd.DataFrame(table_data)
        else:
            if not yearly_df.empty:
                df_pie = yearly_df[yearly_df['date'].dt.month == month]
            else:
                df_pie = pd.DataFrame()

        pie_fig = category_pie_chart(df=df_pie)

        # 4. KPIs
        month_str_padded = f"{month:02d}"
        total_spent = float(trend_summary.get(month_str_padded, 0.0))
        text_spent = f"₪{total_spent:,.0f}"

        # Budget Pacing
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

        # Monthly Average
        historical_trend = list(trend_summary.values())
        non_zero_months = [float(v) for v in historical_trend if float(v) > 0]
        avg_monthly = float(sum(non_zero_months) / len(
            non_zero_months)) if non_zero_months else 0.0
        text_average = f"₪{avg_monthly:,.0f}"

        return pie_fig, trends_fig, text_spent, text_pacing, pacing_class, text_average

    # Callback 3: Update the Payer Totals (Michael vs Ori)
    @app.callback(
        Output(ids.payer_summary_div, "children"),
        Input(ids.year_dropdown, "value"),
        Input(ids.month_tabs, "active_tab"),
        Input(ids.table, "data"),
    )
    def _update_payer_summary(selected_year: int, active_month_str: str,
                              table_data: list[dict]):
        if not selected_year or not active_month_str:
            return ""

        month = int(active_month_str)

        # --- Fetch all three data sources in parallel-friendly order ---
        df_shared = fetch_raw_expenses(selected_year, month, split="shared")
        personal_totals = fetch_personal_totals(selected_year, month)
        settlement = fetch_settlement(selected_year, month)

        if df_shared.empty and not personal_totals:
            return html.Div("No transactions this month.", className="text-muted")

        # --- Shared paid per person (what each physically paid, not their fair share) ---
        shared_paid: dict[str, float] = {}
        if not df_shared.empty:
            shared_paid = df_shared.groupby("payer")["amount"].sum().to_dict()

        # --- Determine all payers present this month ---
        payers = sorted(set(list(shared_paid.keys()) + list(personal_totals.keys())))

        # --- Build one card per person ---
        cards = []
        for p in payers:
            paid_shared = shared_paid.get(p, 0.0)
            paid_personal = personal_totals.get(p, 0.0)

            # Net total after settlement = fair share of shared + personal
            total_shared_all = sum(shared_paid.values())
            fair_share = total_shared_all / 2.0
            net_total = fair_share + paid_personal

            # --- Settlement line ---
            is_balanced = settlement.get("balanced", False)
            if is_balanced or settlement.get("amount", 0.0) == 0.0:
                settlement_line = html.Div(
                    "Settled ✓",
                    className="fw-medium text-success",
                )
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
                        [
                            html.Span("Shared paid:", className="text-muted me-2"),
                            html.Span(f"₪{paid_shared:,.0f}", className="fw-medium text-primary"),
                        ],
                        className="d-flex justify-content-between mb-1",
                    ),
                    html.Div(
                        [
                            html.Span("Personal:", className="text-muted me-2"),
                            html.Span(f"₪{paid_personal:,.0f}", className="fw-medium text-secondary"),
                        ],
                        className="d-flex justify-content-between mb-1",
                    ),
                    html.Div(
                        [
                            html.Span("Settlement:", className="text-muted me-2"),
                            settlement_line,
                        ],
                        className="d-flex justify-content-between mb-1",
                    ),
                    html.Hr(className="my-2"),
                    html.Div(
                        [
                            html.Span("Net Total:", className="fw-bold text-dark me-2"),
                            html.Span(f"₪{net_total:,.0f}", className="fw-bold text-dark"),
                        ],
                        className="d-flex justify-content-between",
                    ),
                ]),
                className="shadow-sm border-0 me-3 mb-2",
                style={"backgroundColor": "#f8f9fa", "minWidth": "240px"},
            )
            cards.append(card)

        return html.Div(cards, className="d-flex flex-wrap")