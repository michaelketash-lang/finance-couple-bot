"""
layouts/expenses_layout.py
==========================

Dash layout definition for the Expenses tab.

Defines the ``_Ids`` dataclass of all component IDs used by both the layout
and its callbacks, and builds the full page structure: controls bar, month
tabs, KPI cards, charts, transactions table, and payer summary section.
"""

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
    """Frozen dataclass holding all Dash component IDs for the Expenses tab.

    Shared between ``expenses_layout.py`` and ``expenses_callbacks.py`` to
    ensure component IDs stay in sync without string duplication.
    """
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
    """Build a KPI summary card with a colored top border.

    :param title: Label shown in the card header (e.g. ``'Total Spent'``).
    :param id: Dash component ID for the value ``html.H3`` element.
    :param color: Bootstrap color name (e.g. ``'primary'``, ``'info'``).
    :returns: A ``dbc.Card`` component with a placeholder ``₪0`` value.
    """
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
    """Build the list of 12 month tab components.

    :returns: A list of ``dbc.Tab`` objects, one per calendar month.
    """
    children: list[dbc.Tab] = []
    for m in range(1, 13):
        label = calendar.month_abbr[m]
        children.append(
            dbc.Tab(label=label, tab_id=str(m), className="fw-medium",
                    label_style={"padding": "6px 8px", "fontSize": "0.78rem"}))
    return children


def get_expenses_layout() -> dbc.Container:
    """Build and return the full Expenses tab layout.

    Includes four ``dcc.Store`` components for state management and five
    layout rows: controls, month tabs, KPI cards, charts, and the
    transactions table with payer summary.

    :returns: A ``dbc.Container`` with all Expenses tab components.
    """
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

            # --- ROW 1: 12 MONTHS TABS + YEAR DROPDOWN + SHEETS EXPORT ICON ---
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                dbc.Tabs(
                                    children=_month_tabs_children(),
                                    id=ids.month_tabs,
                                    active_tab=current_month,
                                    className="flex-grow-1",
                                ),
                                dcc.Dropdown(
                                    id=ids.year_dropdown,
                                    options=years_options,
                                    value=current_year,
                                    clearable=False,
                                    # Added explicit marginRight here to guarantee the gap
                                    style={"width": "110px", "minWidth": "110px", "marginRight": "16px"},
                                    className="ms-3",
                                ),
                                # Google Sheets icon button
                                dbc.Button(
                                    html.Img(
                                        src='data:image/svg+xml;utf8,<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="%2334A853"/><path d="M14 2v6h6" fill="%231E8E3E"/><rect x="8" y="9" width="8" height="1.5" rx="0.5" fill="white"/><rect x="8" y="12" width="8" height="1.5" rx="0.5" fill="white"/><rect x="8" y="15" width="8" height="1.5" rx="0.5" fill="white"/></svg>',
                                        style={"width": "40px", "height": "40px"}  # Increased to 40px
                                    ),
                                    id=ids.export_btn,
                                    color="link",
                                    className="p-1",  # Removed previous margin classes so the dropdown handles the gap
                                    title="Export to Google Sheets",
                                    style={"lineHeight": "1"},
                                ),
                                html.Div(id="export-status", className="ms-2 fw-medium",
                                         style={"fontSize": "0.8rem"}),
                            ],
                            className="d-flex align-items-center",
                        ),
                        xs=12,
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
                                html.Div(
                                    [
                                        html.H5("Transactions", className="mb-0 fw-bold text-muted"),
                                        dbc.RadioItems(
                                            id=ids.split_radio,
                                            options=[
                                                {"label": "Shared",  "value": "shared"},
                                                {"label": PAYER_1,   "value": PAYER_1.lower()},
                                                {"label": PAYER_2,   "value": PAYER_2.lower()},
                                            ],
                                            value=default_split,
                                            inline=True,
                                            className="mb-0 fw-medium",
                                        ),
                                    ],
                                    className="d-flex align-items-center justify-content-between mb-3",
                                ),
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
