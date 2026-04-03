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
    year_dropdown: str = "budget-year-dropdown"
    month_tabs: str = "budget-month-tabs"
    table: str = "budgets-table"
    progress_cards: str = "budget-progress-cards"
    save_btn: str = "budget-save-btn"
    save_status: str = "budget-save-status"


def _month_tabs_children() -> list[dbc.Tab]:
    return [
        dbc.Tab(label=calendar.month_abbr[m], tab_id=str(m), className="fw-medium")
        for m in range(1, 13)
    ]


def get_budget_layout() -> dbc.Container:
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
                            # Header row: title + save button side by side
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
    """
    Registers all reactive callbacks for the Budget tab.

    There is one callback here that does the following:
      Inputs  → year dropdown value + active month tab
      Outputs → budget table data + progress cards children

    Whenever the user switches month or year, Dash fires this function.
    We then:
      1. Fetch the saved budget targets from the API (/budget/all)
      2. Fetch every expense for that month from the API (/expenses/raw)
      3. Group expenses by category to get the actual spend per category
      4. Merge: for each category we now have (target, actual, remaining)
      5. Push the merged rows into the table
      6. Build a progress card for each category and push them into the grid
    """
    ids = _Ids()

    @app.callback(
        Output(ids.table, "data"),
        Output(ids.progress_cards, "children"),
        Input(ids.year_dropdown, "value"),
        Input(ids.month_tabs, "active_tab"),
    )
    def _update_budget_view(selected_year: int, active_month_str: str):
        if not selected_year or not active_month_str:
            return [], []

        month = int(active_month_str)

        # --- Single BFF call replaces fetch_all_budgets() + fetch_raw_expenses() ---
        bff = fetch_budget_bff(selected_year, month)

        # --- 1. Budget targets ---
        budgets_list = bff.get("budgets", [])
        target_by_cat = {b["category"]: float(b["monthly_target"]) for b in budgets_list}

        # --- 2. Category actuals (pre-aggregated by the BFF) ---
        actual_by_cat = {k: float(v) for k, v in bff.get("category_actuals", {}).items()}

        # --- 3. Merge targets with actuals, compute remaining ---
        # Always iterate over ALL categories so every row appears in the table,
        # even if no budget target has been saved yet (defaults to 0).

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

        # --- 5. Build progress cards grid ---
        # One card per category, arranged in a responsive 3-column grid.
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

    # --- Callback 2: Save edited budget targets ---
    # This callback is intentionally separate from the update callback above.
    # It only fires when the user explicitly clicks "Save Budgets".
    #
    # Input  → save button n_clicks (fires on every click)
    # State  → current table data (read without triggering the callback)
    # Output → save_status text (confirms success or reports errors)
    #
    # Using State instead of Input for the table data is the key pattern here:
    # State lets us READ the current table rows at the moment the button is
    # clicked, without the table itself being able to trigger this callback.
    # That completely avoids the circular-trigger problem.
    @app.callback(
        Output(ids.save_status, "children"),
        Input(ids.save_btn, "n_clicks"),
        State(ids.table, "data"),
        prevent_initial_call=True,
    )
    def _save_budgets(n_clicks: int, table_data: list[dict]):
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
