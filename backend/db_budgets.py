"""
db_budgets.py
=============

Data-access functions for the ``budgets`` table.

Manages monthly budget targets per expense category and provides
a pacing calculation to compare current spending against the budget.
"""

import sqlite3
import datetime
import calendar

from db_expenses import get_total_monthly_expenses


def set_category_budget(category: str, monthly_target: float) -> bool:
    """Insert or update the monthly budget target for a category.

    :param category: The expense category name (must match the ``budgets`` table constraint).
    :param monthly_target: The target spend amount in ILS.
    :returns: ``True`` on success, ``False`` on validation or database error.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            sql = '''INSERT OR REPLACE INTO budgets (category, monthly_target)
                     VALUES (?, ?)'''
            cursor.execute(sql, (category, monthly_target))
            return True
    except sqlite3.IntegrityError as e:
        print(f"❌ Validation Error: Invalid category name. ({e})")
        return False
    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
        return False


def get_total_budget() -> float:
    """Return the sum of all category monthly targets.

    :returns: Grand total budget in ILS, or ``0.0`` if no budgets are set.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(monthly_target) FROM budgets")
            result = cursor.fetchone()[0]
            return result if result is not None else 0.0
    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
        return 0.0


def get_all_budgets() -> list[dict]:
    """Return all category budget targets as a list of dicts.

    :returns: List of ``{"category": str, "monthly_target": float}`` dicts,
              or an empty list on error.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT category, monthly_target FROM budgets")
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"❌ Database Error in get_all_budgets: {e}")
        return []


def check_total_pacing(year: int, month: int) -> dict:
    """Calculate whether spending is on track against the total monthly budget.

    For the current month, projects the final spend based on the daily average.
    For past months, compares the actual total directly against the budget.

    :param year: The year to evaluate.
    :param month: The month to evaluate (1–12).
    :returns: A dict with ``status`` (``'Over Budget'``, ``'On Track'``, or
              ``'No Budget Set'``) and ``amount`` (the surplus or deficit in ILS).
    """
    total_budget = get_total_budget()
    total_spent = get_total_monthly_expenses(year, month)

    if total_budget == 0.0:
        return {"status": "No Budget Set", "amount": 0.0}

    today = datetime.date.today()

    if today.year == year and today.month == month:
        # Project end-of-month spend from the daily average so far
        current_day = today.day
        days_in_month = calendar.monthrange(year, month)[1]
        projected_total = (total_spent / current_day) * days_in_month
        difference = projected_total - total_budget
    else:
        difference = total_spent - total_budget

    if difference > 0:
        return {"status": "Over Budget", "amount": round(difference, 2)}
    else:
        return {"status": "On Track", "amount": round(abs(difference), 2)}