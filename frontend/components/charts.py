from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go


def category_pie_chart(df: pd.DataFrame) -> go.Figure:
    """
    Pie chart: Breakdown by category.

    - Labels show % and ILS (₪).
    """
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
        return fig

    dff = df.copy()
    dff["amount"] = pd.to_numeric(dff.get("amount", 0), errors="coerce").fillna(0.0)
    dff["category"] = dff.get("category", "Other").fillna("Other")

    totals = (
        dff.groupby("category", dropna=False)["amount"]
        .sum()
        .sort_values(ascending=False)
    )

    fig = go.Figure(
        go.Pie(
            labels=totals.index.astype(str),
            values=totals.values,
            texttemplate="%{percent:.1%}<br>₪%{value:,.0f}",
            hovertemplate="<b>%{label}</b><br>%{percent:.1%}<br>₪%{value:,.0f}<extra></extra>",
        )
    )

    fig.update_layout(
        title="Expenses by Category",
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h"),
        hoverlabel=dict(bgcolor="rgba(0,0,0,0.75)", font=dict(color="white")),
    )
    return fig


def monthly_trends_bar_chart(df: pd.DataFrame) -> go.Figure:
    """
    Monthly trends bar chart.

    - X = Months
    - Y = Total Amount
    - Adds a horizontal red dashed line for Average Monthly Spending
      across all bars.
    """
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
        return fig

    dff = df.copy()
    dff["amount"] = pd.to_numeric(dff.get("amount", 0), errors="coerce").fillna(0.0)
    dff["date"] = pd.to_datetime(dff.get("date"), errors="coerce")
    dff = dff.dropna(subset=["date"])

    if dff.empty:
        fig = go.Figure()
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
        return fig

    dff["month_id"] = dff["date"].dt.to_period("M").astype(str)  # YYYY-MM
    dff["month_label"] = dff["date"].dt.strftime("%b")  # Jan..Dec

    monthly = (
        dff.groupby(["month_id", "month_label"], as_index=False)["amount"]
        .sum()
        .sort_values("month_id")
    )

    x = monthly["month_label"].tolist()
    y = monthly["amount"].tolist()

    avg_monthly = float(pd.Series(y).mean()) if y else 0.0

    fig = go.Figure(
        go.Bar(
            x=x,
            y=y,
            marker=dict(color="rgba(54, 162, 235, 0.85)"),
            hovertemplate="<b>%{x}</b><br>₪%{y:,.0f}<extra></extra>",
        )
    )

    fig.add_hline(
        y=avg_monthly,
        line_dash="dash",
        line_color="red",
        line_width=2,
        annotation_text=f"Avg: ₪{avg_monthly:,.0f}",
        annotation_position="top right",
    )

    fig.update_layout(
        title="Monthly Spending Trend",
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
        yaxis=dict(tickprefix="₪", separatethousands=True),
    )

    return fig

