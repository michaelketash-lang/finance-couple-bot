from __future__ import annotations

from dataclasses import dataclass

import plotly.graph_objects as go
import dash_bootstrap_components as dbc
from dash import Dash, Input, Output, State, ctx, dcc, html, no_update

from api_client import fetch_investments_summary, add_funds_to_pot, log_investment


INVESTMENT_CATEGORIES = ['stocks', 'bonds', 'cash', 'pension', 'gemel', 'hishtalmut']

INVESTMENT_DISPLAY = {
    'stocks': 'Stocks',
    'bonds': 'Bonds',
    'cash': 'Cash',
    'pension': 'Pension',
    'gemel': 'Gemel',
    'hishtalmut': 'Hishtalmut',
}

# Fixed colors per asset class + The Pot slice
ALLOCATION_COLORS = {
    'stocks': '#3498db',       # Blue
    'bonds': '#e67e22',        # Orange
    'cash': '#9b59b6',         # Purple
    'pension': '#e74c3c',      # Red
    'gemel': '#f39c12',        # Amber
    'hishtalmut': '#1abc9c',   # Teal
    'pot': '#2ecc71',          # Light green — Cash / Unallocated
}


@dataclass(frozen=True)
class _Ids:
    # KPI outputs
    net_worth: str = "inv-net-worth"
    total_invested: str = "inv-total-invested"
    pot_balance: str = "inv-pot-balance"

    # Chart
    donut_chart: str = "inv-donut-chart"

    # Add Funds modal
    add_funds_modal: str = "inv-add-funds-modal"
    add_funds_open_btn: str = "inv-add-funds-open-btn"
    add_funds_amount: str = "inv-add-funds-amount"
    add_funds_note: str = "inv-add-funds-note"
    add_funds_submit_btn: str = "inv-add-funds-submit-btn"
    add_funds_status: str = "inv-add-funds-status"
    add_funds_store: str = "inv-add-funds-store"   # refresh trigger

    # New Investment modal
    new_inv_modal: str = "inv-new-inv-modal"
    new_inv_open_btn: str = "inv-new-inv-open-btn"
    new_inv_category: str = "inv-new-inv-category"
    new_inv_amount: str = "inv-new-inv-amount"
    new_inv_name: str = "inv-new-inv-name"
    new_inv_ticker: str = "inv-new-inv-ticker"
    new_inv_submit_btn: str = "inv-new-inv-submit-btn"
    new_inv_status: str = "inv-new-inv-status"
    new_inv_store: str = "inv-new-inv-store"       # refresh trigger


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
            dbc.ModalHeader(dbc.ModalTitle("💰 Add Funds to The Pot")),
            dbc.ModalBody(
                [
                    dbc.Label("Amount (₪)", className="fw-medium"),
                    dbc.Input(
                        id=ids.add_funds_amount,
                        type="number",
                        placeholder="e.g. 3000",
                        min=1,
                        step=1,
                    ),
                    dbc.Label("Note (optional)", className="fw-medium mt-3"),
                    dbc.Input(
                        id=ids.add_funds_note,
                        type="text",
                        placeholder="e.g. December bonus",
                    ),
                    html.Div(id=ids.add_funds_status, className="mt-3 small text-danger"),
                ]
            ),
            dbc.ModalFooter(
                [
                    dbc.Button(
                        "Add Funds",
                        id=ids.add_funds_submit_btn,
                        color="success",
                        n_clicks=0,
                    ),
                ]
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
            dbc.ModalBody(
                [
                    dbc.Label("Asset Type", className="fw-medium"),
                    dcc.Dropdown(
                        id=ids.new_inv_category,
                        options=category_options,
                        placeholder="Select asset type...",
                        clearable=False,
                    ),
                    dbc.Label("Amount (₪)", className="fw-medium mt-3"),
                    dbc.Input(
                        id=ids.new_inv_amount,
                        type="number",
                        placeholder="e.g. 5000",
                        min=1,
                        step=1,
                    ),
                    dbc.Label("Name / Description", className="fw-medium mt-3"),
                    dbc.Input(
                        id=ids.new_inv_name,
                        type="text",
                        placeholder="e.g. S&P 500 ETF",
                    ),
                    dbc.Label("Ticker (optional)", className="fw-medium mt-3"),
                    dbc.Input(
                        id=ids.new_inv_ticker,
                        type="text",
                        placeholder="e.g. SPY",
                    ),
                    html.Div(id=ids.new_inv_status, className="mt-3 small text-danger"),
                ]
            ),
            dbc.ModalFooter(
                [
                    dbc.Button(
                        "Save Investment",
                        id=ids.new_inv_submit_btn,
                        color="primary",
                        n_clicks=0,
                    ),
                ]
            ),
        ],
        id=ids.new_inv_modal,
        is_open=False,
        centered=True,
        backdrop="static",
    )


def _build_donut_chart(allocation: dict, pot_balance: float) -> go.Figure:
    """Builds the asset allocation donut chart including The Pot as its own slice."""
    labels, values, colors = [], [], []

    for cat in INVESTMENT_CATEGORIES:
        amt = allocation.get(cat, 0.0)
        if amt > 0:
            labels.append(INVESTMENT_DISPLAY[cat])
            values.append(amt)
            colors.append(ALLOCATION_COLORS[cat])

    # The Pot always gets a slice (even when 0, to signal it exists)
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
            annotations=[dict(text="₪0", x=0.5, y=0.5, font_size=22,
                              showarrow=False, font_color="#aaa")],
            margin=dict(l=20, r=20, t=60, b=20),
            title="Asset Allocation",
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
        title=f"Asset Allocation  •  Net Worth: ₪{total:,.0f}",
        annotations=[dict(
            text=f"₪{total:,.0f}",
            x=0.5, y=0.5,
            font=dict(size=18, color="#2c3e50", family="Arial"),
            showarrow=False,
        )],
        margin=dict(l=20, r=20, t=60, b=20),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.18,
            xanchor="center",
            x=0.5,
        ),
        hoverlabel=dict(bgcolor="rgba(0,0,0,0.8)", font=dict(color="white")),
    )
    return fig


