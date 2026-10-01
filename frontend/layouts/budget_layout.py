"""
layouts/budget_layout.py
========================

Dash layout and callbacks for the Budget tab.

Provides the full page layout (year dropdown, payer radio, month tabs, budget
goals table, category progress cards, and yearly category chart) and registers
three reactive callbacks:

- ``_update_budget_view``    — fetches budget + actuals on year/month/payer change.
- ``_save_budgets``          — persists edited budget targets on button click.
- ``_update_category_chart`` — builds the yearly spending chart for a category.
"""

from __future__ import annotations

import calendar
import os
from dataclasses import dataclass
from datetime import datetime

import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dcc, html

from components.cards import budget_progress_card
from components.tables import budgets_datatable
from api_client import (
    fetch_budget_bff,
    fetch_all_budgets,
    fetch_yearly_expenses_raw,
    save_budgets_batch,
    CATEGORIES,
)

PAYER_1 = os.getenv('PAYER_1', 'Michael')
PAYER_2 = os.getenv('PAYER_2', 'Ori')


@dataclass(frozen=True)
class _Ids:
    """Frozen dataclass holding all Dash component IDs for the Budget tab."""
    year_dropdown:    str = "budget-year-dropdown"
    payer_radio:      str = "budget-payer-radio"
    month_tabs:       str = "budget-month-tabs"
    table:            str = "budgets-table"
    progress_cards:   str = "budget-progress-cards"
    save_btn:         str = "budget-save-btn"
    save_status:      str = "budget-save-status"
    category_selector: str = "budget-category-selector"
    category_chart:   str = "budget-category-chart"


def _month_tabs_children() -> list[dbc.Tab]:
    return [
        dbc.Tab(label=calendar.month_abbr[m], tab_id=str(m), className="fw-medium")
        for m in range(1, 13)
    ]


def _empty_chart() -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis={'visible': False},
        yaxis={'visible': False},
        margin=dict(l=20, r=20, t=20, b=20),
        annotations=[dict(
            text='Select a category above to see yearly spending.',
            x=0.5, y=0.5, showarrow=False,
            font=dict(size=14, color='#aaa'),
            xref='paper', yref='paper',
        )],
    )
    return fig


def get_budget_layout() -> dbc.Container:
    """Build and return the full Budget tab layout."""
    ids = _Ids()
    current_year  = datetime.today().year
    current_month = str(datetime.today().month)

    years_options = [{"label": str(y), "value": y} for y in range(2023, current_year + 2)]
    category_options = [{"label": c, "value": c} for c in CATEGORIES]

    return dbc.Container(
        fluid=True,
        children=[

            # ── ROW 1: YEAR + PAYER CONTROLS ─────────────────────────────────
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
                            html.Div(
                                style={"width": "1px", "backgroundColor": "#dee2e6",
                                       "margin": "0 20px", "alignSelf": "stretch"},
                            ),
                            html.Span("Budget for:", className="fw-bold me-3 text-muted"),
                            dbc.RadioItems(
                                id=ids.payer_radio,
                                options=[
                                    {"label": "Shared",  "value": "shared"},
                                    {"label": PAYER_1,   "value": PAYER_1},
                                    {"label": PAYER_2,   "value": PAYER_2},
                                ],
                                value="shared",
                                inline=True,
                                inputClassName="me-1",
                                labelClassName="me-4 fw-medium",
                            ),
                        ],
                        className="d-flex align-items-center bg-white p-3 rounded shadow-sm budget-controls-bar",
                    ),
                    xs=12,
                ),
                className="mb-4",
            ),

            # ── ROW 2: MONTH TABS ─────────────────────────────────────────────
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

            # ── ROW 3: BUDGET GOALS TABLE ─────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.Div(
                                        [
                                            html.H5("Budget Goals",
                                                    className="fw-bold text-muted mb-1"),
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
                            budgets_datatable(data=[], table_id=ids.table),
                        ],
                        className="bg-white p-4 rounded shadow-sm",
                    ),
                    xs=12,
                ),
                className="mb-4",
            ),

            # ── ROW 4: CATEGORY PROGRESS CARDS ───────────────────────────────
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.H5("Spending vs Target",
                                    className="fw-bold text-muted mb-3"),
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
                className="mb-4",
            ),

            # ── ROW 5: YEARLY CATEGORY CHART ─────────────────────────────────
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.H5("Yearly Category Breakdown",
                                    className="fw-bold text-muted mb-1"),
                            html.P(
                                "See how much was spent each month on a single category. "
                                "The dashed line shows the monthly budget target.",
                                className="text-muted mb-3",
                                style={"fontSize": "0.875rem"},
                            ),
                            dcc.Dropdown(
                                id=ids.category_selector,
                                options=category_options,
                                placeholder="Select a category…",
                                clearable=True,
                                style={"maxWidth": "320px"},
                                className="mb-3",
                            ),
                            dcc.Graph(
                                id=ids.category_chart,
                                figure=_empty_chart(),
                                config={"displayModeBar": False},
                                style={"height": "380px"},
                            ),
                        ],
                        className="bg-white p-4 rounded shadow-sm",
                    ),
                    xs=12,
                ),
                className="desktop-only",
            ),

        ],
    )


