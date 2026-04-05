"""
db_expenses.py
==============

Data-access functions for the ``expenses`` table.

Handles all expense reads and writes, including personal/shared split logic,
per-person breakdowns, monthly settlement calculations, and yearly summaries.
"""

import sqlite3


def add_expense(merchant: str, amount: float, payer: str, split: str, category: str) -> bool:
    """Insert a new expense record into the database.

    :param merchant: Name of the merchant or payee.
    :param amount: Transaction amount in ILS.
    :param payer: Name of the person who paid.
    :param split: ``'shared'`` or ``'personal'``.
    :param category: Expense category (must match the table constraint).
    :returns: ``True`` on success, ``False`` on validation or database error.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            sql = '''INSERT INTO expenses (merchant, amount, payer, split, category)
                     VALUES (?, ?, ?, ?, ?)'''
            cursor.execute(sql, (merchant, amount, payer, split, category))
            conn.commit()
            return True
    except sqlite3.IntegrityError as e:
        print(f"❌ Validation Error: Did you use the wrong category?({e})")
    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
    return False


def get_total_monthly_expenses(year: int, month: int) -> float:
    """Return the total financial burden for a given month.

    Shared expenses are halved per person; personal expenses are counted in full.

    :param year: The year to query.
    :param month: The month to query (1–12).
    :returns: Rounded total in ILS, or ``0.0`` on error.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            month_filter = f"{year:04d}-{month:02d}%"
            sql = '''
                SELECT SUM(
                    CASE
                        WHEN split = 'personal' THEN amount
                        WHEN split = 'shared' THEN amount / 2.0
                        ELSE 0
                    END
                )
                FROM expenses
                WHERE created_at LIKE ?
            '''
            cursor.execute(sql, (month_filter,))
            result = cursor.fetchone()[0]
            return round(result, 2) if result is not None else 0.0
    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
        return 0.0


def get_average_total_monthly_expenses() -> float:
    """Return the average monthly financial burden across all recorded months.

    :returns: Rounded average in ILS, or ``0.0`` on error.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            sql = '''
                SELECT AVG(monthly_total)
                FROM (
                    SELECT SUM(
                        CASE
                            WHEN split = 'personal' THEN amount
                            WHEN split = 'shared' THEN amount / 2.0
                            ELSE 0
                        END
                    ) as monthly_total
                    FROM expenses
                    GROUP BY strftime('%Y-%m', created_at)
                )
            '''
            cursor.execute(sql)
            result = cursor.fetchone()[0]
            return round(result, 2) if result is not None else 0.0
    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
        return 0.0


def get_monthly_expenses_by_category(year: int, month: int, category: str) -> float:
    """Return the total spent in a specific category for a given month.

    :param year: The year to query.
    :param month: The month to query (1–12).
    :param category: The expense category to filter by.
    :returns: Total in ILS, or ``0.0`` on error.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            month_filter = f"{year:04d}-{month:02d}%"
            sql = '''
                SELECT SUM(
                    CASE
                        WHEN split = 'personal' THEN amount
                        WHEN split = 'shared' THEN amount / 2.0
                        ELSE 0
                    END
                )
                FROM expenses
                WHERE category = ? AND created_at LIKE ?
            '''
            cursor.execute(sql, (category, month_filter))
            result = cursor.fetchone()[0]
            return result if result is not None else 0.0
    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
        return 0.0