# ── Layout ─────────────────────────────────────────────────────────────────────

def get_investments_layout() -> dbc.Container:
    ids = _Ids()

    return dbc.Container(
        fluid=True,
        children=[
            # Hidden stores used as refresh triggers between callbacks
            dcc.Store(id=ids.add_funds_store, data=0),
            dcc.Store(id=ids.new_inv_store, data=0),

            # Modals (always in DOM, toggled via is_open)
            _add_funds_modal(ids),
            _new_investment_modal(ids),

            # ── Zone 1: KPI Cards ──────────────────────────────────────────────
            dbc.Row(
                [
                    _kpi_card("Net Worth", ids.net_worth, "💼", "#2c3e50"),
                    _kpi_card("Total Invested", ids.total_invested, "📈", "#2980b9"),
                    _kpi_card("The Pot  (Available)", ids.pot_balance, "💰", "#27ae60"),
                ],
                className="mb-4",
            ),

            # ── Zone 2: Action Buttons ─────────────────────────────────────────
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.H5("Actions", className="fw-bold text-muted mb-3"),
                            html.Div(
                                [
                                    dbc.Button(
                                        ["➕  Add Funds"],
                                        id=ids.add_funds_open_btn,
                                        color="success",
                                        size="lg",
                                        className="me-3 px-4",
                                        n_clicks=0,
                                    ),
                                    dbc.Button(
                                        ["📊  New Investment"],
                                        id=ids.new_inv_open_btn,
                                        color="primary",
                                        size="lg",
                                        className="px-4",
                                        n_clicks=0,
                                    ),
                                ],
                                className="d-flex flex-wrap gap-2",
                            ),
                        ],
                        className="bg-white p-4 rounded shadow-sm",
                    ),
                    xs=12,
                ),
                className="mb-4",
            ),

            # ── Zone 3: Asset Allocation Donut Chart ───────────────────────────
            dbc.Row(
                dbc.Col(
                    html.Div(
                        [
                            html.H5("Asset Allocation", className="fw-bold text-muted mb-1"),
                            html.P(
                                'Each slice shows where your money sits. '
                                '"Cash / Unallocated" is The Pot — funds ready to deploy.',
                                className="text-muted mb-3",
                                style={"fontSize": "0.875rem"},
                            ),
                            dcc.Graph(
                                id=ids.donut_chart,
                                config={"displayModeBar": False},
                                style={"height": "480px"},
                            ),
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

    # ── Callback 1: Update KPIs + Donut Chart ─────────────────────────────────
    # Fires on initial load and whenever a form submission refreshes either store.
    @app.callback(
        Output(ids.net_worth, "children"),
        Output(ids.total_invested, "children"),
        Output(ids.pot_balance, "children"),
        Output(ids.donut_chart, "figure"),
        Input(ids.add_funds_store, "data"),
        Input(ids.new_inv_store, "data"),
    )
    def _update_investments_view(_add_ts, _new_ts):
        summary = fetch_investments_summary()
        net_worth = summary.get('net_worth', 0.0)
        total_invested = summary.get('total_invested', 0.0)
        pot = summary.get('pot_balance', 0.0)
        allocation = summary.get('allocation', {})

        fmt = lambda v: f"₪{v:,.0f}"
        fig = _build_donut_chart(allocation, pot)
        return fmt(net_worth), fmt(total_invested), fmt(pot), fig

    # ── Callback 2: Add Funds modal (open / submit / close) ───────────────────
    @app.callback(
        Output(ids.add_funds_modal, "is_open"),
        Output(ids.add_funds_status, "children"),
        Output(ids.add_funds_store, "data"),
        Input(ids.add_funds_open_btn, "n_clicks"),
        Input(ids.add_funds_submit_btn, "n_clicks"),
        State(ids.add_funds_modal, "is_open"),
        State(ids.add_funds_amount, "value"),
        State(ids.add_funds_note, "value"),
        State(ids.add_funds_store, "data"),
        prevent_initial_call=True,
    )
    def _handle_add_funds(open_clicks, submit_clicks, is_open, amount, note, ts):
        triggered = ctx.triggered_id

        if triggered == ids.add_funds_open_btn:
            return not is_open, "", ts

        if triggered == ids.add_funds_submit_btn:
            if not amount or float(amount) <= 0:
                return True, "Please enter a valid amount greater than 0.", ts
            success = add_funds_to_pot(float(amount), note or None)
            if success:
                return False, "", ts + 1   # close modal + trigger KPI refresh
            return True, "Failed to add funds. Please try again.", ts

        return is_open, "", ts

    # ── Callback 3: New Investment modal (open / submit / close) ──────────────
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
        State(ids.new_inv_store, "data"),
        prevent_initial_call=True,
    )
    def _handle_new_investment(open_clicks, submit_clicks, is_open,
                               category, amount, name, ticker, ts):
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
                ticker=ticker.strip() if ticker else None,
            )
            if success:
                return False, "", ts + 1   # close modal + trigger KPI refresh
            return (
                True,
                "Could not save — make sure The Pot has enough funds for this amount.",
                ts,
            )

        return is_open, "", ts
