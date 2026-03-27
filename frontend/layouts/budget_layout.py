from __future__ import annotations

import pandas as pd
import dash_bootstrap_components as dbc
from dash import html

from components.tables import budgets_datatable
from api_client import fetch_all_budgets


def get_budget_layout() -> dbc.Container:
    """
    Budget goals UI.
    Fetches live data from the Flask API.
    """
    # Fetch data directly from the backend API
    df_budgets = fetch_all_budgets()

    table = budgets_datatable(
        data=df_budgets.to_dict("records"),
        table_id="budgets-table",
    )

    return dbc.Container(
        fluid=True,
        children=[
            dbc.Row(
                [
                    dbc.Col(
                        html.Div(
                            [
                                html.H4("Budget Goals", className="mb-2"),
                                html.P(
                                    "Set a monthly target per category.",
                                    className="text-muted mb-4",
                                ),
                                table,
                            ],
                            className="bg-white p-4 rounded shadow-sm",
                        ),
                        xs=12,
                    )
                ],
                className="mb-4",
            )
        ],
    )