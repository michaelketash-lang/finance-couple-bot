from __future__ import annotations

import calendar
import os
from dataclasses import dataclass
from datetime import datetime

import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, ctx, dash_table, dcc, html, no_update

from api_client import (
    fetch_investments_summary,
    fetch_all_investments,
    fetch_all_budgets,
    fetch_raw_expenses,
    add_funds_to_pot,
    log_investment,
    update_investment_record,
)

PAYER_1 = os.getenv('PAYER_1', 'Michael')
PAYER_2 = os.getenv('PAYER_2', 'Ori')

INVESTMENT_CATEGORIES = ['stocks', 'bonds', 'cash', 'pension', 'gemel', 'hishtalmut']

INVESTMENT_DISPLAY = {
    'stocks': 'Stocks',
    'bonds': 'Bonds',
    'cash': 'Cash',
    'pension': 'Pension',
    'gemel': 'Gemel',
    'hishtalmut': 'Hishtalmut',
}

ALLOCATION_COLORS = {
    'stocks': '#3498db',
    'bonds': '#e67e22',
    'cash': '#9b59b6',
    'pension': '#e74c3c',
    'gemel': '#f39c12',
    'hishtalmut': '#1abc9c',
    'pot': '#2ecc71',
}


@dataclass(frozen=True)
class _Ids:
    payer_radio: str = "inv-payer-radio"

    # KPI outputs
    net_worth: str = "inv-net-worth"
    total_invested: str = "inv-total-invested"
    pot_balance: str = "inv-pot-balance"

    # Donut chart
    donut_chart: str = "inv-donut-chart"

    # Refresh trigger stores (each form writes to its own store to avoid allow_duplicate)
    add_funds_store: str = "inv-add-funds-store"
    new_inv_store: str = "inv-new-inv-store"
    edit_inv_store: str = "inv-edit-inv-store"
    surplus_store: str = "inv-surplus-store"

    # Budget surplus panel
    surplus_year: str = "inv-surplus-year"
    surplus_month: str = "inv-surplus-month"
    surplus_display: str = "inv-surplus-display"
    surplus_transfer_amount: str = "inv-surplus-transfer-amount"
    surplus_transfer_btn: str = "inv-surplus-transfer-btn"
    surplus_status: str = "inv-surplus-status"

    # Add Funds modal
    add_funds_modal: str = "inv-add-funds-modal"
    add_funds_open_btn: str = "inv-add-funds-open-btn"
    add_funds_amount: str = "inv-add-funds-amount"
    add_funds_note: str = "inv-add-funds-note"
    add_funds_submit_btn: str = "inv-add-funds-submit-btn"
    add_funds_status: str = "inv-add-funds-status"

    # New Investment modal
    new_inv_modal: str = "inv-new-inv-modal"
    new_inv_open_btn: str = "inv-new-inv-open-btn"
    new_inv_category: str = "inv-new-inv-category"
    new_inv_amount: str = "inv-new-inv-amount"
    new_inv_name: str = "inv-new-inv-name"
    new_inv_ticker: str = "inv-new-inv-ticker"
    new_inv_submit_btn: str = "inv-new-inv-submit-btn"
    new_inv_status: str = "inv-new-inv-status"

    # Current holdings table + Edit modal
    holdings_table: str = "inv-holdings-table"
    edit_inv_open_btn: str = "inv-edit-open-btn"
    edit_inv_modal: str = "inv-edit-modal"
    edit_inv_id_store: str = "inv-edit-id-store"
    edit_inv_category_display: str = "inv-edit-category-display"
    edit_inv_amount: str = "inv-edit-amount"
    edit_inv_name: str = "inv-edit-name"
    edit_inv_ticker: str = "inv-edit-ticker"
    edit_inv_submit_btn: str = "inv-edit-submit-btn"
    edit_inv_status: str = "inv-edit-status"


# ── Chart ──────────────────────────────────────────────────────────────────────

