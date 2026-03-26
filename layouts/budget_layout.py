from __future__ import annotations

import pandas as pd
import dash_bootstrap_components as dbc
from dash import html

from components.tables import budgets_datatable
from mock_data import get_mock_budgets_df


MOCK_BUDGETS_DF = get_mock_budgets_df()
MOCK_BUDGETS_DF["monthly_target"] = pd.to_numeric(
    MOCK_BUDGETS_DF["monthly_target"], errors="coerce"
).fillna(0.0)


def get_budget_layout() -> dbc.Container:
    """
    Budget goals UI (mock data only).

    This is an editable DataTable that lets you set a target budget per category.
    Persistence can be added later by wiring callbacks + a REST API.
    """
    table = budgets_datatable(
        data=MOCK_BUDGETS_DF.to_dict("records"),
        table_id="budgets-table",
    )

    return dbc.Container(
        fluid=True,
        children=[
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.H3("Budget Goals", className="mb-2"),
                            html.P(
                                "Set a monthly target per category (mock UI — persistence TBD).",
                                className="text-muted",
                            ),
                            table,
                        ],
                        xs=12,
                    )
                ]
            )
        ],
    )

