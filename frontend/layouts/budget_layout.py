"""
layouts/budget_layout.py
========================

Dash layout and callbacks for the Budget tab.

Provides the full page layout (year dropdown, month tabs, budget goals table,
and category progress cards) and registers two reactive callbacks:

- ``_update_budget_view`` — fetches budget + actuals on year/month change.
- ``_save_budgets`` — persists edited budget targets on button click.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import datetime

import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, dcc, html

from components.cards import budget_progress_card
from components.tables import budgets_datatable
from api_client import fetch_budget_bff, save_category_budget, CATEGORIES


@dataclass(frozen=True)
class _Ids:
    """Frozen dataclass holding all Dash component IDs for the Budget tab."""
    year_dropdown: str = "budget-year-dropdown"
    month_tabs: str = "budget-month-tabs"
    table: str = "budgets-table"
    progress_cards: str = "budget-progress-cards"
    save_btn: str = "budget-save-btn"
    save_status: str = "budget-save-status"


def _month_tabs_children() -> list[dbc.Tab]:
    """Build the list of 12 month tab components.

    :returns: A list of ``dbc.Tab`` objects, one per calendar month.
    """
    return [
        dbc.Tab(label=calendar.month_abbr[m], tab_id=str(m), className="fw-medium")
        for m in range(1, 13)
    ]


def get_budget_layout() -> dbc.Container:
    """Build and return the full Budget tab layout.

    :returns: A ``dbc.Container`` with year selector, month tabs, budget
              goals table, and category progress cards.
    """
    ids = _Ids()
    current_year = datetime.today().year
    current_month = str(datetime.today().month)

    years_options = [{"label": str(y), "value": y} for y in range(2023, current_year + 2)]

    return dbc.Container(
        fluid=True,
        children=[

            # --- ROW 1: CONTROLS ---
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.Span("Year:", className="fw-bold me-2 text-muted"),
                            dcc.Dropdown(
                                id=ids.year_dropdown,
                                options=years_options,
                                value=current_year,
                                clearable=False,
                                style={"width": "130px"},
                            ),
                        ],
                        className="d-flex align-items-center bg-white p-3 rounded shadow-sm",
                    ),
                    xs=12,
                ),
                className="mb-4",
            ),

            # --- ROW 2: MONTH TABS ---
            dbc.Row(
                dbc.Col(
                    dbc.Tabs(
                        children=_month_tabs_children(),
                        id=ids.month_tabs,
                        active_tab=current_month,
                    ),
                    xs=12,
                ),
                className="mb-4",
            ),

            # --- ROW 3: BUDGET GOALS TABLE ---
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.H5("Budget Goals", className="fw-bold text-muted mb-1"),
                                            html.P(
                                                "Edit the Target ₪ column, then click Save.",
                                                className="text-muted mb-0",
                                                style={"fontSize": "0.875rem"},
                                            ),
                                        ]
                                    ),
                                    html.Div(
                                        [
                                            html.Span(
                                                id=ids.save_status,
                                                className="text-success me-3 fw-medium",
                                                style={"fontSize": "0.875rem"},
                                            ),
                                            dbc.Button(
                                                "Save Budgets",
                                                id=ids.save_btn,
                                                color="success",
                                                size="sm",
                                                n_clicks=0,
                                            ),
                                        ],
                                        className="d-flex align-items-center",
                                    ),
                                ],
                                className="d-flex justify-content-between align-items-start mb-3",
                            ),
                            budgets_datatable(
                                data=[],
                                table_id=ids.table,
                            ),
                        ],
                        className="bg-white p-4 rounded shadow-sm",
                    ),
                    xs=12,
                ),
                className="mb-4",
            ),

            # --- ROW 4: CATEGORY PROGRESS CARDS ---
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.H5("Spending vs Target", className="fw-bold text-muted mb-3"),
                            html.Div(
                                id=ids.progress_cards,
                                children=html.P(
                                    "Select a month to see category progress.",
                                    className="text-muted",
                                ),
                            ),
                        ],
                        className="bg-white p-4 rounded shadow-sm",
                    ),
                    xs=12,
                ),
            ),

        ],
    )


def register_budget_callbacks(app: Dash) -> None:
    """Register all reactive callbacks for the Budget tab.

    Callback 1 — ``_update_budget_view``:
        Fires on year or month change. Fetches budget targets and category
        actuals via the BFF endpoint, merges them, and populates the table
        and progress cards.

    Callback 2 — ``_save_budgets``:
        Fires only when the user clicks "Save Budgets". Reads the current
        table rows via ``State`` (avoiding circular triggers) and persists
        each category's target to the API.

    :param app: The ``Dash`` application instance to register callbacks on.
    """
    ids = _Ids()

    @app.callback(
        Output(ids.table, "data"),
        Output(ids.progress_cards, "children"),
        Input(ids.year_dropdown, "value"),
        Input(ids.month_tabs, "active_tab"),
    )
    def _update_budget_view(selected_year: int, active_month_str: str):
        """Fetch budget + actuals and populate the table and progress cards."""
        if not selected_year or not active_month_str:
            return [], []

        month = int(active_month_str)

        bff = fetch_budget_bff(selected_year, month)

        budgets_list = bff.get("budgets", [])
        target_by_cat = {b["category"]: float(b["monthly_target"]) for b in budgets_list}

        actual_by_cat = {k: float(v) for k, v in bff.get("category_actuals", {}).items()}

        # Always include all categories so empty rows still appear in the table
        table_rows = []
        for cat in CATEGORIES:
            target = float(target_by_cat.get(cat, 0.0))
            actual = float(actual_by_cat.get(cat, 0.0))
            remaining = target - actual
            table_rows.append(
                {
                    "category": cat,
                    "monthly_target": target,
                    "actual": actual,
                    "remaining": remaining,
                }
            )

        # One card per category, arranged in a responsive 3-column grid
        card_cols = [
            dbc.Col(
                budget_progress_card(
                    category=r["category"],
                    actual=r["actual"],
                    target=r["monthly_target"],
                ),
                xs=12,
                sm=6,
                lg=4,
                className="mb-3",
            )
            for r in table_rows
        ]
        progress_grid = dbc.Row(card_cols)

        return table_rows, progress_grid

    @app.callback(
        Output(ids.save_status, "children"),
        Input(ids.save_btn, "n_clicks"),
        State(ids.table, "data"),
        prevent_initial_call=True,
    )
    def _save_budgets(n_clicks: int, table_data: list[dict]):
        """Persist edited budget targets when the Save button is clicked.

        Uses ``State`` for the table data so the table itself cannot
        trigger this callback — avoiding circular firing.
        """
        if not table_data:
            return "Nothing to save."

        failed = []
        for row in table_data:
            category = row.get("category")
            target = row.get("monthly_target", 0.0)
            if category is None:
                continue
            success = save_category_budget(category, float(target))
            if not success:
                failed.append(category)

        if failed:
            return f"Failed to save: {', '.join(failed)}"
        return f"✓ Saved {len(table_data)} categories"