def _build_donut_chart(allocation: dict, pot_balance: float, payer: str) -> go.Figure:
    labels, values, colors = [], [], []

    for cat in INVESTMENT_CATEGORIES:
        amt = allocation.get(cat, 0.0)
        if amt > 0:
            labels.append(INVESTMENT_DISPLAY[cat])
            values.append(amt)
            colors.append(ALLOCATION_COLORS[cat])

    pot = max(pot_balance, 0.0)
    labels.append("Cash / Unallocated")
    values.append(pot)
    colors.append(ALLOCATION_COLORS['pot'])

    total = sum(values)

    if total == 0:
        fig = go.Figure(go.Pie(
            labels=["No Assets Yet"],
            values=[1],
            marker=dict(colors=["#e8e8e8"]),
            hole=0.6,
            textinfo="none",
            showlegend=False,
            hoverinfo="skip",
        ))
        fig.update_layout(
            title=f"{payer}'s Asset Allocation",
            annotations=[dict(text="₪0", x=0.5, y=0.5, font_size=22,
                              showarrow=False, font_color="#aaa")],
            margin=dict(l=20, r=20, t=60, b=20),
        )
        return fig

    fig = go.Figure(go.Pie(
        labels=labels,
        values=values,
        marker=dict(colors=colors, line=dict(color="white", width=2)),
        hole=0.6,
        textposition="inside",
        texttemplate="%{percent:.1%}",
        hovertemplate="<b>%{label}</b><br>₪%{value:,.0f}  (%{percent:.1%})<extra></extra>",
        sort=False,
    ))
    fig.update_layout(
        title=f"{payer}'s Asset Allocation  •  Net Worth: ₪{total:,.0f}",
        annotations=[dict(
            text=f"₪{total:,.0f}",
            x=0.5, y=0.5,
            font=dict(size=18, color="#2c3e50", family="Arial"),
            showarrow=False,
        )],
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=-0.18, xanchor="center", x=0.5),
        hoverlabel=dict(bgcolor="rgba(0,0,0,0.8)", font=dict(color="white")),
    )
    return fig


# ── Helpers ────────────────────────────────────────────────────────────────────

def _kpi_card(label: str, value_id: str, icon: str, accent: str) -> dbc.Col:
    return dbc.Col(
        html.Div(
            [
                html.Div(icon, style={"fontSize": "2.2rem", "lineHeight": "1"}),
                html.P(label, className="text-muted mb-1 mt-2",
                       style={"fontSize": "0.8rem", "letterSpacing": "0.05em",
                              "textTransform": "uppercase"}),
                html.H2(id=value_id, children="—", className="fw-bold mb-0",
                        style={"color": accent}),
            ],
            className="bg-white rounded shadow-sm p-4 text-center h-100",
        ),
        xs=12, md=4, className="mb-3",
    )


def _add_funds_modal(ids: _Ids) -> dbc.Modal:
    return dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("💰 Add Funds to Pot")),
            dbc.ModalBody([
                dbc.Label("Amount (₪)", className="fw-medium"),
                dbc.Input(id=ids.add_funds_amount, type="number", placeholder="e.g. 3000",
                          min=1, step=1),
                dbc.Label("Note (optional)", className="fw-medium mt-3"),
                dbc.Input(id=ids.add_funds_note, type="text",
                          placeholder="e.g. December bonus"),
                html.Div(id=ids.add_funds_status, className="mt-3 small text-danger"),
            ]),
            dbc.ModalFooter(
                dbc.Button("Add Funds", id=ids.add_funds_submit_btn, color="success", n_clicks=0)
            ),
        ],
        id=ids.add_funds_modal, is_open=False, centered=True, backdrop="static",
    )


