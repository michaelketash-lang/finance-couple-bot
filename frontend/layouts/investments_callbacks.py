"""
investments_callbacks.py
────────────────────────
Owns all reactive logic for the Investments tab.

Each callback has one clear job:
  1. _update_main_display   — refresh KPIs, donut chart, and holdings table
  2. _update_surplus        — calculate and display the monthly budget surplus
  3. _transfer_surplus      — move surplus cash into the selected payer's Pot
  4. _toggle_edit_btn       — enable/disable "Edit Selected" based on table selection
  5. _handle_add_funds      — open/submit the Add Funds modal
  6. _handle_new_investment — open/submit the New Investment modal
  7. _handle_edit_investment — open with pre-filled data / submit the Edit modal

Import contract:
  Layout IDs and domain constants come from investments_layout.py.
  API calls come from api_client.py.
  No HTML assembly happens here.
"""
from __future__ import annotations

import calendar

import plotly.graph_objects as go
from dash import Dash, Input, Output, State, ctx, html, no_update

from api_client import (
    fetch_investments_summary,
    fetch_all_investments,
    fetch_all_budgets,
    fetch_raw_expenses,
    add_funds_to_pot,
    log_investment,
    update_investment_record,
)
from layouts.investments_layout import (
    _Ids,
    INVESTMENT_CATEGORIES,
    INVESTMENT_DISPLAY,
    ALLOCATION_COLORS,
)


# ── Chart builder (pure function, no side-effects) ─────────────────────────────

def _build_donut_chart(allocation: dict, pot_balance: float, payer: str) -> go.Figure:
    """
    Builds the asset allocation donut chart.
    The Pot always gets its own 'Cash / Unallocated' slice so the visual
    shrinks as money moves from pot → investments.
    """
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
        return _empty_donut(payer)

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
        legend=dict(orientation="h", yanchor="bottom", y=-0.18,
                    xanchor="center", x=0.5),
        hoverlabel=dict(bgcolor="rgba(0,0,0,0.8)", font=dict(color="white")),
    )
    return fig


def _empty_donut(payer: str) -> go.Figure:
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


# ── Surplus calculation helper ─────────────────────────────────────────────────

def _calc_surplus(year: int, month: int) -> tuple[float, float, float]:
    """
    Returns (total_budget, total_actual, surplus) for the given month.
    Surplus is clamped to 0 — negative means over budget, not a negative surplus.
    """
    df_budgets  = fetch_all_budgets()
    total_budget = float(df_budgets['monthly_target'].sum()) if not df_budgets.empty else 0.0

    df_expenses  = fetch_raw_expenses(year, month, split='')
    total_actual = float(df_expenses['amount'].sum()) if not df_expenses.empty else 0.0

    surplus = max(0.0, total_budget - total_actual)
    return total_budget, total_actual, surplus


# ── Callback registration ──────────────────────────────────────────────────────