def get_spending_per_person_per_month(year: int, month: int) -> dict:
    """Return the total financial burden per person for a given month.

    Each person's burden = their personal spend + half of all shared spend.

    :param year: The year to query.
    :param month: The month to query (1–12).
    :returns: ``{payer: total_spent}`` dict, or ``{}`` on error.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            month_filter = f"{year:04d}-{month:02d}%"
            sql = '''
                WITH all_people AS (
                    SELECT DISTINCT payer FROM expenses WHERE created_at LIKE ?
                ),
                personal_totals AS (
                    SELECT payer, SUM(amount) as personal_spent
                    FROM expenses
                    WHERE split = 'personal' AND created_at LIKE ?
                    GROUP BY payer
                ),
                shared_total AS (
                    SELECT SUM(amount) / 2.0 as shared_burden
                    FROM expenses
                    WHERE split = 'shared' AND created_at LIKE ?
                )
                SELECT
                    p.payer,
                    ROUND(COALESCE(pt.personal_spent, 0) + COALESCE(st.shared_burden, 0), 2) as total_spent
                FROM all_people p
                LEFT JOIN personal_totals pt ON p.payer = pt.payer
                CROSS JOIN shared_total st
                ORDER BY total_spent DESC
            '''
            cursor.execute(sql, (month_filter, month_filter, month_filter))
            rows = cursor.fetchall()
            return {payer: total for payer, total in rows}
    except sqlite3.Error as e:
        print(f"❌ Database Error in get_spending_per_person_per_month: {e}")
        return {}


def get_shared_monthly_totals(year: int, month: int) -> float:
    """Return the shared expense burden per person for a given month (total shared / 2).

    :param year: The year to query.
    :param month: The month to query (1–12).
    :returns: Each person's share in ILS, or ``0.0`` on error.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            month_filter = f"{year:04d}-{month:02d}%"
            sql = '''
                SELECT SUM(amount) / 2.0
                FROM expenses
                WHERE split = 'shared' AND created_at LIKE ?
            '''
            cursor.execute(sql, (month_filter,))
            result = cursor.fetchone()[0]
            return round(result, 2) if result is not None else 0.0
    except sqlite3.Error as e:
        print(f"❌ Database Error in get_shared_monthly_totals: {e}")
        return 0.0


def get_personal_monthly_totals(year: int, month: int) -> dict:
    """Return the total personal spending per person for a given month.

    :param year: The year to query.
    :param month: The month to query (1–12).
    :returns: ``{payer: total_personal_spent}`` dict, or ``{}`` on error.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            month_filter = f"{year:04d}-{month:02d}%"
            sql = '''
                SELECT payer, ROUND(SUM(amount), 2)
                FROM expenses
                WHERE split = 'personal' AND created_at LIKE ?
                GROUP BY payer
            '''
            cursor.execute(sql, (month_filter,))
            rows = cursor.fetchall()
            return {payer: total for payer, total in rows}
    except sqlite3.Error as e:
        print(f"❌ Database Error in get_personal_monthly_totals: {e}")
        return {}


def get_monthly_settlement(year: int, month: int) -> dict:
    """Calculate who owes whom based on shared expense payments for a given month.

    Compares each person's actual payments against the fair share (total / 2)
    to determine the debtor and creditor.

    :param year: The year to query.
    :param month: The month to query (1–12).
    :returns: ``{"debtor": str, "creditor": str, "amount": float}`` or
              ``{"balanced": True, "amount": 0.0}`` if no settlement is needed.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            month_filter = f"{year:04d}-{month:02d}%"
            cursor.execute('''
                SELECT payer, SUM(amount)
                FROM expenses
                WHERE split = 'shared' AND created_at LIKE ?
                GROUP BY payer
            ''', (month_filter,))
            payments = dict(cursor.fetchall())

        if not payments:
            return {"balanced": True, "amount": 0.0}

        total_shared = sum(payments.values())
        fair_share = total_shared / 2.0
        # Positive balance = overpaid (creditor), negative = underpaid (debtor)
        balances = {person: round(paid - fair_share, 2) for person, paid in payments.items()}
        debtor = min(balances, key=balances.get)
        creditor = max(balances, key=balances.get)
        amount = round(abs(balances[debtor]), 2)

        if amount == 0.0:
            return {"balanced": True, "amount": 0.0}

        return {"debtor": debtor, "creditor": creditor, "amount": amount}
    except sqlite3.Error as e:
        print(f"❌ Database Error in get_monthly_settlement: {e}")
        return {}


