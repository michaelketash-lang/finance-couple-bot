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
from api_client import fetch_raw_expenses, fetch_yearly_summary, \
    fetch_yearly_data, fetch_budget_pacing


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


# --- UI Construction Functions ---

def _create_kpi_card(title: str, id: str, color: str) -> dbc.Card:
    """Creates a stylized, colored KPI card."""
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
        # Luxe Bootstrap color variables
    )


def _month_tabs_children() -> list[dbc.Tab]:
    """Always display 12 tabs for Jan through Dec."""
    children: list[dbc.Tab] = []
    for m in range(1, 13):
        label = calendar.month_abbr[m]  # 'Jan', 'Feb', etc.
        children.append(
            dbc.Tab(label=label, tab_id=str(m), className="fw-medium"))
    return children


# --- Main Layout Function ---

def get_expenses_layout() -> dbc.Container:
    """Constructs the stylized and performant Expenses layout."""
    ids = _Ids()

    current_year = datetime.today().year
    current_month = str(datetime.today().month)
    default_split = "shared"

    # Generate years (e.g., 2023 to next year)
    years_options = [{"label": str(y), "value": y} for y in
                     range(2023, current_year + 2)]

    return dbc.Container(
        fluid=True,
        children=[
            dcc.Store(id=ids.edits_store, data={}, storage_type="memory"),

            # --- ROW 1: CONTROLS (Split, Year, Export) ---
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(
                                [
                                    # Split Radio
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
                                    # Year Dropdown
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
                                    # Export Button
                                    dbc.Button(
                                        [html.I(
                                            className="fas fa-file-export me-2"),
                                         "Export to Sheets"],
                                        id=ids.export_btn,
                                        color="primary",  # Colored button
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

            # --- ROW 3: KPI CARDS (Colored) ---
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

            # --- ROW 4: CHARTS (Category & Trend) ---
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

            # --- ROW 5: TRANSACTIONS TABLE (With enhanced styling) ---
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.H5("Transactions",
                                        className="mb-3 fw-bold text-muted"),
                                expenses_datatable(
                                    data=[],  # Will be populated by callback
                                    categories=CATEGORIES,
                                    table_id=ids.table,
                                    # Add direct styling to the table call
                                    style_header={'backgroundColor': '#f8f9fa',
                                                  'fontWeight': 'bold'},
                                    style_data_conditional=[
                                        {'if': {'row_index': 'odd'},
                                         'backgroundColor': '#f2f2f2'}],
                                    # Alternating rows
                                )
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

    # Callback 1: Update the table data ONLY (Triggers first)
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

        # Fetch the monthly raw rows (Acceptable speed for one month)
        df_month = fetch_raw_expenses(selected_year, month, split_value)
        if not df_month.empty and "date" in df_month.columns:
            df_month["date"] = df_month["date"].dt.strftime("%Y-%m-%d")

        return df_month.to_dict("records")

    # Callback 2: Update charts and KPI Cards (Uses FAST summary data)
    @app.callback(
        # Outputs for Charts
        Output(ids.pie_graph, "figure"),
        Output(ids.trends_graph, "figure"),
        # Outputs for Colored KPI Cards
        Output(ids.kpi_spent, "children"),
        Output(ids.kpi_pacing, "children"),
        Output(ids.kpi_pacing, "className"),  # To color the text conditionally
        Output(ids.kpi_average, "children"),
        # Inputs
        Input(ids.year_dropdown, "value"),
        Input(ids.month_tabs, "active_tab"),
        Input(ids.split_radio, "value"),
        Input(ids.table, "data"),  # Used ONLY to detect if edits were made
    )
    def _update_fast_components(selected_year: int, active_month_str: str,
                                split_value: str, table_data: list[dict]):
        if not selected_year or not active_month_str:
            return go.Figure(), go.Figure(), "₪0", "₪0", "fw-bold", "₪0"

        split_value = split_value or "shared"
        month = int(active_month_str)
        month_str_padded = f"{month:02d}"

        # --- FAST PATH: Use pre-aggregated summary ---
        # Instead of recalculating, fetch a tiny JSON of totals.
        summary_data = fetch_yearly_summary(selected_year, split_value)
        category_summary = summary_data.get("category_breakdown", {})
        trend_summary = summary_data.get("monthly_trend", {})

        # --- 1. Update Charts ---

        # If the user just edited the table, table_data has rows,
        # so we must use it to make the Pie Chart react instantly.
        # Otherwise, use the fast summary_dict.
        df_pie = pd.DataFrame(table_data) if table_data else None
        pie_fig = category_pie_chart(df=df_pie, summary_dict=category_summary)

        # Update Trends Chart (Fetch the whole year instantly from summary)
        trends_fig = monthly_trends_bar_chart(summary_dict=trend_summary,
                                              year=selected_year)

        # --- 2. Calculate and Format Colored KPI Cards ---

        # KPI 1: Total Spent (for current month)
        total_spent = float(trend_summary.get(month_str_padded, 0.0))
        text_spent = f"₪{total_spent:,.0f}"

        # KPI 2: Budget Pacing (Fetches small JSON, very fast)
        pacing_data = fetch_budget_pacing(selected_year, month)
        pacing_status = pacing_data.get("status", "On Track")
        pacing_amount = pacing_data.get("amount", 0.0)

        text_pacing = f"₪{pacing_amount:,.0f}"
        if pacing_status == "Over Budget":
            # If over, change text color to Danger (Red)
            pacing_class = "text-danger fw-bold mb-0"
            text_pacing = f"{pacing_status} (₪{pacing_amount:,.0f})"
        else:
            # If on track, use Luxe's Info color
            pacing_class = "text-info fw-bold mb-0"

        # KPI 3: Monthly Average (Calculate from the trend_summary we already have)
        historical_trend = list(trend_summary.values())
        non_zero_months = [float(v) for v in historical_trend if float(v) > 0]
        avg_monthly = float(sum(non_zero_months) / len(
            non_zero_months)) if non_zero_months else 0.0
        text_average = f"₪{avg_monthly:,.0f}"

        return pie_fig, trends_fig, text_spent, text_pacing, pacing_class, text_average