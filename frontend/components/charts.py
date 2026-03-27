from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import calendar

# 1. Define a Master Category List and fixed colors palette
CATEGORIES = [
    "Rent", "Utilities", "Groceries", "Eating Out", "Transport",
    "Maintenance", "Shopping", "Health", "Leisure", "Other"
]

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

EMPTY_COLOR = "#f0f0f0"


def category_pie_chart(df: pd.DataFrame = None,
                       summary_dict: dict = None) -> go.Figure:
    """
    Creates a fixed-color Donut Chart showing ALL categories.
    Accepts raw DataFrame (for edits) OR a pre-aggregated summary dict (for speed).
    """
    labels = []
    values = []
    colors = []
    hovertemplates = []
    text_info = []
    total_spent = 0.0

    # 1. Determine the source of data (Raw DF for edits, or Fast Summary)
    if df is not None and not df.empty:
        # Edit mode: Calculate totals from the table data
        dff = df.copy()
        dff["amount"] = pd.to_numeric(dff.get("amount", 0),
                                      errors="coerce").fillna(0.0)
        dff["category"] = dff.get("category", "Other").fillna("Other")
        actual_totals_df = dff.groupby("category")["amount"].sum().reset_index()
        actual_totals = dict(
            zip(actual_totals_df["category"], actual_totals_df["amount"]))
    elif summary_dict:
        # Speed mode: Use the pre-aggregated summary from the API
        actual_totals = summary_dict
    else:
        # Fallback empty mode
        actual_totals = {}

    # 2. Build the chart structure based on master CATEGORIES list (for fixed legend)
    for cat in CATEGORIES:
        # Get amount from our chosen source, defaulting to 0
        amt = float(actual_totals.get(cat, 0.0))
        total_spent += amt

        labels.append(cat)
        hovertemplates.append(f"<b>{cat}</b><br>₪{amt:,.0f}<extra></extra>")

        if amt > 0:
            values.append(amt)
            colors.append(CATEGORY_COLORS.get(cat, "#cccccc"))
            if amt > 0:  # Check later to only show text > 5% total_spent
                text_info.append(f"₪{amt:,.0f}")
            else:
                text_info.append("")
        else:
            values.append(0.0)
            colors.append(
                EMPTY_COLOR)  # Slice won't show, but legend entry will
            text_info.append("")

    # 3. Adjust text info based on percentage
    if total_spent > 0:
        final_text_info = []
        for i, val in enumerate(values):
            if val > 0 and (val / total_spent) > 0.05:
                final_text_info.append(text_info[i])
            else:
                final_text_info.append("")
    else:
        final_text_info = [""] * len(labels)

    # 4. Handle 'Zero Spending' state
    if total_spent == 0:
        hole_labels = ["No Expenses"]
        hole_values = [1]
        hole_colors = [EMPTY_COLOR]
        hole_hovertemplate = "<b>No Expenses this month</b><extra></extra>"

        # Main Pie Trace (Forces the full category legend to appear)
        fig = go.Figure(
            go.Pie(
                labels=labels,
                values=[0.0] * len(labels),  # All 0 so no slices show
                marker=dict(colors=[CATEGORY_COLORS.get(l) for l in labels]),
                showlegend=True,
                hole=0.6,
                sort=False
            )
        )
        # Add the 'Empty' grayplaceholder
        fig.add_trace(
            go.Pie(
                labels=hole_labels,
                values=hole_values,
                marker=dict(colors=hole_colors),
                textinfo="none",
                hovertemplate=hole_hovertemplate,
                showlegend=False,
                hole=0.6,
                sort=False
            )
        )
    else:
        # Normal scenario: Spending exists
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
                sort=False,  # Keep CATEGORIES list order
                showlegend=True
            )
        )

    # --- Universal Layout ---
    fig.update_layout(
        title=f"Breakdown: ₪{total_spent:,.0f}" if total_spent > 0 else "Breakdown",
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.12,
            xanchor="center",
            x=0.5
        ),
        hoverlabel=dict(bgcolor="rgba(0,0,0,0.8)", font=dict(color="white")),
    )
    return fig


def monthly_trends_bar_chart(summary_dict: dict = None,
                             year: int = datetime.date.today().year) -> go.Figure:
    """
    Monthly trends bar chart. Always displays 12 months.
    Accepts raw DataFrame (legacy) OR a pre-aggregated summary dict (for speed).
    """
    # Initialize the base DataFrame with all 12 months set to 0.0
    all_months = pd.DataFrame({
        "month_num": [f"{m:02d}" for m in range(1, 13)],
        "month_label": [calendar.month_abbr[m] for m in range(1, 13)],
        "amount": 0.0
    })

    # Use the pre-aggregated summary from the API
    for m_str, amt in summary_dict.items():
        if m_str in all_months['month_num'].values:
            all_months.loc[all_months['month_num'] == m_str, 'amount'] = float(
                amt)

    x = all_months["month_label"].tolist()
    y = all_months["amount"].tolist()

    # Calculate average only for months that have passed or have data
    non_zero_months = [val for val in y if val > 0]
    avg_monthly = float(
        sum(non_zero_months) / len(non_zero_months)) if non_zero_months else 0.0

    # Colors for the bars: Rich Teal
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
            line_color="#e53e3e",  # Red
            line_width=2,
            annotation_text=f"Avg: ₪{avg_monthly:,.0f}",
            annotation_position="top right",
        )

    fig.update_layout(
        title=f"Monthly Spending Trend ({year})",
        margin=dict(l=10, r=10, t=40, b=10),
        hovermode="x unified",
        yaxis=dict(tickprefix="₪", separatethousands=True),
        plot_bgcolor="rgba(0,0,0,0)"  # Transparent background for cleaner look
    )

    return fig
