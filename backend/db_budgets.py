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


def set_budgets_batch(budgets: list[dict]) -> bool:
    """Insert or update budget targets for multiple categories in one transaction.

    :param budgets: List of ``{"category": str, "monthly_target": float, "payer": str}`` dicts.
                    ``payer`` defaults to ``'shared'`` if omitted.
    :returns: ``True`` on success, ``False`` on error.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.executemany(
                'INSERT OR REPLACE INTO budgets (category, monthly_target, payer) VALUES (?, ?, ?)',
                [(b['category'], float(b['monthly_target']), b.get('payer', 'shared')) for b in budgets]
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"❌ Database Error in set_budgets_batch: {e}")
        return False


def set_category_budget(category: str, monthly_target: float, payer: str = 'shared') -> bool:
    """Insert or update the monthly budget target for a category.

    :param category: The expense category name.
    :param monthly_target: The target spend amount in ILS.
    :param payer: Who this budget belongs to: ``'shared'``, or a payer name.
    :returns: ``True`` on success, ``False`` on validation or database error.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            sql = '''INSERT OR REPLACE INTO budgets (category, monthly_target, payer)
                     VALUES (?, ?, ?)'''
            cursor.execute(sql, (category, monthly_target, payer))
            return True
    except sqlite3.IntegrityError as e:
        print(f"❌ Validation Error: Invalid category name. ({e})")
        return False
    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
        return False


def get_total_budget(payer: str = 'shared') -> float:
    """Return the sum of all category monthly targets for a given payer.

    :param payer: Filter by payer (default ``'shared'``).
    :returns: Grand total budget in ILS, or ``0.0`` if no budgets are set.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(monthly_target) FROM budgets WHERE payer = ?", (payer,))
            result = cursor.fetchone()[0]
            return result if result is not None else 0.0
    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
        return 0.0


def get_all_budgets(payer: str = 'shared') -> list[dict]:
    """Return all category budget targets for a given payer.

    :param payer: Filter by payer — ``'shared'``, ``'Michael'``, ``'Ori'``, etc.
                  Defaults to ``'shared'``.
    :returns: List of ``{"category": str, "monthly_target": float}`` dicts,
              or an empty list on error.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT category, monthly_target FROM budgets WHERE payer = ?", (payer,)
            )
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"❌ Database Error in get_all_budgets: {e}")
        return []


def check_total_pacing(year: int, month: int) -> dict:
    """Calculate whether spending is on track against the shared monthly budget.

    For the current month, projects the final spend based on the daily average.
    For past months, compares the actual total directly against the budget.

    :param year: The year to evaluate.
    :param month: The month to evaluate (1–12).
    :returns: A dict with ``status`` (``'Over Budget'``, ``'On Track'``, or
              ``'No Budget Set'``) and ``amount`` (the surplus or deficit in ILS).
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()

            cursor.execute(
                "SELECT COALESCE(SUM(monthly_target), 0) FROM budgets WHERE payer = 'shared'"
            )
            total_budget = float(cursor.fetchone()[0])

            if total_budget == 0.0:
                return {"status": "No Budget Set", "amount": 0.0}

            month_filter = f"{year:04d}-{month:02d}%"
            cursor.execute('''
                SELECT SUM(
                    CASE
                        WHEN split = 'personal' THEN amount
                        WHEN split = 'shared' THEN amount / 2.0
                        ELSE 0
                    END
                )
                FROM expenses WHERE created_at LIKE ?
            ''', (month_filter,))
            result = cursor.fetchone()[0]
            total_spent = round(result, 2) if result is not None else 0.0

    except sqlite3.Error as e:
        print(f"❌ Database Error in check_total_pacing: {e}")
        return {"status": "No Budget Set", "amount": 0.0}

    today = datetime.date.today()
    if today.year == year and today.month == month:
        current_day = today.day
        days_in_month = calendar.monthrange(year, month)[1]
        projected_total = (total_spent / current_day) * days_in_month
        difference = projected_total - total_budget
    else:
        difference = total_spent - total_budget

    if difference > 0:
        return {"status": "Over Budget", "amount": round(difference, 2)}
    return {"status": "On Track", "amount": round(abs(difference), 2)}