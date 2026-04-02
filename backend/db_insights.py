import sqlite3
import datetime


def get_ai_context_data():
    """Gathers a financial snapshot of the last 14 days for the AI agent."""
    fourteen_days_ago = (datetime.datetime.now() - datetime.timedelta(days=14)).strftime('%Y-%m-%d %H:%M:%S')

    category_breakdown = []
    recent_transactions = []

    try:
        with sqlite3.connect('finance_bot.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute('SELECT category, monthly_target FROM budgets')
            budgets = {row['category']: row['monthly_target'] for row in cursor.fetchall()}

            cursor.execute('''
                SELECT merchant, amount, category, payer, split, created_at
                FROM expenses
                WHERE created_at >= ?
                ORDER BY created_at DESC
            ''', (fourteen_days_ago,))

            transactions = cursor.fetchall()
            category_totals = {cat: 0.0 for cat in budgets.keys()}

            for row in transactions:
                cat = row['category']
                amt = row['amount']
                split = row['split']
                actual_cost = amt / 2.0 if split == 'shared' else amt

                if cat in category_totals:
                    category_totals[cat] += actual_cost
                else:
                    category_totals[cat] = actual_cost

                recent_transactions.append({
                    "date": row['created_at'][:10],
                    "merchant": row['merchant'],
                    "amount": row['amount'],
                    "category": cat,
                    "payer": row['payer'],
                    "split": split
                })

            for cat, target in budgets.items():
                spent_14_days = round(category_totals.get(cat, 0.0), 2)
                category_breakdown.append({
                    "category": cat,
                    "monthly_budget": target,
                    "spent_last_14_days": spent_14_days
                })

    except sqlite3.Error as e:
        print(f"❌ Database Error in AI context gathering: {e}")

    return {
        "timeframe": "Last 14 Days",
        "category_breakdown": category_breakdown,
        "recent_transactions": recent_transactions
    }
