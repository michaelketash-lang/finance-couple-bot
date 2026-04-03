"""
investments_layout.py
─────────────────────
Owns the static structure of the Investments tab:
  - Component ID registry (_Ids)
  - Shared constants (categories, colors, display names)
  - Modal builders
  - Holdings table definition
  - get_investments_layout() — the single public entry point

No API calls. No callbacks. No Plotly. Pure UI assembly.
"""
from __future__ import annotations

import calendar
import os
from dataclasses import dataclass
from datetime import datetime

import dash_bootstrap_components as dbc
from dash import dash_table, dcc, html

# ── Payer names come from the environment (same as the rest of the app) ────────
PAYER_1 = os.getenv('PAYER_1', 'Michael')
PAYER_2 = os.getenv('PAYER_2', 'Ori')

# ── Investment domain constants ────────────────────────────────────────────────
INVESTMENT_CATEGORIES = ['stocks', 'bonds', 'cash', 'pension', 'gemel', 'hishtalmut']

INVESTMENT_DISPLAY: dict[str, str] = {
    'stocks':      'Stocks',
    'bonds':       'Bonds',
    'cash':        'Cash',
    'pension':     'Pension',
    'gemel':       'Gemel',
    'hishtalmut':  'Hishtalmut',
}

ALLOCATION_COLORS: dict[str, str] = {
    'stocks':     '#3498db',   # Blue
    'bonds':      '#e67e22',   # Orange
    'cash':       '#9b59b6',   # Purple
    'pension':    '#e74c3c',   # Red
    'gemel':      '#f39c12',   # Amber
    'hishtalmut': '#1abc9c',   # Teal
    'pot':        '#2ecc71',   # Light green — Cash / Unallocated
}


# ── Component ID registry ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class _Ids:
    """
    Single source of truth for every Dash component ID used across both
    investments_layout.py and investments_callbacks.py.

    Frozen so IDs are never mutated at runtime.
    """
    # Payer filter
    payer_radio: str = "inv-payer-radio"

    # KPI cards
    net_worth:      str = "inv-net-worth"
    total_invested: str = "inv-total-invested"
    pot_balance:    str = "inv-pot-balance"

    # Donut chart
    donut_chart: str = "inv-donut-chart"

    # Refresh-trigger stores — each form writes to its own so no allow_duplicate needed
    add_funds_store: str = "inv-add-funds-store"
    new_inv_store:   str = "inv-new-inv-store"
    edit_inv_store:  str = "inv-edit-inv-store"
    surplus_store:   str = "inv-surplus-store"

    # Budget surplus panel
    surplus_year:            str = "inv-surplus-year"
    surplus_month:           str = "inv-surplus-month"
    surplus_display:         str = "inv-surplus-display"
    surplus_transfer_amount: str = "inv-surplus-transfer-amount"
    surplus_transfer_btn:    str = "inv-surplus-transfer-btn"
    surplus_status:          str = "inv-surplus-status"

    # Add Funds modal
    add_funds_modal:      str = "inv-add-funds-modal"
    add_funds_open_btn:   str = "inv-add-funds-open-btn"
    add_funds_amount:     str = "inv-add-funds-amount"
    add_funds_note:       str = "inv-add-funds-note"
    add_funds_submit_btn: str = "inv-add-funds-submit-btn"
    add_funds_status:     str = "inv-add-funds-status"

    # New Investment modal
    new_inv_modal:      str = "inv-new-inv-modal"
    new_inv_open_btn:   str = "inv-new-inv-open-btn"
    new_inv_category:   str = "inv-new-inv-category"
    new_inv_amount:     str = "inv-new-inv-amount"
    new_inv_name:       str = "inv-new-inv-name"
    new_inv_ticker:     str = "inv-new-inv-ticker"
    new_inv_submit_btn: str = "inv-new-inv-submit-btn"
    new_inv_status:     str = "inv-new-inv-status"

    # Current holdings table + Edit modal
    holdings_table:           str = "inv-holdings-table"
    edit_inv_open_btn:        str = "inv-edit-open-btn"
    edit_inv_modal:           str = "inv-edit-modal"
    edit_inv_id_store:        str = "inv-edit-id-store"
    edit_inv_category_display: str = "inv-edit-category-display"
    edit_inv_amount:          str = "inv-edit-amount"
    edit_inv_name:            str = "inv-edit-name"
    edit_inv_ticker:          str = "inv-edit-ticker"
    edit_inv_submit_btn:      str = "inv-edit-submit-btn"
    edit_inv_status:          str = "inv-edit-status"


# ── Private UI component builders ──────────────────────────────────────────────