def get_raw_monthly_expenses(year: int, month: int, split: str | None = None) -> list[dict]:
    """Return all individual expense records for a given month.

    :param year: The year to query.
    :param month: The month to query (1–12).
    :param split: Optional filter — ``'shared'``, ``'personal'``, or ``None`` for all.
    :returns: List of expense dicts with ``id``, ``merchant``, ``amount``,
              ``category``, ``payer``, ``split``, and ``date`` keys.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            month_filter = f"{year:04d}-{month:02d}%"
            if split:
                sql = "SELECT id, merchant, amount, category, payer, split, strftime('%Y-%m-%d', created_at) as date FROM expenses WHERE created_at LIKE ? AND split = ?"
                cursor.execute(sql, (month_filter, split))
            else:
                sql = "SELECT id, merchant, amount, category, payer, split, strftime('%Y-%m-%d', created_at) as date FROM expenses WHERE created_at LIKE ?"
                cursor.execute(sql, (month_filter,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"❌ Database Error in get_raw_monthly_expenses: {e}")
        return []


def update_expense_category(expense_id: int, new_category: str) -> bool:
    """Update the category of a specific expense.

    :param expense_id: Primary key of the expense to update.
    :param new_category: The new category value.
    :returns: ``True`` if a row was updated, ``False`` otherwise.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE expenses SET category = ? WHERE id = ?",
                (new_category, expense_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"❌ Database Error in update_expense_category: {e}")
        return False


def update_expense(expense_id: int, merchant: str, amount: float, category: str, payer: str) -> bool:
    """Update all editable fields of a specific expense record.

    :param expense_id: Primary key of the expense to update.
    :param merchant: Updated merchant name.
    :param amount: Updated amount in ILS.
    :param category: Updated expense category.
    :param payer: Updated payer name.
    :returns: ``True`` if a row was updated, ``False`` otherwise.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                """UPDATE expenses
                   SET merchant = ?, amount = ?, category = ?, payer = ?
                   WHERE id = ?""",
                (merchant, float(amount), category, payer, expense_id)
            )
            conn.commit()
            return cursor.rowcount > 0
    except sqlite3.Error as e:
        print(f"❌ Database Error in update_expense: {e}")
        return False


def get_raw_yearly_expenses(year: int, split: str | None = None) -> list[dict]:
    """Return all individual expense records for an entire year.

    :param year: The year to query.
    :param split: Optional filter — ``'shared'``, ``'personal'``, or ``None`` for all.
    :returns: List of expense dicts with ``merchant``, ``amount``, ``category``,
              ``payer``, ``split``, and ``date`` keys.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            year_filter = f"{year:04d}-%"
            if split:
                sql = "SELECT merchant, amount, category, payer, split, strftime('%Y-%m-%d', created_at) as date FROM expenses WHERE created_at LIKE ? AND split = ?"
                cursor.execute(sql, (year_filter, split))
            else:
                sql = "SELECT merchant, amount, category, payer, split, strftime('%Y-%m-%d', created_at) as date FROM expenses WHERE created_at LIKE ?"
                cursor.execute(sql, (year_filter,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        print(f"❌ Database Error in get_raw_yearly_expenses: {e}")
        return []


def get_yearly_summary(year: int, split: str | None = None) -> dict:
    """Return pre-aggregated monthly trend and category breakdown for a full year.

    :param year: The year to summarize.
    :param split: Optional filter — ``'shared'``, ``'personal'``, or ``None`` for all.
    :returns: Dict with ``year``, ``split``, ``monthly_trend`` (``{month: total}``),
              and ``category_breakdown`` (``{category: total}``).
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            year_filter = f"{year:04d}-%"
            split_sql = "AND split = ?" if split else ""
            params = (year_filter, split) if split else (year_filter,)

            sql_trend = f'''
                SELECT strftime('%m', created_at) as month, SUM(amount) as total
                FROM expenses
                WHERE created_at LIKE ?
                {split_sql}
                GROUP BY month
            '''
            cursor.execute(sql_trend, params)
            trend_data = {row['month']: row['total'] for row in cursor.fetchall()}

            sql_categories = f'''
                SELECT category, SUM(amount) as total
                FROM expenses
                WHERE created_at LIKE ?
                {split_sql}
                GROUP BY category
            '''
            cursor.execute(sql_categories, params)
            category_data = {row['category']: row['total'] for row in cursor.fetchall()}

            return {
                "year": year,
                "split": split,
                "monthly_trend": trend_data,
                "category_breakdown": category_data
            }
    except sqlite3.Error as e:
        print(f"❌ Database Error in get_yearly_summary: {e}")
        return {}