def register_budget_callbacks(app: Dash) -> None:
    """Register all reactive callbacks for the Budget tab."""
    ids = _Ids()

    # ── 1. Refresh table and progress cards ───────────────────────────────────
    @app.callback(
        Output(ids.table,          "data"),
        Output(ids.progress_cards, "children"),
        Input(ids.year_dropdown,   "value"),
        Input(ids.month_tabs,      "active_tab"),
        Input(ids.payer_radio,     "value"),
    )
    def _update_budget_view(selected_year, active_month_str, payer):
        if not selected_year or not active_month_str:
            return [], []

        month = int(active_month_str)
        bff   = fetch_budget_bff(selected_year, month, payer)

        target_by_cat = {b["category"]: float(b["monthly_target"])
                         for b in bff.get("budgets", [])}
        actual_by_cat = {k: float(v)
                         for k, v in bff.get("category_actuals", {}).items()}

        table_rows = []
        for cat in CATEGORIES:
            target    = target_by_cat.get(cat, 0.0)
            actual    = actual_by_cat.get(cat, 0.0)
            remaining = target - actual
            table_rows.append({
                "category":       cat,
                "monthly_target": target,
                "actual":         actual,
                "remaining":      remaining,
            })

        card_cols = [
            dbc.Col(
                budget_progress_card(
                    category=r["category"],
                    actual=r["actual"],
                    target=r["monthly_target"],
                ),
                xs=12, sm=6, lg=4, className="mb-3",
            )
            for r in table_rows
        ]

        return table_rows, dbc.Row(card_cols)

    # ── 2. Save budgets ───────────────────────────────────────────────────────
    @app.callback(
        Output(ids.save_status, "children"),
        Input(ids.save_btn,     "n_clicks"),
        State(ids.table,        "data"),
        State(ids.payer_radio,  "value"),
        prevent_initial_call=True,
    )
    def _save_budgets(n_clicks, table_data, payer):
        if not table_data:
            return "Nothing to save."

        budgets = [
            {
                "category":       row["category"],
                "monthly_target": float(row.get("monthly_target", 0.0)),
                "payer":          payer,
            }
            for row in table_data if row.get("category")
        ]

        success = save_budgets_batch(budgets)
        if success:
            payer_label = "Shared" if payer == "shared" else payer
            return f"✓ Saved {len(budgets)} categories for {payer_label}"
        return "Failed to save budgets."

    # ── 3. Yearly category chart ──────────────────────────────────────────────
    @app.callback(
        Output(ids.category_chart,   "figure"),
        Input(ids.year_dropdown,     "value"),
        Input(ids.category_selector, "value"),
        Input(ids.payer_radio,       "value"),
    )
    def _update_category_chart(year, category, payer):
        if not year or not category:
            return _empty_chart()

        # ── Fetch all raw expense rows for the year ──
        df = fetch_yearly_expenses_raw(year)
        if df.empty:
            return _empty_chart()

        # ── Filter to selected category ──
        df = df[df['category'] == category]

        # ── Filter by payer view ──
        if payer == 'shared':
            df = df[df['split'] == 'shared']
        else:
            df = df[(df['split'] == 'personal') & (df['payer'] == payer)]

        # ── Aggregate by month ──
        df['month'] = df['date'].dt.month
        monthly = (
            df.groupby('month')['amount']
            .sum()
            .reindex(range(1, 13), fill_value=0.0)
        )
        month_labels = [calendar.month_abbr[m] for m in range(1, 13)]

        # ── Get budget target for this category + payer ──
        budgets_df = fetch_all_budgets(payer)
        target = 0.0
        if not budgets_df.empty:
            match = budgets_df[budgets_df['category'] == category]
            if not match.empty:
                target = float(match.iloc[0]['monthly_target'])

        # ── Bar colours: red if over budget, blue otherwise ──
        bar_colors = [
            '#e74c3c' if (target > 0 and v > target) else '#3498db'
            for v in monthly.values
        ]

        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=month_labels,
            y=monthly.values,
            marker_color=bar_colors,
            name='Actual',
            hovertemplate='%{x}: ₪%{y:,.0f}<extra></extra>',
        ))

        # ── Dashed budget target line ──
        if target > 0:
            fig.add_hline(
                y=target,
                line_dash='dash',
                line_color='#e74c3c',
                line_width=2,
                annotation_text=f'Budget ₪{target:,.0f}',
                annotation_position='top left',
                annotation_font=dict(color='#e74c3c', size=12),
            )

        payer_label = 'Shared' if payer == 'shared' else payer
        fig.update_layout(
            title=dict(
                text=f'{category} — {payer_label} • {year}',
                font=dict(size=15, color='#2c3e50'),
            ),
            xaxis_title='Month',
            yaxis_title='Amount (₪)',
            yaxis=dict(tickformat=',.0f', gridcolor='#f0f0f0'),
            xaxis=dict(showgrid=False),
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=20, r=20, t=50, b=20),
            showlegend=False,
            bargap=0.35,
        )

        return fig
