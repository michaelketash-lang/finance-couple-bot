from __future__ import annotations
from dash import dash_table


def expenses_datatable(
        data: list[dict],
        categories: list[str],
        table_id: str,
        **kwargs  # This magic keyword allows passing extra styling arguments!
):
    """
    Editable DataTable for manual corrections (expenses) with premium styling.
    """
    amount_format = {"specifier": ",.2f"}

    # --- Premium Base Styling ---
    base_style_header = {
        "backgroundColor": "#2c3e50",  # Dark elegant blue
        "color": "white",
        "fontWeight": "bold",
        "textAlign": "left",
        "padding": "12px",
        "border": "none"
    }

    base_style_data_conditional = [
        # Alternating row colors (Zebra stripes)
        {"if": {"row_index": "odd"}, "backgroundColor": "#f8fafc"},
        {"if": {"row_index": "even"}, "backgroundColor": "white"},
        # Highlight row on hover or select
        {"if": {"state": "active"}, "backgroundColor": "#e2e8f0",
         "border": "1px solid #cbd5e1"}
    ]

    # Extract dynamic styles if passed from layout, otherwise use base styles
    style_header = kwargs.pop("style_header", base_style_header)
    style_data_conditional = kwargs.pop("style_data_conditional",
                                        base_style_data_conditional)

    return dash_table.DataTable(
        id=table_id,
        data=data,
        columns=[
            {"name": "Date", "id": "date"},
            {"name": "Merchant", "id": "merchant", "editable": True},
            {
                "name": "Amount (ILS)",
                "id": "amount",
                "type": "numeric",
                "editable": True,
                "format": amount_format,
            },
            {
                "name": "Category",
                "id": "category",
                "editable": True,
                "presentation": "dropdown",
            },
            {"name": "Payer", "id": "payer", "editable": True},
        ],
        editable=True,
        row_deletable=False,
        sort_action="native",
        page_size=10,

        # --- Clean LTR Layout Styling ---
        style_table={"overflowX": "auto", "borderRadius": "8px",
                     "border": "1px solid #e2e8f0"},
        style_cell={
            "textAlign": "left",
            "padding": "12px",
            "whiteSpace": "normal",
            "fontFamily": "'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
            "color": "#2d3748",
            "border": "none",
            "borderBottom": "1px solid #e2e8f0"
        },
        style_header=style_header,
        style_data_conditional=style_data_conditional,
        dropdown={"category": {
            "options": [{"label": c, "value": c} for c in categories]}},
        **kwargs  # Pass any remaining arguments safely
    )


def budgets_datatable(
        data: list[dict],
        table_id: str,
        **kwargs
):
    """
    Editable DataTable for budget targets per category.
    Columns: Category | Target (editable) | Actual (read-only) | Remaining (read-only).
    Rows turn red when actual spend exceeds target, green when under budget.
    """
    amount_format = {"specifier": ",.0f"}

    style_data_conditional = [
        # Zebra stripes baseline
        {"if": {"row_index": "odd"}, "backgroundColor": "#f8fafc"},
        {"if": {"row_index": "even"}, "backgroundColor": "white"},
        # Over budget → red tint
        {
            "if": {
                "filter_query": "{remaining} < 0",
            },
            "backgroundColor": "#fff5f5",
            "color": "#c53030",
        },
        # Under budget (target set and spend > 0) → green tint
        {
            "if": {
                "filter_query": "{remaining} > 0 && {actual} > 0",
            },
            "backgroundColor": "#f0fff4",
            "color": "#276749",
        },
        # Highlight active cell
        {"if": {"state": "active"}, "backgroundColor": "#e2e8f0",
         "border": "1px solid #cbd5e1"},
    ]

    return dash_table.DataTable(
        id=table_id,
        data=data,
        columns=[
            {
                "name": "Category",
                "id": "category",
                "editable": False,
            },
            {
                "name": "Target ₪",
                "id": "monthly_target",
                "type": "numeric",
                "editable": True,
                "format": amount_format,
            },
            {
                "name": "Actual ₪",
                "id": "actual",
                "type": "numeric",
                "editable": False,
                "format": amount_format,
            },
            {
                "name": "Remaining ₪",
                "id": "remaining",
                "type": "numeric",
                "editable": False,
                "format": amount_format,
            },
        ],
        editable=True,
        row_deletable=False,
        sort_action="native",
        page_size=10,
        style_table={"overflowX": "auto", "borderRadius": "8px",
                     "border": "1px solid #e2e8f0"},
        style_cell={
            "textAlign": "left",
            "padding": "12px",
            "fontFamily": "'Segoe UI', Roboto, Helvetica, Arial, sans-serif",
            "color": "#2d3748",
            "border": "none",
            "borderBottom": "1px solid #e2e8f0",
        },
        style_header={
            "backgroundColor": "#2c3e50",
            "color": "white",
            "fontWeight": "bold",
            "textAlign": "left",
            "padding": "12px",
            "border": "none",
        },
        style_data_conditional=style_data_conditional,
        **kwargs
    )