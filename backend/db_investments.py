import sqlite3

INVESTMENT_CATEGORIES = ['stocks', 'bonds', 'cash', 'pension', 'gemel', 'hishtalmut']


def add_investment(category, amount, name, ticker, expense_ratio):
    """Legacy: adds investment without payer or pot deduction."""
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''INSERT INTO investments (category, amount, name, ticker, expense_ratio)
                   VALUES (?, ?, ?, ?, ?)''',
                (category, amount, name, ticker, expense_ratio)
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError as e:
        print(f"❌ Validation Error: ({e})")
    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
    return False


def add_to_pot(amount: float, payer: str, note: str = None) -> bool:
    """Adds funds to a specific person's Pot."""
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO pot_transactions (amount, payer, note) VALUES (?, ?, ?)',
                (float(amount), payer, note)
            )
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"❌ Database Error adding to pot: {e}")
        return False


def log_new_investment(category: str, amount: float, name: str, payer: str,
                       ticker: str = None, expense_ratio: float = None) -> bool:
    """
    Logs a new investment for a specific payer AND atomically deducts from their Pot.
    Returns False if pot balance is insufficient or category is invalid.
    """
    if category not in INVESTMENT_CATEGORIES:
        print(f"❌ Invalid category: {category}")
        return False
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()

            cursor.execute(
                'SELECT COALESCE(SUM(amount), 0) FROM pot_transactions WHERE payer = ?',
                (payer,)
            )
            pot_balance = float(cursor.fetchone()[0])

            if pot_balance < float(amount):
                print(f"❌ Insufficient pot for {payer}: ₪{pot_balance:.2f} < ₪{float(amount):.2f}")
                return False

            cursor.execute(
                '''INSERT INTO investments (category, amount, name, ticker, expense_ratio, payer)
                   VALUES (?, ?, ?, ?, ?, ?)''',
                (category, float(amount), name, ticker, expense_ratio, payer)
            )
            cursor.execute(
                'INSERT INTO pot_transactions (amount, payer, note) VALUES (?, ?, ?)',
                (-float(amount), payer, f"Investment: {name} ({category})")
            )
            conn.commit()
            return True
    except sqlite3.IntegrityError as e:
        print(f"❌ Validation Error: ({e})")
    except sqlite3.Error as e:
        print(f"❌ Database Error logging investment: {e}")
    return False


def get_pot_balance(payer: str) -> float:
    """Returns the current Pot balance for a specific payer."""
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT COALESCE(SUM(amount), 0) FROM pot_transactions WHERE payer = ?',
                (payer,)
            )
            return float(cursor.fetchone()[0])
    except sqlite3.Error as e:
        print(f"❌ Database Error fetching pot balance: {e}")
        return 0.0


def get_investments_summary(payer: str) -> dict:
    """
    Returns KPI summary filtered by payer:
    { total_invested, pot_balance, net_worth, allocation }
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()

            cursor.execute(
                'SELECT COALESCE(SUM(amount), 0) FROM investments WHERE payer = ?',
                (payer,)
            )
            total_invested = float(cursor.fetchone()[0])

            cursor.execute(
                'SELECT COALESCE(SUM(amount), 0) FROM pot_transactions WHERE payer = ?',
                (payer,)
            )
            pot_balance = float(cursor.fetchone()[0])

            cursor.execute(
                'SELECT category, SUM(amount) FROM investments WHERE payer = ? GROUP BY category',
                (payer,)
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
        return {'total_invested': 0.0, 'pot_balance': 0.0, 'net_worth': 0.0, 'allocation': {}}


def get_all_investments(payer: str) -> list:
    """Returns all investment records for a specific payer, ordered by category then name."""
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''SELECT id, category, name, amount, ticker
                   FROM investments WHERE payer = ? ORDER BY category, name''',
                (payer,)
            )
            return [
                {
                    'id': r[0],
                    'category': r[1],
                    'name': r[2],
                    'amount': float(r[3]),
                    'ticker': r[4] or '',
                }
                for r in cursor.fetchall()
            ]
    except sqlite3.Error as e:
        print(f"❌ Database Error fetching investments: {e}")
        return []


def update_investment(inv_id: int, amount: float, name: str,
                      ticker: str = None) -> bool:
    """
    Updates an investment's amount, name, and ticker.
    This is a direct value edit — no pot adjustment is made.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                '''UPDATE investments SET amount = ?, name = ?, ticker = ? WHERE id = ?''',
                (float(amount), name, ticker or None, inv_id)
            )
            if cursor.rowcount == 0:
                print(f"❌ Investment id={inv_id} not found.")
                return False
            conn.commit()
            return True
    except sqlite3.Error as e:
        print(f"❌ Database Error updating investment: {e}")
        return False