def _new_investment_modal(ids: _Ids) -> dbc.Modal:
    options = [{"label": INVESTMENT_DISPLAY[c], "value": c} for c in INVESTMENT_CATEGORIES]
    return dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("📊 Log New Investment")),
            dbc.ModalBody([
                dbc.Label("Asset Type", className="fw-medium"),
                dcc.Dropdown(id=ids.new_inv_category, options=options,
                             placeholder="Select asset type...", clearable=False),
                dbc.Label("Amount (₪)", className="fw-medium mt-3"),
                dbc.Input(id=ids.new_inv_amount, type="number", placeholder="e.g. 5000",
                          min=1, step=1),
                dbc.Label("Name / Description", className="fw-medium mt-3"),
                dbc.Input(id=ids.new_inv_name, type="text", placeholder="e.g. S&P 500 ETF"),
                dbc.Label("Ticker (optional)", className="fw-medium mt-3"),
                dbc.Input(id=ids.new_inv_ticker, type="text", placeholder="e.g. SPY"),
                html.Div(id=ids.new_inv_status, className="mt-3 small text-danger"),
            ]),
            dbc.ModalFooter(
                dbc.Button("Save Investment", id=ids.new_inv_submit_btn, color="primary",
                           n_clicks=0)
            ),
        ],
        id=ids.new_inv_modal, is_open=False, centered=True, backdrop="static",
    )


def _edit_investment_modal(ids: _Ids) -> dbc.Modal:
    return dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("✏️ Edit Investment")),
            dbc.ModalBody([
                dbc.Label("Asset Type", className="fw-medium"),
                html.P(id=ids.edit_inv_category_display, className="fw-bold text-primary mb-3"),
                dbc.Label("Amount (₪)", className="fw-medium"),
                dbc.Input(id=ids.edit_inv_amount, type="number", min=0, step=1),
                dbc.Label("Name / Description", className="fw-medium mt-3"),
                dbc.Input(id=ids.edit_inv_name, type="text"),
                dbc.Label("Ticker (optional)", className="fw-medium mt-3"),
                dbc.Input(id=ids.edit_inv_ticker, type="text"),
                html.P("Note: editing the amount adjusts the book value only — "
                       "your Pot is not affected.",
                       className="text-muted small mt-3 mb-0"),
                html.Div(id=ids.edit_inv_status, className="mt-2 small text-danger"),
            ]),
            dbc.ModalFooter(
                dbc.Button("Save Changes", id=ids.edit_inv_submit_btn, color="warning",
                           n_clicks=0)
            ),
        ],
        id=ids.edit_inv_modal, is_open=False, centered=True, backdrop="static",
    )


def _holdings_table() -> dash_table.DataTable:
    return dash_table.DataTable(
        id=_Ids().holdings_table,
        columns=[
            {"name": "Category", "id": "category_display", "editable": False},
            {"name": "Name",     "id": "name",              "editable": False},
            {"name": "Amount (₪)", "id": "amount",          "editable": False,
             "type": "numeric", "format": {"specifier": ",.0f"}},
            {"name": "Ticker",   "id": "ticker",            "editable": False},
        ],
        data=[],
        row_selectable="single",
        selected_rows=[],
        page_size=10,
        style_header={
            "backgroundColor": "#2c3e50",
            "color": "white",
            "fontWeight": "bold",
            "fontSize": "0.85rem",
        },
        style_cell={
            "padding": "10px 14px",
            "fontSize": "0.875rem",
            "border": "1px solid #e9ecef",
        },
        style_data_conditional=[
            {"if": {"row_index": "odd"}, "backgroundColor": "#f8f9fa"},
        ],
        style_table={"overflowX": "auto"},
    )


# ── Layout ─────────────────────────────────────────────────────────────────────

