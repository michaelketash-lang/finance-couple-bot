from __future__ import annotations

import pandas as pd


CATEGORIES = [
    "Rent",
    "Utilities",
    "Groceries",
    "Eating Out",
    "Transport",
    "Maintenance",
    "Shopping",
    "Health",
    "Leisure",
    "Other",
]


def get_mock_expenses_df() -> pd.DataFrame:
    """
    Dummy expense rows that mimic the future JSON API response.

    Columns (matches backend idea):
      - merchant: str
      - amount: float (ILS)
      - category: one of CATEGORIES
      - payer: str (e.g., Michael / Partner)
      - split: 'shared' | 'personal'
      - date: YYYY-MM-DD string
    """
    rows: list[dict] = []

    # Jan..Jun 2026 (deterministic mock)
    months = [1, 2, 3, 4, 5, 6]
    for m in months:
        # Shared expenses (backend stores shared as split='shared')
        rows.extend(
            [
                {
                    "merchant": "Rami Levy",
                    "amount": float(220 + 8 * m),
                    "category": "Groceries",
                    "payer": "Michael",
                    "split": "shared",
                    "date": f"2026-{m:02d}-03",
                },
                {
                    "merchant": "Wolt",
                    "amount": float(120 + 5 * m),
                    "category": "Eating Out",
                    "payer": "Michael",
                    "split": "shared",
                    "date": f"2026-{m:02d}-12",
                },
                {
                    "merchant": "Super-Pharm",
                    "amount": float(70 + 3 * m),
                    "category": "Health",
                    "payer": "Michael",
                    "split": "shared",
                    "date": f"2026-{m:02d}-20",
                },
            ]
        )

        # Personal expenses
        rows.extend(
            [
                {
                    "merchant": "Amazon",
                    "amount": float(95 + 7 * m),
                    "category": "Shopping",
                    "payer": "Partner",
                    "split": "personal",
                    "date": f"2026-{m:02d}-07",
                },
                {
                    "merchant": "Rav-Kav",
                    "amount": float(140 + 6 * m),
                    "category": "Transport",
                    "payer": "Partner",
                    "split": "personal",
                    "date": f"2026-{m:02d}-14",
                },
                {
                    "merchant": "Netflix",
                    "amount": 39.9,
                    "category": "Leisure",
                    "payer": "Partner",
                    "split": "personal",
                    "date": f"2026-{m:02d}-26",
                },
            ]
        )

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
    return df


def get_mock_budgets_df() -> pd.DataFrame:
    """
    Dummy monthly budget targets per category.

    Columns:
      - category
      - monthly_target
    """
    targets = {
        "Rent": 0.0,
        "Utilities": 550.0,
        "Groceries": 1200.0,
        "Eating Out": 400.0,
        "Transport": 600.0,
        "Maintenance": 250.0,
        "Shopping": 450.0,
        "Health": 300.0,
        "Leisure": 350.0,
        "Other": 200.0,
    }

    df = pd.DataFrame(
        [{"category": cat, "monthly_target": float(targets[cat])} for cat in CATEGORIES]
    )
    df["monthly_target"] = pd.to_numeric(df["monthly_target"], errors="coerce").fillna(0.0)
    return df

