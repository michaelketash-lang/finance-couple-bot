from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html


def budget_progress_card(
    category: str,
    actual: float,
    target: float,
) -> dbc.Card:
    """
    A single category progress card showing spent vs target as a labelled
    progress bar.

    Color logic:
      - No target set (target == 0)  → grey  / "No target set"
      - Under 80% spent              → green  (on track)
      - 80–99% spent                 → yellow (getting close)
      - 100%+ spent                  → red    (over budget)
    """
    if target <= 0:
        pct = 0.0
        bar_color = "secondary"
        spend_label = "No target set"
    else:
        pct = min((actual / target) * 100, 100.0)
        if pct >= 100:
            bar_color = "danger"
        elif pct >= 80:
            bar_color = "warning"
        else:
            bar_color = "success"
        spend_label = f"₪{actual:,.0f} of ₪{target:,.0f}"

    return dbc.Card(
        dbc.CardBody(
            [
                # Category name + percentage on the same row
                html.Div(
                    [
                        html.Span(category, className="fw-bold text-dark"),
                        html.Span(
                            f"{pct:.0f}%",
                            className="text-muted ms-auto",
                            style={"fontSize": "0.85rem"},
                        ),
                    ],
                    className="d-flex justify-content-between mb-2",
                ),
                # Progress bar
                dbc.Progress(
                    value=pct,
                    color=bar_color,
                    className="mb-2",
                    style={"height": "10px", "borderRadius": "6px"},
                ),
                # "₪X of ₪Y" label
                html.Small(spend_label, className="text-muted"),
            ]
        ),
        className="shadow-sm border-0 h-100",
        style={"backgroundColor": "#f8fafc"},
    )