def get_investments_layout() -> dbc.Container:
    ids = _Ids()
    current_year = datetime.today().year
    current_month = datetime.today().month
    year_options = [{"label": str(y), "value": y} for y in range(2023, current_year + 2)]
    month_options = [{"label": calendar.month_abbr[m], "value": m} for m in range(1, 13)]

    return dbc.Container(
        fluid=True,
        children=[
            # ── Stores (refresh triggers, no UI) ──────────────────────────────
            dcc.Store(id=ids.add_funds_store, data=0),
            dcc.Store(id=ids.new_inv_store, data=0),
            dcc.Store(id=ids.edit_inv_store, data=0),
            dcc.Store(id=ids.surplus_store, data=0),
            dcc.Store(id=ids.edit_inv_id_store, data=None),

            # ── Modals ────────────────────────────────────────────────────────
            _add_funds_modal(ids),
            _new_investment_modal(ids),
            _edit_investment_modal(ids),

            # ── Payer Selector ────────────────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.Span("Viewing:", className="fw-bold me-3 text-muted"),
                            dbc.RadioItems(
                                id=ids.payer_radio,
                                options=[
                                    {"label": PAYER_1, "value": PAYER_1},
                                    {"label": PAYER_2, "value": PAYER_2},
                                ],
                                value=PAYER_1,
                                inline=True,
                                inputClassName="me-1",
                                labelClassName="me-4 fw-medium",
                            ),
                        ],
                        className="d-flex align-items-center bg-white p-3 rounded shadow-sm",
                    ),
                    xs=12,
                ),
                className="mb-4",
            ),

            # ── Zone 1: KPI Cards ─────────────────────────────────────────────
            dbc.Row(
                [
                    _kpi_card("Net Worth",          ids.net_worth,      "💼", "#2c3e50"),
                    _kpi_card("Total Invested",      ids.total_invested,  "📈", "#2980b9"),
                    _kpi_card("The Pot (Available)", ids.pot_balance,     "💰", "#27ae60"),
                ],
                className="mb-4",
            ),

            # ── Zone 2: Budget Surplus Panel ──────────────────────────────────
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.H5("💡 Monthly Budget Surplus", className="fw-bold text-muted mb-1"),
                            html.P(
                                "See how much you under-spent vs your budget this month "
                                "and transfer the surplus directly into your Pot.",
                                className="text-muted mb-3",
                                style={"fontSize": "0.875rem"},
                            ),
                            html.Div(
                                [
                                    html.Span("Month:", className="fw-bold me-2 text-muted"),
                                    dcc.Dropdown(
                                        id=ids.surplus_year,
                                        options=year_options,
                                        value=current_year,
                                        clearable=False,
                                        style={"width": "110px"},
                                    ),
                                    dcc.Dropdown(
                                        id=ids.surplus_month,
                                        options=month_options,
                                        value=current_month,
                                        clearable=False,
                                        style={"width": "110px"},
                                        className="ms-2",
                                    ),
                                ],
                                className="d-flex align-items-center mb-3",
                            ),
                            html.Div(id=ids.surplus_display, className="mb-3"),
                            html.Div(
                                [
                                    html.Span("Transfer amount (₪):", className="fw-medium me-2"),
                                    dbc.Input(
                                        id=ids.surplus_transfer_amount,
                                        type="number",
                                        min=0,
                                        step=1,
                                        style={"width": "140px"},
                                        className="me-3",
                                    ),
                                    dbc.Button(
                                        "➡ Add to My Pot",
                                        id=ids.surplus_transfer_btn,
                                        color="info",
                                        size="sm",
                                        disabled=True,
                                        n_clicks=0,
                                    ),
                                ],
                                className="d-flex align-items-center flex-wrap gap-2",
                            ),
                            html.Div(id=ids.surplus_status, className="mt-2 small"),
                        ],
                        className="bg-white p-4 rounded shadow-sm",
                    ),
                    xs=12,
                ),
                className="mb-4",
            ),

            # ── Zone 3: Action Buttons ────────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.H5("Actions", className="fw-bold text-muted mb-3"),
                            html.Div(
                                [
                                    dbc.Button("➕ Add Funds", id=ids.add_funds_open_btn,
                                               color="success", size="lg", className="px-4",
                                               n_clicks=0),
                                    dbc.Button("📊 New Investment", id=ids.new_inv_open_btn,
                                               color="primary", size="lg", className="px-4",
                                               n_clicks=0),
                                ],
                                className="d-flex flex-wrap gap-3",
                            ),
                        ],
                        className="bg-white p-4 rounded shadow-sm",
                    ),
                    xs=12,
                ),
                className="mb-4",
            ),

            # ── Zone 4: Current Holdings Table ────────────────────────────────
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H5("Current Holdings", className="fw-bold text-muted mb-0"),
                                    dbc.Button(
                                        "✏️ Edit Selected",
                                        id=ids.edit_inv_open_btn,
                                        color="warning",
                                        size="sm",
                                        disabled=True,
                                        n_clicks=0,
                                    ),
                                ],
                                className="d-flex justify-content-between align-items-center mb-3",
                            ),
                            _holdings_table(),
                        ],
                        className="bg-white p-4 rounded shadow-sm",
                    ),
                    xs=12,
                ),
                className="mb-4",
            ),

            # ── Zone 5: Donut Chart ───────────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.H5("Asset Allocation", className="fw-bold text-muted mb-1"),
                            html.P(
                                '"Cash / Unallocated" is The Pot. '
                                'It shrinks as you log investments.',
                                className="text-muted mb-3",
                                style={"fontSize": "0.875rem"},
                            ),
                            dcc.Graph(id=ids.donut_chart, config={"displayModeBar": False},
                                      style={"height": "480px"}),
                        ],
                        className="bg-white p-4 rounded shadow-sm",
                    ),
                    xs=12,
                ),
            ),
        ],
    )


