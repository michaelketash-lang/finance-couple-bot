import sqlite3

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
    get_total_budget,
    get_all_budgets,
    check_total_pacing,
)
from db_investments import add_investment
from db_insights import get_ai_context_data


def setup_database():
    """Initializes all database tables."""
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

    cursor.execute('''CREATE TABLE IF NOT EXISTS investments (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        category TEXT CHECK(category IN('stocks', 'bonds', 'cash', 'pension', 'gemel', 'hishtalmut')),
                                        amount REAL,
                                        name TEXT,
                                        ticker TEXT DEFAULT NULL,
                                        expense_ratio REAL DEFAULT NULL
                                        )
                                    ''')

    cursor.execute('''CREATE TABLE IF NOT EXISTS ai_insights (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        insight TEXT,
                                        type TEXT CHECK(type IN('alert', 'summary', 'praise')),
                                        isread BOOLEAN DEFAULT FALSE
                                        )
                                    ''')

    connection.commit()
    return True


if __name__ == '__main__':
    setup_database()