def _kpi_card(label: str, value_id: str, icon: str, accent: str) -> dbc.Col:
    return dbc.Col(
        html.Div(
            [
                html.Div(icon, style={"fontSize": "2.2rem", "lineHeight": "1"}),
                html.P(
                    label,
                    className="text-muted mb-1 mt-2",
                    style={"fontSize": "0.8rem", "letterSpacing": "0.05em",
                           "textTransform": "uppercase"},
                ),
                html.H2(
                    id=value_id,
                    children="—",
                    className="fw-bold mb-0",
                    style={"color": accent},
                ),
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
                dbc.Input(id=ids.add_funds_amount, type="number",
                          placeholder="e.g. 3000", min=1, step=1),
                dbc.Label("Note (optional)", className="fw-medium mt-3"),
                dbc.Input(id=ids.add_funds_note, type="text",
                          placeholder="e.g. December bonus"),
                html.Div(id=ids.add_funds_status, className="mt-3 small text-danger"),
            ]),
            dbc.ModalFooter(
                dbc.Button("Add Funds", id=ids.add_funds_submit_btn,
                           color="success", n_clicks=0)
            ),
        ],
        id=ids.add_funds_modal,
        is_open=False,
        centered=True,
        backdrop="static",
    )


def _new_investment_modal(ids: _Ids) -> dbc.Modal:
    category_options = [
        {"label": INVESTMENT_DISPLAY[c], "value": c}
        for c in INVESTMENT_CATEGORIES
    ]
    return dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("📊 Log New Investment")),
            dbc.ModalBody([
                dbc.Label("Asset Type", className="fw-medium"),
                dcc.Dropdown(id=ids.new_inv_category, options=category_options,
                             placeholder="Select asset type...", clearable=False),
                dbc.Label("Amount (₪)", className="fw-medium mt-3"),
                dbc.Input(id=ids.new_inv_amount, type="number",
                          placeholder="e.g. 5000", min=1, step=1),
                dbc.Label("Name / Description", className="fw-medium mt-3"),
                dbc.Input(id=ids.new_inv_name, type="text",
                          placeholder="e.g. S&P 500 ETF"),
                dbc.Label("Ticker (optional)", className="fw-medium mt-3"),
                dbc.Input(id=ids.new_inv_ticker, type="text", placeholder="e.g. SPY"),
                html.Div(id=ids.new_inv_status, className="mt-3 small text-danger"),
            ]),
            dbc.ModalFooter(
                dbc.Button("Save Investment", id=ids.new_inv_submit_btn,
                           color="primary", n_clicks=0)
            ),
        ],
        id=ids.new_inv_modal,
        is_open=False,
        centered=True,
        backdrop="static",
    )


def _edit_investment_modal(ids: _Ids) -> dbc.Modal:
    return dbc.Modal(
        [
            dbc.ModalHeader(dbc.ModalTitle("✏️ Edit Investment")),
            dbc.ModalBody([
                dbc.Label("Asset Type", className="fw-medium"),
                html.P(id=ids.edit_inv_category_display,
                       className="fw-bold text-primary mb-3"),
                dbc.Label("Amount (₪)", className="fw-medium"),
                dbc.Input(id=ids.edit_inv_amount, type="number", min=0, step=1),
                dbc.Label("Name / Description", className="fw-medium mt-3"),
                dbc.Input(id=ids.edit_inv_name, type="text"),
                dbc.Label("Ticker (optional)", className="fw-medium mt-3"),
                dbc.Input(id=ids.edit_inv_ticker, type="text"),
                html.P(
                    "Editing the amount adjusts book value only — your Pot is not affected.",
                    className="text-muted small mt-3 mb-0",
                ),
                html.Div(id=ids.edit_inv_status, className="mt-2 small text-danger"),
            ]),
            dbc.ModalFooter(
                dbc.Button("Save Changes", id=ids.edit_inv_submit_btn,
                           color="warning", n_clicks=0)
            ),
        ],
        id=ids.edit_inv_modal,
        is_open=False,
        centered=True,
        backdrop="static",
    )


