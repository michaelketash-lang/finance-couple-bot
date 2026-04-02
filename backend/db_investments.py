import sqlite3


def add_investment(category, amount, name, ticker, expense_ratio):
    """Adds a new investment record to the database."""
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            sql = '''INSERT INTO investments (category, amount, name, ticker, expense_ratio)
                     VALUES (?, ?, ?, ?, ?)'''
            cursor.execute(sql, (category, amount, name, ticker, expense_ratio))
            conn.commit()
            return True
    except sqlite3.IntegrityError as e:
        print(f"❌ Validation Error: Did you use a wrong category or split type? ({e})")
    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
    return False
