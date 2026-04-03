"""
db_investments.py
=================

Data-access functions for the ``investments`` table.

Handles writing investment holdings (stocks, bonds, cash, pension, etc.)
to the database.
"""

import sqlite3


def add_investment(category: str, amount: float, name: str,
                   ticker: str | None, expense_ratio: float | None) -> bool:
    """Insert a new investment record into the database.

    :param category: Asset class (e.g. ``'stocks'``, ``'bonds'``, ``'pension'``).
    :param amount: Current value of the holding in ILS.
    :param name: Descriptive name of the investment (e.g. fund name).
    :param ticker: Optional ticker symbol (e.g. ``'VOO'``).
    :param expense_ratio: Optional annual expense ratio as a decimal (e.g. ``0.003``).
    :returns: ``True`` on success, ``False`` on validation or database error.
    """
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
