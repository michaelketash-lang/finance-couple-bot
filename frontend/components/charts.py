"""
components/charts.py
====================

Reusable Plotly chart components for the finance bot frontend.

Provides a donut pie chart for category spending breakdown and a bar chart
for monthly spending trends. Both use a fixed color palette keyed to the
10 predefined expense categories so colors remain consistent across views.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import calendar
import datetime

CATEGORIES = [
    "Rent", "Utilities", "Groceries", "Eating Out", "Transport",
    "Maintenance", "Shopping", "Health", "Leisure", "Other"
]

CATEGORY_COLORS = {
    "Rent": "#264653",
    "Utilities": "#2a9d8f",
    "Groceries": "#e9c46a",
    "Eating Out": "#f4a261",
    "Transport": "#e76f51",
    "Maintenance": "#8ab17d",
    "Shopping": "#babb74",
    "Health": "#e07a5f",
    "Leisure": "#3d5a80",
    "Other": "#98c1d9"
}

EMPTY_COLOR = "#f0f0f0"


def category_pie_chart(df: pd.DataFrame = None,
                       summary_dict: dict = None) -> go.Figure:
    """Build a fixed-color donut chart showing spending across all 10 categories.

    Accepts either a raw DataFrame (used after inline edits) or a pre-aggregated
    summary dict (used on initial load for speed). Falls back to an empty state
    if neither is provided or both are empty.

    :param df: Optional raw expense DataFrame with ``amount`` and ``category`` columns.
    :param summary_dict: Optional pre-aggregated ``{category: total}`` dict from the API.
    :returns: A ``go.Figure`` donut chart with a fixed legend and hover labels.
    """
    labels = []
    values = []
    colors = []
    hovertemplates = []
    text_info = []
    total_spent = 0.0

    if df is not None and not df.empty:
        # Edit mode: recalculate totals directly from the table data
        dff = df.copy()
        dff["amount"] = pd.to_numeric(dff.get("amount", 0), errors="coerce").fillna(0.0)
        dff["category"] = dff.get("category", "Other").fillna("Other")
        actual_totals_df = dff.groupby("category")["amount"].sum().reset_index()
        actual_totals = dict(zip(actual_totals_df["category"], actual_totals_df["amount"]))
    elif summary_dict:
        actual_totals = summary_dict
    else:
        actual_totals = {}

    for cat in CATEGORIES:
        amt = float(actual_totals.get(cat, 0.0))
        total_spent += amt

        labels.append(cat)
        hovertemplates.append(f"<b>{cat}</b><br>₪{amt:,.0f}<extra></extra>")

        if amt > 0:
            values.append(amt)
            colors.append(CATEGORY_COLORS.get(cat, "#cccccc"))
            text_info.append(f"₪{amt:,.0f}")
        else:
            values.append(0.0)
            colors.append(EMPTY_COLOR)  # Slice won't show, but legend entry will
            text_info.append("")

    # Only show inline labels for slices that are large enough to read
    if total_spent > 0:
        final_text_info = []
        for i, val in enumerate(values):
            if val > 0 and (val / total_spent) > 0.05:
                final_text_info.append(text_info[i])
            else:
                final_text_info.append("")
    else:
        final_text_info = [""] * len(labels)

    if total_spent == 0:
        # Render a grey placeholder donut with the full category legend still visible
        fig = go.Figure(
            go.Pie(
                labels=labels,
                values=[0.0] * len(labels),
                marker=dict(colors=[CATEGORY_COLORS.get(l) for l in labels]),
                showlegend=True,
                hole=0.6,
                sort=False
            )
        )
        fig.add_trace(
            go.Pie(
                labels=["No Expenses"],
                values=[1],
                marker=dict(colors=[EMPTY_COLOR]),
                textinfo="none",
                hovertemplate="<b>No Expenses this month</b><extra></extra>",
                showlegend=False,
                hole=0.6,
                sort=False
            )
        )
    else:
        fig = go.Figure(
            go.Pie(
                labels=labels,
                values=values,
                marker=dict(colors=colors, line=dict(color='white', width=1)),
                hole=0.6,
                text=final_text_info,
                textposition="inside",
                texttemplate="%{text}",
                hovertemplate=hovertemplates,
                sort=False,  # Preserve CATEGORIES list order for a consistent legend
                showlegend=True
            )
        )

    fig.update_layout(
        title=f"Breakdown: ₪{total_spent:,.0f}" if total_spent > 0 else "Breakdown",
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02,
            font=dict(size=11),
        ),
        hoverlabel=dict(bgcolor="rgba(0,0,0,0.8)", font=dict(color="white")),
    )
    return fig


def monthly_trends_bar_chart(summary_dict: dict = None,
                             year: int = datetime.date.today().year) -> go.Figure:
    """Build a 12-month spending trend bar chart with an average line.

    Always renders all 12 months (zero-filling missing months). The average
    line is calculated only from months that have non-zero spending.

    :param summary_dict: Pre-aggregated ``{"MM": total}`` dict from the API.
    :param year: The year being displayed, used in the chart title.
    :returns: A ``go.Figure`` bar chart with an optional dashed average line.
    """
    # Initialize all 12 months to 0.0 so the x-axis is always complete
    all_months = pd.DataFrame({
        "month_num": [f"{m:02d}" for m in range(1, 13)],
        "month_label": [calendar.month_abbr[m] for m in range(1, 13)],
        "amount": 0.0
    })

    for m_str, amt in summary_dict.items():
        if m_str in all_months['month_num'].values:
            all_months.loc[all_months['month_num'] == m_str, 'amount'] = float(amt)

    x = all_months["month_label"].tolist()
    y = all_months["amount"].tolist()

    non_zero_months = [val for val in y if val > 0]
    avg_monthly = float(sum(non_zero_months) / len(non_zero_months)) if non_zero_months else 0.0

    BAR_COLOR = "#38b2ac"

    fig = go.Figure(
        go.Bar(
            x=x,
            y=y,
            marker=dict(color=BAR_COLOR),
            hovertemplate="<b>%{x}</b><br>₪%{y:,.0f}<extra></extra>",
        )
    )

    if avg_monthly > 0:
        fig.add_hline(
            y=avg_monthly,
            line_dash="dash",
            line_color="#e53e3e",
            line_width=2,
            annotation_text=f"Avg: ₪{avg_monthly:,.0f}",
            annotation_position="top right",
        )

    fig.update_layout(
        title=f"Monthly Spending Trend ({year})",
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
        yaxis=dict(tickprefix="₪", separatethousands=True),
        plot_bgcolor="rgba(0,0,0,0)"
    )

    return fig
