from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import calendar
import os

import dash_bootstrap_components as dbc
from dash import Dash, dcc, html

from components.charts import CATEGORIES
from components.tables import expenses_datatable

PAYER_1 = os.getenv('PAYER_1', 'Michael')
PAYER_2 = os.getenv('PAYER_2', 'Ori')


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
    ids_store: str = "expenses-ids-store"
    reference_store: str = "expenses-reference-store"
    edit_status: str = "expenses-edit-status"
    # Payer Summary
    payer_summary_div: str = "expenses-payer-summary"
    # BFF master store — holds all fetched data for the selected month
    dashboard_store: str = "expenses-dashboard-store"


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
            dcc.Store(id=ids.dashboard_store, data={}, storage_type="memory"),
            dcc.Store(id=ids.edits_store, data={}, storage_type="memory"),
            dcc.Store(id=ids.ids_store, data=[], storage_type="memory"),
            dcc.Store(id=ids.reference_store, data=[], storage_type="memory"),

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
                                            {"label": "Shared",     "value": "shared"},
                                            {"label": PAYER_1,      "value": PAYER_1.lower()},
                                            {"label": PAYER_2,      "value": PAYER_2.lower()},
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
                                        [html.I(className="fas fa-file-export me-2"),
                                         "Export to Sheets"],
                                        id=ids.export_btn,
                                        color="primary",
                                    ),
                                    html.Div(id="export-status", className="ms-3 fw-medium",
                                             style={"fontSize": "0.875rem"}),
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
                            [dcc.Graph(id=ids.pie_graph, config={"displayModeBar": False})],
                            className="bg-white p-3 rounded shadow-sm h-100",
                        ),
                        md=6, xs=12, className="mb-4 mb-md-0",
                    ),
                    dbc.Col(
                        html.Div(
                            [dcc.Graph(id=ids.trends_graph, config={"displayModeBar": False})],
                            className="bg-white p-3 rounded shadow-sm h-100",
                        ),
                        md=6, xs=12,
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
                                html.Div(
                                    id=ids.edit_status,
                                    className="mt-2 text-success fw-medium",
                                    style={"fontSize": "0.875rem", "minHeight": "20px"},
                                ),
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
