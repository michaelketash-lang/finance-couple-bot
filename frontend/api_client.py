"""
api_client.py
=============

HTTP client for the finance bot's Flask REST API.

All functions use a shared ``requests.Session`` to reuse the TCP/SSL
connection across calls, reducing overhead on repeated dashboard loads.

The base URL points to the production Flask server on PythonAnywhere.
"""

import requests
import pandas as pd

BASE_URL = "https://michaelketash.pythonanywhere.com/api"
# Shared session reuses the TCP/SSL connection across all API calls
session = requests.Session()

# Categories must match the database constraints
CATEGORIES = [
    "Rent", "Utilities", "Groceries", "Eating Out", "Transport",
    "Maintenance", "Shopping", "Health", "Leisure", "Other"
]


def fetch_raw_expenses(year: int, month: int, split: str = "shared") -> pd.DataFrame:
    """Fetch raw expense rows for a given month and split type.

    :param year: The year to query.
    :param month: The month to query (1–12).
    :param split: ``'shared'`` or ``'personal'`` (defaults to ``'shared'``).
    :returns: DataFrame with columns ``id``, ``date``, ``merchant``, ``amount``,
              ``category``, ``payer``, ``split``. Returns an empty DataFrame on error.
    """
    url = f"{BASE_URL}/expenses/raw?year={year}&month={month}&split={split}"
    columns = ["id", "date", "merchant", "amount", "category", "payer", "split"]

    try:
        response = session.get(url)
        response.raise_for_status()
        data = response.json()

        if not data:
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
        return df

    except Exception as e:
        print(f"Error fetching raw expenses: {e}")
        return pd.DataFrame(columns=columns)


def fetch_all_budgets() -> pd.DataFrame:
    """Fetch all category budget targets.

    :returns: DataFrame with columns ``category`` and ``monthly_target``.
              Returns an empty DataFrame on error.
    """
    url = f"{BASE_URL}/budget/all"
    columns = ["category", "monthly_target"]

    try:
        response = session.get(url)
        response.raise_for_status()
        data = response.json()

        if not data:
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(data)
        df["monthly_target"] = pd.to_numeric(df["monthly_target"], errors="coerce").fillna(0.0)
        return df

    except Exception as e:
        print(f"Error fetching budgets: {e}")
        return pd.DataFrame(columns=columns)


def fetch_yearly_data(year: int, split: str = "shared") -> pd.DataFrame:
    """Fetch raw expense rows for all 12 months of a year in a single request.

    :param year: The year to query.
    :param split: ``'shared'`` or ``'personal'`` (defaults to ``'shared'``).
    :returns: DataFrame with columns ``date``, ``merchant``, ``amount``,
              ``category``, ``payer``, ``split``. Returns an empty DataFrame on error.
    """
    url = f"{BASE_URL}/expenses/yearly/raw?year={year}&split={split}"
    columns = ["date", "merchant", "amount", "category", "payer", "split"]

    try:
        response = session.get(url)
        response.raise_for_status()
        data = response.json()

        if not data:
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(data)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
        return df

    except Exception as e:
        print(f"Error fetching yearly raw expenses: {e}")
        return pd.DataFrame(columns=columns)


def fetch_yearly_summary(year: int, split: str = "shared") -> dict:
    """Fetch pre-aggregated yearly spending summaries.

    :param year: The year to query.
    :param split: ``'shared'`` or ``'personal'`` (defaults to ``'shared'``).
    :returns: Dict with ``monthly_trend`` and ``category_breakdown`` keys,
              or ``{}`` on error.
    """
    url = f"{BASE_URL}/expenses/yearly/summary?year={year}&split={split}"
    try:
        response = session.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching yearly summary: {e}")
        return {}


def save_category_budget(category: str, monthly_target: float) -> bool:
    """Upsert a monthly budget target for a single category.

    :param category: The expense category to set the budget for.
    :param monthly_target: The target spend amount in ILS.
    :returns: ``True`` on success, ``False`` on failure.
    """
    url = f"{BASE_URL}/budget"
    try:
        response = session.post(url, json={"category": category, "monthly_target": monthly_target})
        response.raise_for_status()
        return response.json().get("success", False)
    except Exception as e:
        print(f"Error saving budget for {category}: {e}")
        return False


