from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from dateutil.relativedelta import relativedelta

import pandas as pd
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, dcc, html

from components.charts import category_pie_chart, monthly_trends_bar_chart
from components.tables import expenses_datatable
from api_client import fetch_raw_expenses, fetch_recent_months_data, CATEGORIES


@dataclass(frozen=True)
class _Ids:
    split_radio: str = "expenses-split-radio"
    month_tabs: str = "expenses-month-tabs"
    table: str = "expenses-table"
    edits_store: str = "expenses-edits-store"
    pie_graph: str = "expenses-category-pie"
    trends_graph: str = "expenses-monthly-trends"
    export_btn: str = "expenses-export-btn"


def _get_recent_month_ids(num_months: int = 6) -> list[str]:
    """Generates a list of recent month IDs in YYYY-MM format."""
    today = datetime.today()
    return [(today - relativedelta(months=i)).strftime("%Y-%m") for i in
            reversed(range(num_months))]


def _default_month_id() -> str:
    """Returns the current month in YYYY-MM format."""
    return datetime.today().strftime("%Y-%m")


def _month_tabs_children() -> list[dbc.Tab]:
    """Dynamically creates UI tabs for the last 6 months."""
    children: list[dbc.Tab] = []
    for month_id in _get_recent_month_ids():
        month_dt = pd.to_datetime(f"{month_id}-01", errors="coerce")
        label = month_dt.strftime("%b %Y") if pd.notna(month_dt) else month_id
        children.append(dbc.Tab(label=label, tab_id=month_id))
    return children


def _get_month_df(month_id: str, split_value: str) -> pd.DataFrame:
    """Parses the month ID and fetches live data from the API."""
    year, month = int(month_id.split("-")[0]), int(month_id.split("-")[1])
    df = fetch_raw_expenses(year, month, split_value)
    if not df.empty and "date" in df.columns:
        df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return df


def get_expenses_layout() -> dbc.Container:
    """Constructs the initial layout using live API data."""
    ids = _Ids()
    default_month = _default_month_id()
    default_split = "shared"

    # Fetch initial data
    df_month = _get_month_df(default_month, default_split)
    df_trends = fetch_recent_months_data(months_back=6, split=default_split)

    table = expenses_datatable(
        data=df_month.to_dict("records"),
        categories=CATEGORIES,
        table_id=ids.table,
    )

    pie_fig = category_pie_chart(df_month)
    trends_fig = monthly_trends_bar_chart(df_trends)

    return dbc.Container(
        fluid=True,
        children=[
            dcc.Store(id=ids.edits_store, data={}, storage_type="memory"),

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
                                        className="mb-0",
                                    ),
                                    dbc.Button(
                                        "Export to Google Sheets",
                                        id=ids.export_btn,
                                        color="dark",
                                        className="ms-auto",
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

            dbc.Row(
                [
                    dbc.Col(
                        dbc.Tabs(
                            children=_month_tabs_children(),
                            id=ids.month_tabs,
                            active_tab=default_month,
                        )
                    )
                ],
                className="mb-4",
            ),

            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.H5("Category Breakdown", className="mb-3"),
                                dcc.Graph(
                                    id=ids.pie_graph,
                                    figure=pie_fig,
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
                                html.H5("6-Month Trend", className="mb-3"),
                                dcc.Graph(
                                    id=ids.trends_graph,
                                    figure=trends_fig,
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

            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.H5("Transactions", className="mb-3"),
                                table
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
        Input(ids.month_tabs, "active_tab"),
        Input(ids.split_radio, "value"),
        State(ids.edits_store, "data"),
    )
    def _update_table(active_month_id: str, split_value: str, store_data: dict):
        active_month_id = active_month_id or _default_month_id()
        split_value = split_value or "shared"

        store_data = store_data or {}
        key = f"{split_value}|{active_month_id}"
        if key in store_data:
            return store_data[key]

        df_month = _get_month_df(active_month_id, split_value)
        return df_month.to_dict("records")

    @app.callback(
        Output(ids.edits_store, "data"),
        Input(ids.table, "data"),
        State(ids.month_tabs, "active_tab"),
        State(ids.split_radio, "value"),
        State(ids.edits_store, "data"),
    )
    def _save_table_edits(table_data: list[dict], active_month_id: str,
                          split_value: str, store_data: dict):
        active_month_id = active_month_id or _default_month_id()
        split_value = split_value or "shared"

        store_data = store_data or {}
        key = f"{split_value}|{active_month_id}"
        store_data[key] = table_data
        return store_data

    @app.callback(
        Output(ids.pie_graph, "figure"),
        Output(ids.trends_graph, "figure"),
        Input(ids.month_tabs, "active_tab"),
        Input(ids.split_radio, "value"),
        Input(ids.table, "data"),
    )
    def _update_charts(active_month_id: str, split_value: str,
                       table_data: list[dict]):
        active_month_id = active_month_id or _default_month_id()
        split_value = split_value or "shared"

        edited_month_df = pd.DataFrame(
            table_data) if table_data else _get_month_df(active_month_id,
                                                         split_value)
        if not edited_month_df.empty and "date" in edited_month_df.columns:
            edited_month_df["date"] = pd.to_datetime(edited_month_df["date"],
                                                     errors="coerce")

        pie_fig = category_pie_chart(edited_month_df)

        # Re-fetch the 6-month historical data directly from the API
        # so the trend chart updates instantly when swapping Personal/Shared
        df_trends = fetch_recent_months_data(months_back=6, split=split_value)
        trends_fig = monthly_trends_bar_chart(df_trends)

        return pie_fig, trends_fig