"""
components/tables.py
====================

Reusable Dash DataTable components for the finance bot frontend.

Provides an editable expenses table and an editable budget targets table,
both with consistent premium styling and conditional row coloring.
"""

from __future__ import annotations
from dash import dash_table


def expenses_datatable(
        data: list[dict],
        categories: list[str],
        table_id: str,
        **kwargs
):
    """Build an editable DataTable for displaying and correcting monthly expenses.

    Columns: Date (read-only) | Merchant | Amount | Category (dropdown) | Payer.
    Supports zebra striping, hover highlight, and category dropdown editing.

    :param data: List of expense row dicts to populate the table.
    :param categories: List of valid category strings for the dropdown column.
    :param table_id: The Dash component ``id`` to assign to this table.
    :param kwargs: Additional keyword arguments forwarded to ``dash_table.DataTable``.
                   ``style_header`` and ``style_data_conditional`` can be overridden here.
    :returns: A configured ``dash_table.DataTable`` component.
    """
    amount_format = {"specifier": ",.2f"}

    base_style_header = {
        "backgroundColor": "#2c3e50",
        "color": "white",
        "fontWeight": "bold",
        "textAlign": "left",
        "padding": "12px",
        "border": "none"
    }

    base_style_data_conditional = [
        {"if": {"row_index": "odd"}, "backgroundColor": "#f8fafc"},
        {"if": {"row_index": "even"}, "backgroundColor": "white"},
        {"if": {"state": "active"}, "backgroundColor": "#e2e8f0",
         "border": "1px solid #cbd5e1"}
    ]

    # Allow callers to override header and row styles without replacing everything
    style_header = kwargs.pop("style_header", base_style_header)
    style_data_conditional = kwargs.pop("style_data_conditional", base_style_data_conditional)

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
        **kwargs
    )


def budgets_datatable(
        data: list[dict],
        table_id: str,
        **kwargs
):
    """Build an editable DataTable for managing monthly budget targets per category.

    Columns: Category (read-only) | Target ₪ (editable) | Actual ₪ | Remaining ₪.
    Rows turn red when actual spend exceeds target and green when under budget.

    :param data: List of budget row dicts with ``category``, ``monthly_target``,
                 ``actual``, and ``remaining`` keys.
    :param table_id: The Dash component ``id`` to assign to this table.
    :param kwargs: Additional keyword arguments forwarded to ``dash_table.DataTable``.
    :returns: A configured ``dash_table.DataTable`` component.
    """
    amount_format = {"specifier": ",.0f"}

    style_data_conditional = [
        {"if": {"row_index": "odd"}, "backgroundColor": "#f8fafc"},
        {"if": {"row_index": "even"}, "backgroundColor": "white"},
        # Over budget → red tint
        {
            "if": {"filter_query": "{remaining} < 0"},
            "backgroundColor": "#fff5f5",
            "color": "#c53030",
        },
        # Under budget (target set and spend > 0) → green tint
        {
            "if": {"filter_query": "{remaining} > 0 && {actual} > 0"},
            "backgroundColor": "#f0fff4",
            "color": "#276749",
        },
        {"if": {"state": "active"}, "backgroundColor": "#e2e8f0",
         "border": "1px solid #cbd5e1"},
    ]

    return dash_table.DataTable(
        id=table_id,
        data=data,
        columns=[
            {"name": "Category", "id": "category", "editable": False},
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
