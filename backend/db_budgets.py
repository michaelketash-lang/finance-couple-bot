import sqlite3
import datetime
import calendar

from db_expenses import get_total_monthly_expenses


def set_category_budget(category, monthly_target):
    """Inserts a new budget or updates an existing one for a category."""
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


def get_total_budget():
    """Calculates the grand total of all category budgets combined."""
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(monthly_target) FROM budgets")
            result = cursor.fetchone()[0]
            return result if result is not None else 0.0
    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
        return 0.0


def get_all_budgets():
    """Fetches all category budget targets from the budgets table."""
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


def check_total_pacing(year, month):
    """Checks if spending is on track for the month."""
    total_budget = get_total_budget()
    total_spent = get_total_monthly_expenses(year, month)

    if total_budget == 0.0:
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
    else:
        return {"status": "On Track", "amount": round(abs(difference), 2)}
