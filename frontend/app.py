from __future__ import annotations

from dash import Dash, Input, Output, html
import dash_bootstrap_components as dbc

from layouts.budget_layout import get_budget_layout
from layouts.expenses_layout import get_expenses_layout, register_expenses_callbacks


def _investments_placeholder() -> html.Div:
    return html.Div(
        [
            html.H4("Investment dashboard", className="mb-2"),
            html.P("Placeholder UI. Connect future investments API + charts here."),
        ]
    )


app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.LUX],
    suppress_callback_exceptions=False,
)
server = app.server  # Gunicorn/Render compatibility.

app.layout = html.Div(
    dir="rtl",
    children=[
        dbc.Container(
            fluid=True,
            children=[
                html.H2(
                    "Michael & Partner Finance Dashboard",
                    className="text-center my-3",
                ),
                dbc.Tabs(
                    [
                        dbc.Tab(label="Expenses", tab_id="expenses"),
                        dbc.Tab(label="Budget", tab_id="budget"),
                        dbc.Tab(label="Investment", tab_id="investments"),
                    ],
                    id="main-nav-tabs",
                    active_tab="expenses",
                ),
                html.Div(id="page-expenses", children=get_expenses_layout()),
                html.Div(
                    id="page-budget",
                    children=get_budget_layout(),
                    style={"display": "none"},
                ),
                html.Div(
                    id="page-investments",
                    children=_investments_placeholder(),
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


if __name__ == "__main__":
    app.run_server(debug=True)