def update_expense(expense_id: int, merchant: str, amount: float,
                   category: str, payer: str) -> bool:
    """Update all editable fields of a single expense record.

    :param expense_id: Primary key of the expense to update.
    :param merchant: Updated merchant name.
    :param amount: Updated amount in ILS.
    :param category: Updated expense category.
    :param payer: Updated payer name.
    :returns: ``True`` on success, ``False`` on failure.
    """
    url = f"{BASE_URL}/expenses/{expense_id}"
    try:
        response = session.put(url, json={
            "merchant": merchant,
            "amount": amount,
            "category": category,
            "payer": payer,
        })
        response.raise_for_status()
        return response.json().get("success", False)
    except Exception as e:
        print(f"Error updating expense {expense_id}: {e}")
        return False


def fetch_spending_per_person(year: int, month: int) -> dict:
    """Fetch the total financial burden per person for a given month.

    Each person's burden = their personal expenses + half of all shared expenses.

    :param year: The year to query.
    :param month: The month to query (1–12).
    :returns: ``{payer: total}`` dict (e.g. ``{'Michael': 620.0, 'Ori': 500.0}``),
              or ``{}`` on error.
    """
    url = f"{BASE_URL}/expenses/per-person?year={year}&month={month}"
    try:
        response = session.get(url)
        response.raise_for_status()
        data = response.json()
        return {k: float(v) for k, v in data.get("spending", {}).items()}
    except Exception as e:
        print(f"Error fetching spending per person: {e}")
        return {}


def fetch_settlement(year: int, month: int) -> dict:
    """Fetch the monthly settlement result.

    :param year: The year to query.
    :param month: The month to query (1–12).
    :returns: ``{"debtor": str, "creditor": str, "amount": float}`` or
              ``{"balanced": True, "amount": 0.0}`` on error.
    """
    url = f"{BASE_URL}/expenses/settlement?year={year}&month={month}"
    try:
        response = session.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching settlement: {e}")
        return {"balanced": True, "amount": 0.0}


def fetch_personal_totals(year: int, month: int) -> dict:
    """Fetch total personal spending per person for a given month.

    :param year: The year to query.
    :param month: The month to query (1–12).
    :returns: ``{payer: personal_amount}`` dict
              (e.g. ``{'Michael': 450.0, 'Ori': 300.0}``), or ``{}`` on error.
    """
    url = f"{BASE_URL}/expenses/personal?year={year}&month={month}"
    try:
        response = session.get(url)
        response.raise_for_status()
        data = response.json()
        return {k: float(v) for k, v in data.get("spending", {}).items()}
    except Exception as e:
        print(f"Error fetching personal totals: {e}")
        return {}


def fetch_budget_pacing(year: int, month: int) -> dict:
    """Fetch the budget pacing status for a given month.

    :param year: The year to query.
    :param month: The month to query (1–12).
    :returns: ``{"status": str, "amount": float}`` dict, or a default error dict.
    """
    url = f"{BASE_URL}/budget/pacing?year={year}&month={month}"
    try:
        response = session.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching budget pacing: {e}")
        return {"status": "Error", "amount": 0.0}


def fetch_dashboard_data(year: int, month: int) -> dict:
    """Fetch all Expenses tab data in a single BFF round-trip.

    :param year: The year to query.
    :param month: The month to query (1–12).
    :returns: Dict with ``expenses``, ``yearly_raw``, ``kpis``, and
              ``payer_summary`` keys, or ``{}`` on error.
    """
    url = f"{BASE_URL}/bff/dashboard-data?year={year}&month={month}"
    try:
        response = session.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching dashboard data: {e}")
        return {}


def fetch_budget_bff(year: int, month: int) -> dict:
    """Fetch all Budget tab data in a single BFF round-trip.

    :param year: The year to query.
    :param month: The month to query (1–12).
    :returns: Dict with ``budgets``, ``category_actuals``, and ``pacing`` keys,
              or ``{}`` on error.
    """
    url = f"{BASE_URL}/bff/budget-data?year={year}&month={month}"
    try:
        response = session.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching budget data: {e}")
        return {}


def export_to_sheets(year: int, month: int, split: str) -> dict:
    """Export a month's expenses to a new tab in the configured Google Sheet.

    :param year: The year to export.
    :param month: The month to export (1–12).
    :param split: The split filter to export (``'shared'``, ``'personal'``, or a payer name).
    :returns: Dict with ``success``, ``url``, ``tab``, and ``rows`` keys on success,
              or ``{"error": str}`` on failure.
    """
    url = f"{BASE_URL}/expenses/export-sheets"
    try:
        response = session.post(url, json={"year": year, "month": month, "split": split})
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error exporting to sheets: {e}")
        return {"error": str(e)}
