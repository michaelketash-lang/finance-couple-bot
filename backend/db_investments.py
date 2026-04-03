import sqlite3

INVESTMENT_CATEGORIES = ['stocks', 'bonds', 'cash', 'pension', 'gemel', 'hishtalmut']


def add_investment(category, amount, name, ticker, expense_ratio):
    """Adds a new investment record to the database (legacy, no pot deduction)."""
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


def add_to_pot(amount: float, note: str = None) -> bool:
    """Adds funds to The Pot (available cash waiting to be invested)."""
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO pot_transactions (amount, note) VALUES (?, ?)',
                (float(amount), note)
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"❌ Database Error adding to pot: {e}")
        return False


def log_new_investment(category: str, amount: float, name: str,
                       ticker: str = None, expense_ratio: float = None) -> bool:
    """
    Logs a new investment AND atomically deducts the amount from The Pot.
    Returns False if pot balance is insufficient or category is invalid.
    """
    if category not in INVESTMENT_CATEGORIES:
        print(f"❌ Invalid category: {category}")
        return False
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM pot_transactions')
            pot_balance = float(cursor.fetchone()[0])

            if pot_balance < float(amount):
                print(f"❌ Insufficient pot balance: ₪{pot_balance:.2f} < ₪{float(amount):.2f}")
                return False

            cursor.execute(
                '''INSERT INTO investments (category, amount, name, ticker, expense_ratio)
                   VALUES (?, ?, ?, ?, ?)''',
                (category, float(amount), name, ticker, expense_ratio)
            )
            cursor.execute(
                'INSERT INTO pot_transactions (amount, note) VALUES (?, ?)',
                (-float(amount), f"Investment: {name} ({category})")
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError as e:
        print(f"❌ Validation Error: ({e})")
    except sqlite3.Error as e:
        print(f"❌ Database Error logging investment: {e}")
    return False


def get_pot_balance() -> float:
    """Returns the current Pot balance (sum of all pot transactions)."""
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM pot_transactions')
            return float(cursor.fetchone()[0])
    except sqlite3.Error as e:
        print(f"❌ Database Error fetching pot balance: {e}")
        return 0.0


def get_investments_summary() -> dict:
    """
    Returns a complete summary for the Investments dashboard:
    {
        'total_invested': float,
        'pot_balance': float,
        'net_worth': float,
        'allocation': {'stocks': 1000.0, 'pension': 5000.0, ...}
    }
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()

            cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM investments')
            total_invested = float(cursor.fetchone()[0])

            cursor.execute('SELECT COALESCE(SUM(amount), 0) FROM pot_transactions')
            pot_balance = float(cursor.fetchone()[0])

            cursor.execute(
                'SELECT category, SUM(amount) FROM investments GROUP BY category'
            )
            allocation = {row[0]: float(row[1]) for row in cursor.fetchall()}

            return {
                'total_invested': total_invested,
                'pot_balance': pot_balance,
                'net_worth': total_invested + pot_balance,
                'allocation': allocation,
            }
    except sqlite3.Error as e:
        print(f"❌ Database Error fetching investments summary: {e}")
        return {
            'total_invested': 0.0,
            'pot_balance': 0.0,
            'net_worth': 0.0,
            'allocation': {},
        }