def _holdings_table(ids: _Ids) -> dash_table.DataTable:
    return dash_table.DataTable(
        id=ids.holdings_table,
        columns=[
            {"name": "Category",   "id": "category_display", "editable": False},
            {"name": "Name",       "id": "name",              "editable": False},
            {"name": "Amount (₪)", "id": "amount",            "editable": False,
             "type": "numeric", "format": {"specifier": ",.0f"}},
            {"name": "Ticker",     "id": "ticker",            "editable": False},
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


def _surplus_panel(ids: _Ids, year_options: list, month_options: list) -> dbc.Row:
    return dbc.Row(
        dbc.Col(
            html.Div(
                [
                    html.H5("💡 Monthly Budget Surplus",
                            className="fw-bold text-muted mb-1"),
                    html.P(
                        "See how much you under-spent vs your budget "
                        "and transfer the surplus directly into your Pot.",
                        className="text-muted mb-3",
                        style={"fontSize": "0.875rem"},
                    ),
                    html.Div(
                        [
                            html.Span("Month:", className="fw-bold me-2 text-muted"),
                            dcc.Dropdown(id=ids.surplus_year, options=year_options,
                                         clearable=False, style={"width": "110px"}),
                            dcc.Dropdown(id=ids.surplus_month, options=month_options,
                                         clearable=False, style={"width": "110px"},
                                         className="ms-2"),
                        ],
                        className="d-flex align-items-center mb-3",
                    ),
                    html.Div(id=ids.surplus_display, className="mb-3"),
                    html.Div(
                        [
                            html.Span("Transfer amount (₪):", className="fw-medium me-2"),
                            dbc.Input(id=ids.surplus_transfer_amount, type="number",
                                      min=0, step=1, style={"width": "140px"},
                                      className="me-3"),
                            dbc.Button("➡ Add to My Pot", id=ids.surplus_transfer_btn,
                                       color="info", size="sm", disabled=True, n_clicks=0),
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
    )


# ── Public entry point ─────────────────────────────────────────────────────────

def get_investments_layout() -> dbc.Container:
    """Builds and returns the complete static layout for the Investments tab."""
    ids = _Ids()
    today = datetime.today()
    year_options  = [{"label": str(y), "value": y}
                     for y in range(2023, today.year + 2)]
    month_options = [{"label": calendar.month_abbr[m], "value": m}
                     for m in range(1, 13)]

    return dbc.Container(
        fluid=True,
        children=[
            # ── Hidden state stores ───────────────────────────────────────────
            dcc.Store(id=ids.add_funds_store, data=0),
            dcc.Store(id=ids.new_inv_store,   data=0),
            dcc.Store(id=ids.edit_inv_store,  data=0),
            dcc.Store(id=ids.surplus_store,   data=0),
            dcc.Store(id=ids.edit_inv_id_store, data=None),

            # ── Modals (in DOM from initial render, toggled via is_open) ──────
            _add_funds_modal(ids),
            _new_investment_modal(ids),
            _edit_investment_modal(ids),

            # ── Payer selector ────────────────────────────────────────────────
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

            # ── Zone 1: KPI cards ─────────────────────────────────────────────
            dbc.Row(
                [
                    _kpi_card("Net Worth",          ids.net_worth,      "💼", "#2c3e50"),
                    _kpi_card("Total Invested",      ids.total_invested,  "📈", "#2980b9"),
                    _kpi_card("The Pot (Available)", ids.pot_balance,     "💰", "#27ae60"),
                ],
                className="mb-4",
            ),

            # ── Zone 2: Budget surplus panel ──────────────────────────────────
            _surplus_panel(ids, year_options, month_options),

            # ── Zone 3: Action buttons ────────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.H5("Actions", className="fw-bold text-muted mb-3"),
                            html.Div(
                                [
                                    dbc.Button("➕ Add Funds", id=ids.add_funds_open_btn,
                                               color="success", size="lg",
                                               className="px-4", n_clicks=0),
                                    dbc.Button("📊 New Investment", id=ids.new_inv_open_btn,
                                               color="primary", size="lg",
                                               className="px-4", n_clicks=0),
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

            # ── Zone 4: Current holdings table ────────────────────────────────
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.Div(
                                [
                                    html.H5("Current Holdings",
                                            className="fw-bold text-muted mb-0"),
                                    dbc.Button("✏️ Edit Selected",
                                               id=ids.edit_inv_open_btn,
                                               color="warning", size="sm",
                                               disabled=True, n_clicks=0),
                                ],
                                className="d-flex justify-content-between align-items-center mb-3",
                            ),
                            _holdings_table(ids),
                        ],
                        className="bg-white p-4 rounded shadow-sm",
                    ),
                    xs=12,
                ),
                className="mb-4",
            ),

            # ── Zone 5: Asset allocation donut chart ──────────────────────────
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.H5("Asset Allocation",
                                    className="fw-bold text-muted mb-1"),
                            html.P(
                                '"Cash / Unallocated" is The Pot. '
                                'It shrinks as you log investments.',
                                className="text-muted mb-3",
                                style={"fontSize": "0.875rem"},
                            ),
                            dcc.Graph(id=ids.donut_chart,
                                      config={"displayModeBar": False},
                                      style={"height": "480px"}),
                        ],
                        className="bg-white p-4 rounded shadow-sm",
                    ),
                    xs=12,
                ),
            ),
        ],
    )