# ── Callbacks ──────────────────────────────────────────────────────────────────

def register_investments_callbacks(app: Dash) -> None:
    ids = _Ids()

    # ── 1. Main display: KPIs + chart + holdings table ─────────────────────
    @app.callback(
        Output(ids.net_worth, "children"),
        Output(ids.total_invested, "children"),
        Output(ids.pot_balance, "children"),
        Output(ids.donut_chart, "figure"),
        Output(ids.holdings_table, "data"),
        Input(ids.payer_radio, "value"),
        Input(ids.add_funds_store, "data"),
        Input(ids.new_inv_store, "data"),
        Input(ids.edit_inv_store, "data"),
        Input(ids.surplus_store, "data"),
    )
    def _update_main_display(payer, _a, _b, _c, _d):
        summary = fetch_investments_summary(payer)
        allocation = summary.get('allocation', {})
        pot = summary.get('pot_balance', 0.0)

        fmt = lambda v: f"₪{v:,.0f}"
        fig = _build_donut_chart(allocation, pot, payer)

        rows = fetch_all_investments(payer)
        table_data = [
            {**r, "category_display": INVESTMENT_DISPLAY.get(r["category"], r["category"])}
            for r in rows
        ]

        return (
            fmt(summary.get('net_worth', 0.0)),
            fmt(summary.get('total_invested', 0.0)),
            fmt(pot),
            fig,
            table_data,
        )

    # ── 2. Budget surplus panel ────────────────────────────────────────────
    @app.callback(
        Output(ids.surplus_display, "children"),
        Output(ids.surplus_transfer_amount, "value"),
        Output(ids.surplus_transfer_btn, "disabled"),
        Input(ids.surplus_year, "value"),
        Input(ids.surplus_month, "value"),
        Input(ids.surplus_store, "data"),
    )
    def _update_surplus_display(year, month, _ts):
        if not year or not month:
            return "Select a month to see the surplus.", None, True

        df_budgets = fetch_all_budgets()
        total_budget = float(df_budgets['monthly_target'].sum()) if not df_budgets.empty else 0.0

        df_expenses = fetch_raw_expenses(year, int(month), split='')
        total_actual = float(df_expenses['amount'].sum()) if not df_expenses.empty else 0.0

        surplus = max(0.0, total_budget - total_actual)
        month_label = f"{calendar.month_abbr[int(month)]} {year}"

        if total_budget == 0:
            display = html.P("No budget set for this month yet.", className="text-muted mb-0")
            return display, None, True

        color = "text-success" if surplus > 0 else "text-danger"
        label = "surplus" if surplus > 0 else "over budget"
        display = html.Div([
            html.Span(f"{month_label}:  ", className="text-muted"),
            html.Span(f"Budget ₪{total_budget:,.0f}", className="fw-medium"),
            html.Span("  vs  ", className="text-muted"),
            html.Span(f"Actual ₪{total_actual:,.0f}", className="fw-medium"),
            html.Span(f"  →  ₪{surplus:,.0f} {label}", className=f"fw-bold {color} ms-1"),
        ])

        return display, surplus if surplus > 0 else None, surplus <= 0

    # ── 3. Transfer surplus to payer's Pot ────────────────────────────────
    @app.callback(
        Output(ids.surplus_status, "children"),
        Output(ids.surplus_store, "data"),
        Input(ids.surplus_transfer_btn, "n_clicks"),
        State(ids.surplus_transfer_amount, "value"),
        State(ids.payer_radio, "value"),
        State(ids.surplus_year, "value"),
        State(ids.surplus_month, "value"),
        State(ids.surplus_store, "data"),
        prevent_initial_call=True,
    )
    def _transfer_surplus(n_clicks, amount, payer, year, month, ts):
        if not amount or float(amount) <= 0:
            return html.Span("Enter a valid amount.", className="text-danger"), ts
        month_label = f"{calendar.month_abbr[int(month)]} {year}"
        success = add_funds_to_pot(
            amount=float(amount),
            payer=payer,
            note=f"Budget surplus — {month_label}",
        )
        if success:
            return (
                html.Span(f"✓ ₪{float(amount):,.0f} added to {payer}'s Pot.",
                          className="text-success fw-medium"),
                ts + 1,
            )
        return html.Span("Failed to transfer. Please try again.", className="text-danger"), ts

    # ── 4. Edit button enabled/disabled based on row selection ────────────
    @app.callback(
        Output(ids.edit_inv_open_btn, "disabled"),
        Input(ids.holdings_table, "selected_rows"),
    )
    def _toggle_edit_btn(selected_rows):
        return not bool(selected_rows)

    # ── 5. Add Funds modal (open / submit) ────────────────────────────────
    @app.callback(
        Output(ids.add_funds_modal, "is_open"),
        Output(ids.add_funds_status, "children"),
        Output(ids.add_funds_store, "data"),
        Input(ids.add_funds_open_btn, "n_clicks"),
        Input(ids.add_funds_submit_btn, "n_clicks"),
        State(ids.add_funds_modal, "is_open"),
        State(ids.add_funds_amount, "value"),
        State(ids.add_funds_note, "value"),
        State(ids.payer_radio, "value"),
        State(ids.add_funds_store, "data"),
        prevent_initial_call=True,
    )
    def _handle_add_funds(open_clicks, submit_clicks, is_open, amount, note, payer, ts):
        triggered = ctx.triggered_id
        if triggered == ids.add_funds_open_btn:
            return not is_open, "", ts
        if triggered == ids.add_funds_submit_btn:
            if not amount or float(amount) <= 0:
                return True, "Please enter a valid amount greater than 0.", ts
            success = add_funds_to_pot(float(amount), payer, note or None)
            if success:
                return False, "", ts + 1
            return True, "Failed to add funds. Please try again.", ts
        return is_open, "", ts

    # ── 6. New Investment modal (open / submit) ───────────────────────────
    @app.callback(
        Output(ids.new_inv_modal, "is_open"),
        Output(ids.new_inv_status, "children"),
        Output(ids.new_inv_store, "data"),
        Input(ids.new_inv_open_btn, "n_clicks"),
        Input(ids.new_inv_submit_btn, "n_clicks"),
        State(ids.new_inv_modal, "is_open"),
        State(ids.new_inv_category, "value"),
        State(ids.new_inv_amount, "value"),
        State(ids.new_inv_name, "value"),
        State(ids.new_inv_ticker, "value"),
        State(ids.payer_radio, "value"),
        State(ids.new_inv_store, "data"),
        prevent_initial_call=True,
    )
    def _handle_new_investment(open_clicks, submit_clicks, is_open,
                               category, amount, name, ticker, payer, ts):
        triggered = ctx.triggered_id
        if triggered == ids.new_inv_open_btn:
            return not is_open, "", ts
        if triggered == ids.new_inv_submit_btn:
            if not category:
                return True, "Please select an asset type.", ts
            if not amount or float(amount) <= 0:
                return True, "Please enter a valid amount greater than 0.", ts
            if not name or not name.strip():
                return True, "Please enter a name or description.", ts
            success = log_investment(
                category=category,
                amount=float(amount),
                name=name.strip(),
                payer=payer,
                ticker=ticker.strip() if ticker else None,
            )
            if success:
                return False, "", ts + 1
            return True, "Could not save — make sure your Pot has enough funds.", ts
        return is_open, "", ts

    # ── 7. Edit Investment modal (open with pre-fill / submit) ────────────
    @app.callback(
        Output(ids.edit_inv_modal, "is_open"),
        Output(ids.edit_inv_amount, "value"),
        Output(ids.edit_inv_name, "value"),
        Output(ids.edit_inv_ticker, "value"),
        Output(ids.edit_inv_category_display, "children"),
        Output(ids.edit_inv_id_store, "data"),
        Output(ids.edit_inv_status, "children"),
        Output(ids.edit_inv_store, "data"),
        Input(ids.edit_inv_open_btn, "n_clicks"),
        Input(ids.edit_inv_submit_btn, "n_clicks"),
        State(ids.edit_inv_modal, "is_open"),
        State(ids.edit_inv_amount, "value"),
        State(ids.edit_inv_name, "value"),
        State(ids.edit_inv_ticker, "value"),
        State(ids.edit_inv_id_store, "data"),
        State(ids.holdings_table, "selected_rows"),
        State(ids.holdings_table, "data"),
        State(ids.edit_inv_store, "data"),
        prevent_initial_call=True,
    )
    def _handle_edit_investment(open_clicks, submit_clicks, is_open,
                                amt_val, name_val, ticker_val, inv_id,
                                selected_rows, table_data, ts):
        triggered = ctx.triggered_id

        if triggered == ids.edit_inv_open_btn:
            if not selected_rows or not table_data:
                return is_open, no_update, no_update, no_update, no_update, inv_id, \
                       "Select a row first.", ts
            row = table_data[selected_rows[0]]
            cat_display = INVESTMENT_DISPLAY.get(row.get('category', ''), row.get('category', ''))
            return (True, row['amount'], row['name'], row.get('ticker', ''),
                    cat_display, row['id'], "", ts)

        if triggered == ids.edit_inv_submit_btn:
            if not amt_val or float(amt_val) < 0:
                return True, amt_val, name_val, ticker_val, no_update, inv_id, \
                       "Please enter a valid amount.", ts
            if not name_val or not str(name_val).strip():
                return True, amt_val, name_val, ticker_val, no_update, inv_id, \
                       "Name cannot be empty.", ts
            success = update_investment_record(
                inv_id=inv_id,
                amount=float(amt_val),
                name=str(name_val).strip(),
                ticker=str(ticker_val).strip() if ticker_val else None,
            )
            if success:
                return False, None, None, None, no_update, None, "", ts + 1
            return True, amt_val, name_val, ticker_val, no_update, inv_id, \
                   "Failed to update. Please try again.", ts

        return is_open, no_update, no_update, no_update, no_update, inv_id, "", ts
