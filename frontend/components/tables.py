from __future__ import annotations

from dash import dash_table


def expenses_datatable(
    data: list[dict],
    categories: list[str],
    table_id: str,
):
    """
    Editable DataTable for manual corrections (expenses).

    Expected columns in `data`:
      - date, merchant, amount, category, payer, split
    """
    # Format numeric amounts as "1,234.56"-style floats.
    amount_format = {"specifier": ",.2f"}

    return dash_table.DataTable(
        id=table_id,
        data=data,
        # Per-column editability + validation (numeric typing, dropdown for category).
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
            # Note: Removed the "split" column from here so it remains hidden without causing errors, 
            # but it is still accessible in the underlying `data` payload.
        ],
        editable=True,
        row_deletable=False,
        sort_action="native",
        page_size=10,
        # LTR layout + improved styling
        style_table={"overflowX": "auto"},
        style_cell={
            "textAlign": "left",
            "padding": "10px",
            "whiteSpace": "normal",
            "fontFamily": "sans-serif",
        },
        style_header={
            "textAlign": "left",
            "fontWeight": "bold",
            "backgroundColor": "#f8f9fa",
        },
        # Constrain category values to the allowed set.
        dropdown={"category": {"options": [{"label": c, "value": c} for c in categories]}},
    )


def budgets_datatable(
    data: list[dict],
    table_id: str,
):
    """
    Editable DataTable for budget targets per category.
    """
    # Format numeric budgets to keep currency display consistent.
    amount_format = {"specifier": ",.2f"}

    return dash_table.DataTable(
        id=table_id,
        data=data,
        columns=[
            # Category is fixed; user edits only the numeric target.
            {"name": "Category", "id": "category", "editable": False},
            {
                "name": "Target Budget (Monthly, ILS)",
                "id": "monthly_target",
                "type": "numeric",
                "editable": True,
                "format": amount_format,
            },
        ],
        editable=True,
        row_deletable=False,
        sort_action="native",
        page_size=10,
        # LTR layout + improved styling
        style_table={"overflowX": "auto"},
        style_cell={
            "textAlign": "left",
            "padding": "10px",
            "whiteSpace": "normal",
            "fontFamily": "sans-serif",
        },
        style_header={
            "textAlign": "left",
            "fontWeight": "bold",
            "backgroundColor": "#f8f9fa",
        },
    )