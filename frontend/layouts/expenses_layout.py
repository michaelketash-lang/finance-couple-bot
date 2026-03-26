from __future__ import annotations

from dataclasses import dataclass #to store ids for the callbacks.

import pandas as pd #to store the expenses data.
import dash_bootstrap_components as dbc #to create the layout of the page.
from dash import Dash, Input, Output, State, dcc, html 

from components.charts import category_pie_chart, monthly_trends_bar_chart #to create the charts.
from components.tables import expenses_datatable
from mock_data import CATEGORIES, get_mock_expenses_df #to store the expenses data.


@dataclass(frozen=True) #mapping cant be accidentally changed at runtime.
class _Ids:
    # Keep IDs centralized so callbacks stay readable.
    split_radio: str = "expenses-split-radio"
    month_tabs: str = "expenses-month-tabs"
    table: str = "expenses-table"
    edits_store: str = "expenses-edits-store"
    pie_graph: str = "expenses-category-pie"
    trends_graph: str = "expenses-monthly-trends"
    export_btn: str = "expenses-export-btn"


MOCK_EXPENSES_DF = get_mock_expenses_df()
MOCK_EXPENSES_DF["date"] = pd.to_datetime(MOCK_EXPENSES_DF["date"], errors="coerce")


def _month_ids_sorted() -> list[str]:
    # month_id looks like "2026-03".
    months = MOCK_EXPENSES_DF["date"].dt.to_period("M").dropna().astype(str).unique().tolist()
    return sorted(months)


def _default_month_id() -> str:
    months = _month_ids_sorted()
    return months[0] if months else "2026-01"

#Create the children for the month tabs (January, February, etc.).
def _month_tabs_children() -> list[dbc.Tab]:
    children: list[dbc.Tab] = []
    for month_id in _month_ids_sorted():
        month_dt = pd.to_datetime(f"{month_id}-01", errors="coerce")
        label = month_dt.strftime("%b") if pd.notna(month_dt) else month_id
        children.append(dbc.Tab(label=label, tab_id=month_id))
    return children

#Create the dataframe for the selected month.
def _get_month_df(month_id: str, split_value: str) -> pd.DataFrame:
    period = pd.Period(month_id, freq="M")
    df = MOCK_EXPENSES_DF[
        (MOCK_EXPENSES_DF["split"] == split_value)
        & (MOCK_EXPENSES_DF["date"].dt.to_period("M") == period)
    ].copy()
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    return df

#Create the layout for the expenses page.
def get_expenses_layout() -> dbc.Container:
    ids = _Ids()
    default_month = _default_month_id()

    default_split = "shared"
    df_month = _get_month_df(default_month, default_split)

    table = expenses_datatable(
        data=df_month.to_dict("records"),
        categories=CATEGORIES,
        table_id=ids.table,
    )

    pie_fig = category_pie_chart(df_month)
    trends_fig = monthly_trends_bar_chart(
        MOCK_EXPENSES_DF[MOCK_EXPENSES_DF["split"] == default_split].copy()
    )

    return dbc.Container(
        fluid=True,
        children=[
            # Persist DataTable edits per (split, month) key.
            dcc.Store(id=ids.edits_store, data={}, storage_type="memory"),
            
            # Filters row: Shared/Personal toggle + export button (Card Style)
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.Div(
                                [
                                    html.Span("Expense Type:", className="fw-bold me-3"),
                                    dbc.RadioItems(
                                        id=ids.split_radio,
                                        options=[
                                            {"label": "Shared", "value": "shared"},
                                            {"label": "Personal", "value": "personal"},
                                        ],
                                        value=default_split,
                                        inline=True,
                                        className="mb-0", # Remove default bottom margin
                                    ),
                                    dbc.Button(
                                        "Export to Google Sheets",
                                        id=ids.export_btn,
                                        color="dark",
                                        className="ms-auto", # Push to the right
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
            
            # Month subtabs row
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
            
            # Analytics row: pie + monthly trend (Cards Style)
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
                        className="mb-4 mb-md-0", # Bottom margin on mobile, none on desktop
                    ),
                    dbc.Col(
                        html.Div(
                            [
                                html.H5("Monthly Trend", className="mb-3"),
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
            
            # Editable table (Card Style)
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

        # Load previously edited rows if they exist.
        store_data = store_data or {}
        key = f"{split_value}|{active_month_id}"
        if key in store_data:
            return store_data[key]

        # Otherwise fall back to mock defaults.
        df_month = _get_month_df(active_month_id, split_value)
        return df_month.to_dict("records")

    @app.callback(
        Output(ids.edits_store, "data"),
        Input(ids.table, "data"),
        State(ids.month_tabs, "active_tab"),
        State(ids.split_radio, "value"),
        State(ids.edits_store, "data"),
    )
    def _save_table_edits(table_data: list[dict], active_month_id: str, split_value: str, store_data: dict):
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
    def _update_charts(active_month_id: str, split_value: str, table_data: list[dict]):
        active_month_id = active_month_id or _default_month_id()
        split_value = split_value or "shared"

        # Use the edited table values for the selected month.
        edited_month_df = pd.DataFrame(table_data) if table_data else _get_month_df(active_month_id, split_value)
        if not edited_month_df.empty and "date" in edited_month_df.columns:
            edited_month_df["date"] = pd.to_datetime(edited_month_df["date"], errors="coerce")

        # Pie reflects only the selected month.
        pie_fig = category_pie_chart(edited_month_df)

        # Trends reflect all months; replace selected month with edited month.
        all_split_df = MOCK_EXPENSES_DF[MOCK_EXPENSES_DF["split"] == split_value].copy()
        period = pd.Period(active_month_id, freq="M")

        selected_mask = all_split_df["date"].dt.to_period("M") == period
        base_other_months = all_split_df.loc[~selected_mask].copy()

        # If edited_month_df is empty, fall back to original selected month.
        if edited_month_df.empty:
            edited_month_for_merge = all_split_df.loc[selected_mask].copy()
        else:
            edited_month_for_merge = edited_month_df.copy()
            edited_month_for_merge["date"] = pd.to_datetime(edited_month_for_merge["date"], errors="coerce")

        edited_month_for_merge["split"] = split_value
        combined = pd.concat([base_other_months, edited_month_for_merge], ignore_index=True)

        trends_fig = monthly_trends_bar_chart(combined)
        return pie_fig, trends_fig