def register_investments_callbacks(app: Dash) -> None:
    ids = _Ids()

    # ── 1. Refresh KPIs, donut chart, and holdings table ──────────────────────
    #
    # Triggered by: payer switch OR any successful form submission.
    # All four refresh stores are inputs so a single write to any of them
    # causes the display to re-fetch from the API.
    @app.callback(
        Output(ids.net_worth,      "children"),
        Output(ids.total_invested, "children"),
        Output(ids.pot_balance,    "children"),
        Output(ids.donut_chart,    "figure"),
        Output(ids.holdings_table, "data"),
        Input(ids.payer_radio,    "value"),
        Input(ids.add_funds_store, "data"),
        Input(ids.new_inv_store,   "data"),
        Input(ids.edit_inv_store,  "data"),
        Input(ids.surplus_store,   "data"),
    )
    def _update_main_display(payer, _add, _new, _edit, _surplus):
        summary    = fetch_investments_summary(payer)
        allocation = summary.get('allocation', {})
        pot        = summary.get('pot_balance', 0.0)

        fmt  = lambda v: f"₪{v:,.0f}"
        fig  = _build_donut_chart(allocation, pot, payer)
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

    # ── 2. Calculate and display the monthly budget surplus ───────────────────
    #
    # Runs whenever the user changes the year/month dropdowns, or after a
    # surplus transfer (surplus_store bump) so the panel resets.
    @app.callback(
        Output(ids.surplus_display,         "children"),
        Output(ids.surplus_transfer_amount, "value"),
        Output(ids.surplus_transfer_btn,    "disabled"),
        Input(ids.surplus_year,  "value"),
        Input(ids.surplus_month, "value"),
        Input(ids.surplus_store, "data"),
    )
    def _update_surplus(year, month, _ts):
        if not year or not month:
            return "Select a month to see the surplus.", None, True

        total_budget, total_actual, surplus = _calc_surplus(int(year), int(month))
        month_label = f"{calendar.month_abbr[int(month)]} {year}"

        if total_budget == 0:
            return html.P("No budget set for this month yet.",
                          className="text-muted mb-0"), None, True

        color = "text-success" if surplus > 0 else "text-danger"
        label = "surplus" if surplus > 0 else "over budget"

        display = html.Div([
            html.Span(f"{month_label}:  ", className="text-muted"),
            html.Span(f"Budget ₪{total_budget:,.0f}", className="fw-medium"),
            html.Span("  vs  ", className="text-muted"),
            html.Span(f"Actual ₪{total_actual:,.0f}", className="fw-medium"),
            html.Span(f"  →  ₪{surplus:,.0f} {label}",
                      className=f"fw-bold {color} ms-1"),
        ])

        return display, (surplus if surplus > 0 else None), (surplus <= 0)

    # ── 3. Transfer the surplus amount to the selected payer's Pot ────────────
    @app.callback(
        Output(ids.surplus_status, "children"),
        Output(ids.surplus_store,  "data"),
        Input(ids.surplus_transfer_btn, "n_clicks"),
        State(ids.surplus_transfer_amount, "value"),
        State(ids.payer_radio,   "value"),
        State(ids.surplus_year,  "value"),
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
            msg = html.Span(
                f"✓ ₪{float(amount):,.0f} added to {payer}'s Pot.",
                className="text-success fw-medium",
            )
            return msg, ts + 1

        return html.Span("Failed to transfer. Please try again.",
                         className="text-danger"), ts

    # ── 4. Gate the Edit button on whether a table row is selected ────────────
    @app.callback(
        Output(ids.edit_inv_open_btn, "disabled"),
        Input(ids.holdings_table, "selected_rows"),
    )
    def _toggle_edit_btn(selected_rows):
        return not bool(selected_rows)

    # ── 5. Add Funds modal — open / validate / submit ─────────────────────────
    @app.callback(
        Output(ids.add_funds_modal,  "is_open"),
        Output(ids.add_funds_status, "children"),
        Output(ids.add_funds_store,  "data"),
        Input(ids.add_funds_open_btn,   "n_clicks"),
        Input(ids.add_funds_submit_btn, "n_clicks"),
        State(ids.add_funds_modal,  "is_open"),
        State(ids.add_funds_amount, "value"),
        State(ids.add_funds_note,   "value"),
        State(ids.payer_radio,      "value"),
        State(ids.add_funds_store,  "data"),
        prevent_initial_call=True,
    )
    def _handle_add_funds(open_clicks, submit_clicks, is_open,
                          amount, note, payer, ts):
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

    # ── 6. New Investment modal — open / validate / submit ────────────────────
    @app.callback(
        Output(ids.new_inv_modal,  "is_open"),
        Output(ids.new_inv_status, "children"),
        Output(ids.new_inv_store,  "data"),
        Input(ids.new_inv_open_btn,   "n_clicks"),
        Input(ids.new_inv_submit_btn, "n_clicks"),
        State(ids.new_inv_modal,    "is_open"),
        State(ids.new_inv_category, "value"),
        State(ids.new_inv_amount,   "value"),
        State(ids.new_inv_name,     "value"),
        State(ids.new_inv_ticker,   "value"),
        State(ids.payer_radio,      "value"),
        State(ids.new_inv_store,    "data"),
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

    # ── 7. Edit Investment modal — open with pre-fill / validate / submit ─────
    #
    # Opening: reads the selected table row and pre-fills amount/name/ticker.
    # Submitting: reads those same fields as State and calls the update API.
    # A component can be both an Output (written on open) and a State
    # (read on submit) within the same Dash callback — this is intentional.
    @app.callback(
        Output(ids.edit_inv_modal,            "is_open"),
        Output(ids.edit_inv_amount,           "value"),
        Output(ids.edit_inv_name,             "value"),
        Output(ids.edit_inv_ticker,           "value"),
        Output(ids.edit_inv_category_display, "children"),
        Output(ids.edit_inv_id_store,         "data"),
        Output(ids.edit_inv_status,           "children"),
        Output(ids.edit_inv_store,            "data"),
        Input(ids.edit_inv_open_btn,   "n_clicks"),
        Input(ids.edit_inv_submit_btn, "n_clicks"),
        State(ids.edit_inv_modal,    "is_open"),
        State(ids.edit_inv_amount,   "value"),
        State(ids.edit_inv_name,     "value"),
        State(ids.edit_inv_ticker,   "value"),
        State(ids.edit_inv_id_store, "data"),
        State(ids.holdings_table,    "selected_rows"),
        State(ids.holdings_table,    "data"),
        State(ids.edit_inv_store,    "data"),
        prevent_initial_call=True,
    )
    def _handle_edit_investment(open_clicks, submit_clicks, is_open,
                                amt_val, name_val, ticker_val, inv_id,
                                selected_rows, table_data, ts):
        triggered = ctx.triggered_id

        if triggered == ids.edit_inv_open_btn:
            if not selected_rows or not table_data:
                return (is_open, no_update, no_update, no_update,
                        no_update, inv_id, "Select a row first.", ts)
            row         = table_data[selected_rows[0]]
            cat_display = INVESTMENT_DISPLAY.get(row.get('category', ''),
                                                 row.get('category', ''))
            return (True, row['amount'], row['name'], row.get('ticker', ''),
                    cat_display, row['id'], "", ts)

        if triggered == ids.edit_inv_submit_btn:
            if amt_val is None or float(amt_val) < 0:
                return (True, amt_val, name_val, ticker_val,
                        no_update, inv_id, "Please enter a valid amount.", ts)
            if not name_val or not str(name_val).strip():
                return (True, amt_val, name_val, ticker_val,
                        no_update, inv_id, "Name cannot be empty.", ts)

            success = update_investment_record(
                inv_id=inv_id,
                amount=float(amt_val),
                name=str(name_val).strip(),
                ticker=str(ticker_val).strip() if ticker_val else None,
            )
            if success:
                return (False, None, None, None, no_update, None, "", ts + 1)
            return (True, amt_val, name_val, ticker_val,
                    no_update, inv_id, "Failed to update. Please try again.", ts)

        return (is_open, no_update, no_update, no_update, no_update, inv_id, "", ts)
