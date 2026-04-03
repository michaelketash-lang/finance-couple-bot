from __future__ import annotations

import os

from dash import Dash, Input, Output, html
import dash_bootstrap_components as dbc

from layouts.budget_layout import get_budget_layout, register_budget_callbacks
from layouts.expenses_layout import get_expenses_layout
from layouts.expenses_callbacks import register_expenses_callbacks
from layouts.investments_layout import get_investments_layout, register_investments_callbacks

PAYER_1 = os.getenv('PAYER_1', 'Michael')
PAYER_2 = os.getenv('PAYER_2', 'Ori')



app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.LUX],
    suppress_callback_exceptions=False,
)
server = app.server  # Gunicorn/Render compatibility.

app.layout = html.Div(
    className="bg-light pb-5",  # Added subtle background and bottom padding
    children=[
        dbc.Container(
            fluid=True,
            className="p-4",  # Added padding around the whole dashboard
            children=[
                html.H2(
                    f"{PAYER_1} & {PAYER_2} Finance Dashboard",
                    className="text-start my-4",
                ),
                dbc.Tabs(
                    [
                        dbc.Tab(label="Expenses", tab_id="expenses"),
                        dbc.Tab(label="Budget", tab_id="budget"),
                        dbc.Tab(label="Investment", tab_id="investments"),
                    ],
                    id="main-nav-tabs",
                    active_tab="expenses",
                    className="mb-4",  # Added margin below the tabs for breathing room
                ),
                html.Div(id="page-expenses", children=get_expenses_layout()),
                html.Div(
                    id="page-budget",
                    children=get_budget_layout(),
                    style={"display": "none"},
                ),
                html.Div(
                    id="page-investments",
                    children=get_investments_layout(),
                    style={"display": "none"},
                ),
            ],
        )
    ],
)


@app.callback(
    Output("page-expenses", "style"),
    Output("page-budget", "style"),
    Output("page-investments", "style"),
    Input("main-nav-tabs", "active_tab"),
)
def _toggle_pages(active_tab: str):
    if active_tab == "budget":
        return {"display": "none"}, {"display": "block"}, {"display": "none"}
    if active_tab == "investments":
        return {"display": "none"}, {"display": "none"}, {"display": "block"}
    return {"display": "block"}, {"display": "none"}, {"display": "none"}


register_expenses_callbacks(app)
register_budget_callbacks(app)
register_investments_callbacks(app)


if __name__ == "__main__":
    app.run(debug=True, port=8050)  # Fixed the obsolete run_server bug!