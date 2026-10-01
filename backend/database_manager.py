"""
database_manager.py
===================

Central database module for the finance bot.

Initializes all SQLite tables via ``setup_database()`` and re-exports
every data-access function from the four ``db_*`` submodules, so the
rest of the app only needs to import from this single module.

Tables managed:
    - ``expenses`` — individual transactions with merchant, amount, payer, split, and category.
    - ``budgets`` — monthly targets per expense category.
    - ``investments`` — investment holdings by asset class.
    - ``ai_insights`` — AI-generated financial insights with read status.
"""

import sqlite3
import datetime

from db_expenses import (
    add_expense,
    get_total_monthly_expenses,
    get_average_total_monthly_expenses,
    get_monthly_expenses_by_category,
    get_spending_per_person_per_month,
    get_shared_monthly_totals,
    get_personal_monthly_totals,
    get_monthly_settlement,
    get_raw_monthly_expenses,
    update_expense_category,
    update_expense,
    get_raw_yearly_expenses,
    get_yearly_summary,
)
from db_budgets import (
    set_category_budget,
    set_budgets_batch,
    get_total_budget,
    get_all_budgets,
    check_total_pacing,
)
from db_investments import (
    add_investment,
    add_to_pot,
    log_new_investment,
    get_pot_balance,
    get_investments_summary,
    get_all_investments,
    get_investments_dashboard,
    update_investment,
    delete_investment,
)
from db_insights import get_ai_context_data


def setup_database() -> bool:
    """Create all required database tables if they do not already exist.

    :returns: ``True`` on success.
    """
    connection = sqlite3.connect('finance_bot.db')
    cursor = connection.cursor()

    cursor.execute('''CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    merchant TEXT,
                    amount REAL,
                    payer TEXT,
                    split TEXT CHECK(split IN('shared', 'personal')),
                    category TEXT CHECK(category IN ('Rent', 'Utilities', 'Groceries', 'Eating Out', 'Transport','Maintenance', 'Shopping', 'Health', 'Leisure', 'Other')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS budgets (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            category TEXT UNIQUE,
                            monthly_target REAL
                            )
                        ''')

    # Migration: add payer column and rebuild unique constraint as (category, payer).
    # Runs only once — if payer column already exists the block is skipped.
    cursor.execute("PRAGMA table_info(budgets)")
    budget_cols = [row[1] for row in cursor.fetchall()]
    if 'payer' not in budget_cols:
        cursor.execute('''
            CREATE TABLE budgets_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                monthly_target REAL,
                payer TEXT NOT NULL DEFAULT 'shared',
                UNIQUE(category, payer)
            )
        ''')
        cursor.execute('''
            INSERT INTO budgets_v2 (category, monthly_target, payer)
            SELECT category, monthly_target, 'shared' FROM budgets
        ''')
        cursor.execute('DROP TABLE budgets')
        cursor.execute('ALTER TABLE budgets_v2 RENAME TO budgets')

    cursor.execute('''CREATE TABLE IF NOT EXISTS investments (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        category TEXT,
                                        amount REAL,
                                        name TEXT,
                                        ticker TEXT DEFAULT NULL,
                                        expense_ratio REAL DEFAULT NULL
                                        )
                                    ''')

    # Migration: expand the investments CHECK constraint to include new categories.
    # Detects the old constraint by inspecting the schema and recreates the table if needed.
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='investments'")
    investments_schema = cursor.fetchone()
    if investments_schema and "CHECK" in investments_schema[0]:
        cursor.execute('''
            CREATE TABLE investments_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                amount REAL,
                name TEXT,
                ticker TEXT DEFAULT NULL,
                expense_ratio REAL DEFAULT NULL,
                payer TEXT
            )
        ''')
        cursor.execute('INSERT INTO investments_v2 SELECT id, category, amount, name, ticker, expense_ratio, payer FROM investments')
        cursor.execute('DROP TABLE investments')
        cursor.execute('ALTER TABLE investments_v2 RENAME TO investments')

    cursor.execute('''CREATE TABLE IF NOT EXISTS pot_transactions (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        amount REAL NOT NULL,
                                        note TEXT,
                                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                        )
                                    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS ai_insights (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        insight TEXT,
                                        type TEXT CHECK(type IN('alert', 'summary', 'praise')),
                                        isread BOOLEAN DEFAULT FALSE
                                        )
                                    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS processed_emails (
                                        msg_id TEXT PRIMARY KEY,
                                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                        )
                                    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS pending_transactions (
                                        txn_id TEXT PRIMARY KEY,
                                        merchant TEXT,
                                        amount REAL,
                                        category TEXT,
                                        payer TEXT,
                                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                        )
                                    ''')

    # Migration: add payer column to investments and pot_transactions if not present.
    # Safe to run every startup — the except silently skips if already exists.
    for table in ('investments', 'pot_transactions'):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN payer TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists

    cleanup_pending_txns(cursor=cursor)
    connection.commit()
    return True

