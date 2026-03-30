import requests
import pandas as pd

# Standard base URL for production Flask development
BASE_URL = "https://michaelketash.pythonanywhere.com/api"

# --- PRO SPEED TIP: Use a Session to reuse the TCP/SSL connection ---
# This eliminates the SSL handshake overhead for every single request,
# making the dashboard feel incredibly fast and responsive.
session = requests.Session()

# Categories must match the database constraints
CATEGORIES = [
    "Rent", "Utilities", "Groceries", "Eating Out", "Transport",
    "Maintenance", "Shopping", "Health", "Leisure", "Other"
]


def fetch_raw_expenses(year: int, month: int, split: str = "shared") -> pd.DataFrame:
    """
    Fetches raw expense rows from the API to populate the DataTable and Charts.
    """
    url = f"{BASE_URL}/expenses/raw?year={year}&month={month}&split={split}"
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
        print(f"Error fetching raw expenses: {e}")
        return pd.DataFrame(columns=columns)


def fetch_all_budgets() -> pd.DataFrame:
    """
    Fetches all category budgets from the API.
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
    """
    Fetches raw data for all 12 months of a specific year in ONE single HTTP request.
    This eliminates the N+1 query delay and drastically speeds up the dashboard.
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
    """
    Fetches pre-calculated yearly aggregates for speed.
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
    """
    Saves (upserts) a monthly budget target for a single category.
    Returns True on success, False on failure.
    """
    url = f"{BASE_URL}/budget"
    try:
        response = session.post(url, json={"category": category, "monthly_target": monthly_target})
        response.raise_for_status()
        return response.json().get("success", False)
    except Exception as e:
        print(f"Error saving budget for {category}: {e}")
        return False


def fetch_budget_pacing(year: int, month: int) -> dict:
    """
    Fetches the pacing data (status, amount over/under budget).
    Uses existing GET /budget/pacing route.
    """
    url = f"{BASE_URL}/budget/pacing?year={year}&month={month}"
    try:
        response = session.get(url)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Error fetching budget pacing: {e}")
        return {"status": "Error", "amount": 0.0}