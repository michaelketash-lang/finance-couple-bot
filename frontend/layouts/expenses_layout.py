from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import calendar

import pandas as pd
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, dcc, html

from components.charts import category_pie_chart, monthly_trends_bar_chart
from components.tables import expenses_datatable
from api_client import fetch_raw_expenses, fetch_yearly_data, CATEGORIES


@dataclass(frozen=True)
class _Ids:
    split_radio: str = "expenses-split-radio"
    year_dropdown: str = "expenses-year-dropdown"
    month_tabs: str = "expenses-month-tabs"
    table: str = "expenses-table"
    edits_store: str = "expenses-edits-store"
    pie_graph: str = "expenses-category-pie"
    trends_graph: str = "expenses-monthly-trends"
    export_btn: str = "expenses-export-btn"


def _month_tabs_children() -> list[dbc.Tab]:
    """Always display 12 tabs for Jan through Dec."""
    children: list[dbc.Tab] = []
    for m in range(1, 13):
        label = calendar.month_abbr[m]  # 'Jan', 'Feb', etc.
        children.append(dbc.Tab(label=label, tab_id=str(m)))
    return children


def get_expenses_layout() -> dbc.Container:
    """Constructs the layout with Year Dropdown and 12-Month Tabs."""
    ids = _Ids()

    current_year = datetime.today().year
    current_month = str(datetime.today().month)
    default_split = "shared"

    # Generate years for the dropdown (e.g., 2023 to next year)
    years_options = [{"label": str(y), "value": y} for y in
                     range(2023, current_year + 2)]

    return dbc.Container(
        fluid=True,
        children=[
            dcc.Store(id=ids.edits_store, data={}, storage_type="memory"),

            # Filters row: Split Radio + Year Dropdown + Export
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(
                                [
                                    html.Span("Expense Type:",
                                              className="fw-bold me-3"),
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
                                        className="mb-0 me-4",
                                    ),
                                    html.Span("Year:",
                                              className="fw-bold me-2"),
                                    dcc.Dropdown(
                                        id=ids.year_dropdown,
                                        options=years_options,
                                        value=current_year,
                                        clearable=False,
                                        style={"width": "120px"},
                                        className="me-auto"
                                    ),
                                    dbc.Button(
                                        "Export to Google Sheets",
                                        id=ids.export_btn,
                                        color="dark",
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

            # 12 Months Tabs
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

            # Charts Row
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.H5("Category Breakdown", className="mb-3"),
                                dcc.Graph(
                                    id=ids.pie_graph,
                                    config={"displayModeBar": False},
                                )
                            ],
                            className="bg-white p-4 rounded shadow-sm h-100",
                        ),
                        md=6,
                        xs=12,
                        className="mb-4 mb-md-0",
                    ),
                    dbc.Col(
                        html.Div(
                            [
                                html.H5("Yearly Trend", className="mb-3"),
                                dcc.Graph(
                                    id=ids.trends_graph,
                                    config={"displayModeBar": False},
                                )
                            ],
                            className="bg-white p-4 rounded shadow-sm h-100",
                        ),
                        md=6,
                        xs=12,
                    ),
                ],
                className="mb-4",
            ),

            # DataTable Row
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.H5("Transactions", className="mb-3"),
                                expenses_datatable(
                                    data=[],  # Will be populated by callback
                                    categories=CATEGORIES,
                                    table_id=ids.table,
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

    @app.callback(
        Output(ids.pie_graph, "figure"),
        Output(ids.trends_graph, "figure"),
        Input(ids.year_dropdown, "value"),
        Input(ids.month_tabs, "active_tab"),
        Input(ids.split_radio, "value"),
        Input(ids.table, "data"),
    )
    def _update_charts(selected_year: int, active_month_str: str,
                       split_value: str, table_data: list[dict]):
        if not selected_year or not active_month_str:
            return go.Figure(), go.Figure()

        split_value = split_value or "shared"

        # Update Pie Chart (Based on current table data / selected month)
        df_month = pd.DataFrame(
            table_data) if table_data else fetch_raw_expenses(selected_year,
                                                              int(active_month_str),
                                                              split_value)
        pie_fig = category_pie_chart(df_month)

        # Update Trends Chart (Fetch the whole year)
        df_yearly = fetch_yearly_data(selected_year, split_value)
        trends_fig = monthly_trends_bar_chart(df_yearly, selected_year)

        return pie_fig, trends_fig