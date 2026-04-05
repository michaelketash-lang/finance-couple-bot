"""
app.py
======

Main Dash application entry point for the finance bot frontend.

Defines a permanent left sidebar for navigation (Expenses, Budget, Investment)
with the app logo and title at the top, and mounts all sub-module callbacks.

The ``server`` attribute is exposed for Gunicorn/Render deployment.
"""

from __future__ import annotations

import os

from dash import Dash, Input, Output, ctx, html, no_update
import dash_bootstrap_components as dbc

from layouts.budget_layout import get_budget_layout, register_budget_callbacks
from layouts.expenses_layout import get_expenses_layout
from layouts.expenses_callbacks import register_expenses_callbacks
from layouts.investments_layout import get_investments_layout
from layouts.investments_callbacks import register_investments_callbacks

PAYER_1 = os.getenv('PAYER_1', 'Michael')
PAYER_2 = os.getenv('PAYER_2', 'Ori')

SHOW = {"display": "block"}
HIDE = {"display": "none"}



app = Dash(
    __name__,
    external_stylesheets=[dbc.themes.LUX],
    suppress_callback_exceptions=False,
)
server = app.server  # Gunicorn/Render compatibility.

# ── Sidebar styles ──────────────────────────────────────────────────────────
SIDEBAR_STYLE = {
    "position": "fixed",
    "top": 0,
    "left": 0,
    "bottom": 0,
    "width": "180px",
    "padding": "24px 16px",
    "backgroundColor": "#ffffff",
    "borderRight": "1px solid #e2e8f0",
    "display": "flex",
    "flexDirection": "column",
    "zIndex": 1000,
}

CONTENT_STYLE = {
    "marginLeft": "180px",
    "padding": "32px 24px",
    "backgroundColor": "#f8f9fa",
    "minHeight": "100vh",
}

NAV_LINK_STYLE = {
    "color": "#64748b",
    "borderRadius": "6px",
    "fontWeight": "500",
    "padding": "10px 14px",
    "marginBottom": "4px",
    "textDecoration": "none",
}

NAV_LINK_ACTIVE_STYLE = {
    **NAV_LINK_STYLE,
    "backgroundColor": "#f1f5f9",
    "color": "#1a2e3b",
}

app.layout = html.Div(
    children=[

        # ── Permanent left sidebar ──────────────────────────────────────────
        html.Div(
            style=SIDEBAR_STYLE,
            children=[
                # Logo
                html.Img(
                    src="/assets/logo.png",
                    style={"width": "150px", "marginBottom": "28px"},
                ),

                # Nav links
                html.Div(
                    [
                        html.A("Expenses",   id="nav-expenses",    href="#",
                               style=NAV_LINK_ACTIVE_STYLE, className="d-block"),
                        html.A("Budget",     id="nav-budget",      href="#",
                               style=NAV_LINK_STYLE, className="d-block"),
                        html.A("Investment", id="nav-investments", href="#",
                               style=NAV_LINK_STYLE, className="d-block"),
                    ]
                ),
            ],
        ),

        # ── Main content area ───────────────────────────────────────────────
        html.Div(
            style=CONTENT_STYLE,
            children=[
                html.Div(id="page-expenses",    children=get_expenses_layout()),
                html.Div(id="page-budget",      children=get_budget_layout(),        style=HIDE),
                html.Div(id="page-investments", children=_investments_placeholder(), style=HIDE),
            ],
        ),
    ]
)


@app.callback(
    Output("page-expenses",    "style"),
    Output("page-budget",      "style"),
    Output("page-investments", "style"),
    Output("nav-expenses",     "style"),
    Output("nav-budget",       "style"),
    Output("nav-investments",  "style"),
    Input("nav-expenses",    "n_clicks"),
    Input("nav-budget",      "n_clicks"),
    Input("nav-investments", "n_clicks"),
    prevent_initial_call=True,
)
def _switch_page(n_exp, n_bud, n_inv):
    """Switch the visible page and highlight the active nav link."""
    triggered = ctx.triggered_id

    if triggered == "nav-budget":
        return HIDE, SHOW, HIDE, NAV_LINK_STYLE, NAV_LINK_ACTIVE_STYLE, NAV_LINK_STYLE
    if triggered == "nav-investments":
        return HIDE, HIDE, SHOW, NAV_LINK_STYLE, NAV_LINK_STYLE, NAV_LINK_ACTIVE_STYLE
    return SHOW, HIDE, HIDE, NAV_LINK_ACTIVE_STYLE, NAV_LINK_STYLE, NAV_LINK_STYLE


register_expenses_callbacks(app)
register_budget_callbacks(app)
register_investments_callbacks(app)


if __name__ == "__main__":
    app.run(debug=True, port=8050)