def is_email_processed(msg_id: str) -> bool:
    """Return True if this Gmail message ID has already been processed.

    :param msg_id: Gmail message ID to check.
    :returns: ``True`` if found in the ``processed_emails`` table, ``False`` otherwise.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT 1 FROM processed_emails WHERE msg_id = ?', (msg_id,))
            return cursor.fetchone() is not None
    except sqlite3.Error:
        return False


def mark_email_processed(msg_id: str) -> None:
    """Record a Gmail message ID as processed so it is never handled twice.

    Uses INSERT OR IGNORE so duplicate calls are safe.

    :param msg_id: Gmail message ID to persist.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR IGNORE INTO processed_emails (msg_id) VALUES (?)', (msg_id,)
            )
            conn.commit()
    except sqlite3.Error as e:
        print(f"❌ Database Error in mark_email_processed: {e}")


def cleanup_pending_txns(cursor=None) -> None:
    """Delete pending transactions older than 24 hours.

    Accepts an optional open cursor (used during ``setup_database``).
    If no cursor is provided, opens its own connection.
    """
    cutoff = (datetime.datetime.now() - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    if cursor:
        cursor.execute('DELETE FROM pending_transactions WHERE created_at < ?', (cutoff,))
    else:
        try:
            with sqlite3.connect('finance_bot.db') as conn:
                conn.execute('DELETE FROM pending_transactions WHERE created_at < ?', (cutoff,))
        except sqlite3.Error as e:
            print(f"❌ Database Error in cleanup_pending_txns: {e}")


def save_ai_insight(text: str, insight_type: str) -> int | None:
    """Persist a generated AI insight to the ``ai_insights`` table.

    :param text: The insight text produced by the AI.
    :param insight_type: One of ``'alert'``, ``'summary'``, or ``'praise'``.
    :returns: The row ID of the newly inserted row, or ``None`` on failure.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO ai_insights (insight, type, isread) VALUES (?, ?, ?)",
                (text, insight_type, False)
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        print(f"❌ Database Error in save_ai_insight: {e}")
        return None


def mark_insight_read(insight_id: int) -> None:
    """Mark an AI insight as read in the database.

    :param insight_id: Primary key of the insight to update.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            conn.execute("UPDATE ai_insights SET isread = 1 WHERE id = ?", (insight_id,))
    except sqlite3.Error as e:
        print(f"❌ Database Error in mark_insight_read: {e}")


def save_pending_txn(txn_id: str, merchant: str, amount: float, category: str, payer: str) -> None:
    """Persist a pending transaction to the database so it survives app restarts.

    :param txn_id: Short unique ID generated for this transaction.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            conn.execute(
                'INSERT OR REPLACE INTO pending_transactions (txn_id, merchant, amount, category, payer) VALUES (?, ?, ?, ?, ?)',
                (txn_id, merchant, amount, category, payer)
            )
    except sqlite3.Error as e:
        print(f"❌ Database Error in save_pending_txn: {e}")


def load_pending_txn(txn_id: str) -> dict | None:
    """Load a pending transaction from the database by its ID.

    :param txn_id: Short unique ID to look up.
    :returns: Dict with merchant, amount, category, payer keys, or ``None`` if not found.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            conn.row_factory = sqlite3.Row
            cutoff = (datetime.datetime.now() - datetime.timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
            row = conn.execute(
                'SELECT merchant, amount, category, payer FROM pending_transactions WHERE txn_id = ? AND created_at >= ?',
                (txn_id, cutoff)
            ).fetchone()
            return dict(row) if row else None
    except sqlite3.Error as e:
        print(f"❌ Database Error in load_pending_txn: {e}")
        return None


def delete_pending_txn(txn_id: str) -> None:
    """Remove a pending transaction from the database after it has been acted on.

    :param txn_id: Short unique ID to delete.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            conn.execute('DELETE FROM pending_transactions WHERE txn_id = ?', (txn_id,))
    except sqlite3.Error as e:
        print(f"❌ Database Error in delete_pending_txn: {e}")


if __name__ == '__main__':
    setup_database()