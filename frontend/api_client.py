import requests
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

# Standard base URL for local Flask development
BASE_URL = "https://michaelketash.pythonanywhere.com/api"
# Categories must match the database constraints
CATEGORIES = [
    "Rent", "Utilities", "Groceries", "Eating Out", "Transport",
    "Maintenance", "Shopping", "Health", "Leisure", "Other"
]


def fetch_raw_expenses(year: int, month: int,
                       split: str = "shared") -> pd.DataFrame:
    """
    Fetches raw expense rows from the API to populate the DataTable and Charts.
    """
    url = f"{BASE_URL}/expenses/raw?year={year}&month={month}&split={split}"
    columns = ["date", "merchant", "amount", "category", "payer", "split"]

    try:
        response = requests.get(url)
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
    """
    Fetches all category budgets from the API.
    """
    url = f"{BASE_URL}/budget/all"
    columns = ["category", "monthly_target"]

    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        if not data:
            return pd.DataFrame(columns=columns)

        df = pd.DataFrame(data)
        df["monthly_target"] = pd.to_numeric(df["monthly_target"],
                                             errors="coerce").fillna(0.0)
        return df

    except Exception as e:
        print(f"Error fetching budgets: {e}")
        return pd.DataFrame(columns=columns)


def fetch_recent_months_data(months_back: int, split: str) -> pd.DataFrame:
    """
    Fetches raw data for the last X months to populate the trends chart.
    """
    today = datetime.today()
    all_dfs = []

    for i in range(months_back):
        target_date = today - relativedelta(months=i)
        df_month = fetch_raw_expenses(target_date.year, target_date.month,
                                      split)
        all_dfs.append(df_month)

    if all_dfs:
        combined_df = pd.concat(all_dfs, ignore_index=True)
        return combined_df

    return pd.DataFrame(
        columns=["date", "merchant", "amount", "category", "payer", "split"])


def fetch_yearly_data(year: int, split: str = "shared") -> pd.DataFrame:
    """
    Fetches raw data for all 12 months of a specific year in ONE single HTTP request.
    This eliminates the N+1 query delay and drastically speeds up the dashboard.
    """
    url = f"{BASE_URL}/expenses/yearly/raw?year={year}&split={split}"
    columns = ["date", "merchant", "amount", "category", "payer", "split"]

    try:
        response = requests.get(url)
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
    """
    Fetches pre-calculated yearly aggregates for speed.
    """
    url = f"{BASE_URL}/expenses/yearly/summary?year={year}&split={split}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching yearly summary: {e}")
        return {}


def fetch_budget_pacing(year: int, month: int) -> dict:
    """
    Fetches the pacing data (status, amount over/under budget).
    Uses existing GET /budget/pacing route.
    """
    url = f"{BASE_URL}/budget/pacing?year={year}&month={month}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json() # {"status": "On Track", "amount": 150.0}
    except Exception as e:
        print(f"Error fetching budget pacing: {e}")
        return {"status": "Error", "amount": 0.0}