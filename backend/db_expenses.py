import sqlite3


def add_expense(merchant, amount, payer, split, category):
    """Adds a new expense to the database."""
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


def get_total_monthly_expenses(year, month):
    """Calculates the grand total of all expenses for a specific month and year."""
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


def get_average_total_monthly_expenses():
    """Calculates the average total amount spent per month across all categories."""
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


def get_monthly_expenses_by_category(year, month, category):
    """Calculates the amount spent in a specific month for a specific category."""
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


def get_spending_per_person_per_month(year, month):
    """Calculates the total financial burden per person for a specific month."""
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


def get_shared_monthly_totals(year, month):
    """Returns the actual shared expense burden per person for a given month."""
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


def get_personal_monthly_totals(year, month):
    """Returns the total personal spending per person for a given month."""
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


def get_monthly_settlement(year, month):
    """Calculates who owes whom for a specific month based on shared expenses."""
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


def get_raw_monthly_expenses(year, month, split=None):
    """Fetches all individual expense records for a specific month and year."""
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


def update_expense_category(expense_id, new_category):
    """Updates the category of a specific expense by id."""
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


def update_expense(expense_id, merchant, amount, category, payer):
    """Updates all editable fields of a specific expense record."""
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


def get_raw_yearly_expenses(year, split=None):
    """Fetches all expense records for an entire year in a single query."""
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


def get_yearly_summary(year, split=None):
    """Returns pre-calculated spending summaries for charts."""
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
