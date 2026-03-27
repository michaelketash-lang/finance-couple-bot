from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import calendar

# 1. Define a fixed, professional color palette for all categories
CATEGORY_COLORS = {
    "Rent": "#264653",  # Dark Slate
    "Utilities": "#2a9d8f",  # Teal
    "Groceries": "#e9c46a",  # Yellow/Gold
    "Eating Out": "#f4a261",  # Orange
    "Transport": "#e76f51",  # Burnt Orange
    "Maintenance": "#8ab17d",  # Olive Green
    "Shopping": "#babb74",  # Light Olive
    "Health": "#e07a5f",  # Coral
    "Leisure": "#3d5a80",  # Steel Blue
    "Other": "#98c1d9"  # Light Blue
}


def category_pie_chart(df: pd.DataFrame) -> go.Figure:
    """
    Pie chart: Breakdown by category with fixed colors.
    """
    if df is None or df.empty:
        fig = go.Figure()
        fig.update_layout(margin=dict(l=10, r=10, t=30, b=10))
        return fig

    dff = df.copy()
    dff["amount"] = pd.to_numeric(dff.get("amount", 0), errors="coerce").fillna(
        0.0)
    dff["category"] = dff.get("category", "Other").fillna("Other")

    totals = (
        dff.groupby("category", dropna=False)["amount"]
        .sum()
        .sort_values(ascending=False)
    )

    # Filter out categories with 0 to keep the pie chart clean
    totals = totals[totals > 0]

    # Map the fixed colors to the categories present in the data
    colors = [CATEGORY_COLORS.get(cat, "#cccccc") for cat in totals.index]

    fig = go.Figure(
        go.Pie(
            labels=totals.index.astype(str),
            values=totals.values,
            marker=dict(colors=colors),
            texttemplate="%{percent:.1%}<br>₪%{value:,.0f}",
            hovertemplate="<b>%{label}</b><br>%{percent:.1%}<br>₪%{value:,.0f}<extra></extra>",
            sort=False  # Keep the order we defined
        )
    )

    fig.update_layout(
        title="Expenses by Category",
        margin=dict(l=10, r=10, t=40, b=10),
        legend=dict(orientation="h"),
        hoverlabel=dict(bgcolor="rgba(0,0,0,0.75)", font=dict(color="white")),
    )
    return fig


def monthly_trends_bar_chart(df: pd.DataFrame, year: int) -> go.Figure:
    """
    Monthly trends bar chart. Always displays 12 months for the given year.
    """
    # Create a base DataFrame with all 12 months set to 0.0
    all_months = pd.DataFrame({
        "month_num": range(1, 13),
        "month_label": [calendar.month_abbr[m] for m in range(1, 13)],
        "amount": 0.0
    })

    if df is not None and not df.empty:
        dff = df.copy()
        dff["amount"] = pd.to_numeric(dff.get("amount", 0),
                                      errors="coerce").fillna(0.0)
        dff["date"] = pd.to_datetime(dff.get("date"), errors="coerce")
        dff = dff.dropna(subset=["date"])

        # Only process data for the requested year
        dff = dff[dff["date"].dt.year == year]

        if not dff.empty:
            dff["month_num"] = dff["date"].dt.month

            # Sum amounts by month
            monthly_sums = dff.groupby("month_num")[
                "amount"].sum().reset_index()

            # Update the base DataFrame with actual sums using map
            amount_map = dict(
                zip(monthly_sums["month_num"], monthly_sums["amount"]))
            all_months["amount"] = all_months["month_num"].map(
                amount_map).fillna(0.0)

    x = all_months["month_label"].tolist()
    y = all_months["amount"].tolist()

    # Calculate average only for months that have passed or have data
    non_zero_months = [val for val in y if val > 0]
    avg_monthly = float(
        sum(non_zero_months) / len(non_zero_months)) if non_zero_months else 0.0

    fig = go.Figure(
        go.Bar(
            x=x,
            y=y,
            marker=dict(color="rgba(54, 162, 235, 0.85)"),
            hovertemplate="<b>%{x}</b><br>₪%{y:,.0f}<extra></extra>",
        )
    )

    if avg_monthly > 0:
        fig.add_hline(
            y=avg_monthly,
            line_dash="dash",
            line_color="red",
            line_width=2,
            annotation_text=f"Avg: ₪{avg_monthly:,.0f}",
            annotation_position="top right",
        )

    fig.update_layout(
        title=f"Monthly Spending Trend ({year})",
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
        yaxis=dict(tickprefix="₪", separatethousands=True),
    )

    return fig
