import sqlite3
import datetime
import calendar

# ==============================================================================================================#
#                              DATABASE SETUP                                                                   #
# ==============================================================================================================#

def setup_database():
    '''
    Initializes the database for expenses and for budgeting
    :return:
    '''
    connection = sqlite3.connect('finance_bot.db')
    # a cursor runs the commands we want to run in the database
    cursor = connection.cursor()
    # Creates the expenses table
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
    # Creates the budgets table
    cursor.execute('''CREATE TABLE IF NOT EXISTS budgets (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            category TEXT UNIQUE,
                            monthly_target REAL
                            )
                        ''')
    # Creates the investments table
    cursor.execute('''CREATE TABLE IF NOT EXISTS investments (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        category TEXT CHECK(category IN('stocks', 'bonds', 'cash', 'pension', 'gemel', 'hishtalmut')),
                                        amount REAL,
                                        name TEXT,
                                        ticker TEXT DEFAULT NULL,
                                        expense_ratio REAL DEFAULT NULL                                      
                                        )
                                    ''')

    # Creates the ai insights table
    cursor.execute('''CREATE TABLE IF NOT EXISTS ai_insights (
                                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                                        insight TEXT,
                                        type TEXT CHECK(type IN('alert', 'summary', 'praise')),
                                        isread BOOLEAN DEFAULT FALSE
                                        )
                                    ''')
    #saves the changes - commit tells sqlite- update the db file.
    connection.commit()
    return True
# ==============================================================================================================#
#                          DATABASE INSERTION (EXPENSES, BUDGETS AND INVESTMENTS                                #
# ==============================================================================================================#
def add_expense(merchant, amount, payer, split, category):
    """
    Adds a new expense to the database.
    :return True if successful, False otherwise
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            #we use ? ? ? ? ? for security - it makes sure that we (or a user) can't trick the database with a command, it means that only text/numebers are expected her
            #it also deals with the messy formatting, sql requires strings to be in quotes, so names of places with strings can break the code. not when using ?.
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

def set_category_budget(category, monthly_target):
    """Inserts a new budget or updates an existing one for a category."""
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()

            # INSERT OR REPLACE handles both creation and updating!
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

def add_investment(category, amount, name, ticker, expense_ratio):
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

# ==============================================================================================================#
#                              EXPENSES DATABASE ANALYTICS                                                      #
# ==============================================================================================================#

def get_total_monthly_expenses(year, month):
    """
    Calculates the grand total of all expenses for a specific month and year,
    accounting for personal vs. shared splits.
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()

            # Format the date just like we did before (e.g., "2023-10%")
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

            # We only have one '?' placeholder now, so we only pass the month_filter
            cursor.execute(sql, (month_filter,))

            result = cursor.fetchone()[0]

            return round(result, 2) if result is not None else 0.0

    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
        return 0.0

def get_average_total_monthly_expenses():
    """
    Calculates the average total amount spent per month across all categories,
    accounting for personal vs. shared splits.
    :return average total amount spent per month across all categories
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()

            sql = '''
                SELECT AVG(monthly_total)
                FROM (
                    -- Step 1: Calculate the grand total for each month
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

            # No tuple needed in execute() since we have no '?' placeholders!
            cursor.execute(sql)

            result = cursor.fetchone()[0]

            return round(result, 2) if result is not None else 0.0

    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
        return 0.0

def get_monthly_expenses_by_category(year, month, category):
    """
    Calculates the amount spent in a specific month for a specific category.
    :return monthly_expenses_by_category
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

            # Note: The order of arguments in the tuple must match the '?' order in the SQL!
            cursor.execute(sql, (category, month_filter))

            # fetchone() returns a tuple like (150.5,), so we grab the first item [0]
            result = cursor.fetchone()[0]

            # If there are no expenses for that month/category, the database returns None.
            # We return 0.0 in that case to keep our math clean.
            return result if result is not None else 0.0

    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
        return 0.0

def get_average_monthly_spend_by_category(category):
    """
    Calculates the average amount spent per month for a specific category,
    accounting for personal vs. shared splits.
    :return avg_monthly_spend_by_category
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()

            sql = '''
                SELECT AVG(monthly_total)
                FROM (
                    -- Step 1: Calculate the total for the category, grouped by month
                    SELECT SUM(
                        CASE 
                            WHEN split = 'personal' THEN amount 
                            WHEN split = 'shared' THEN amount / 2.0
                            ELSE 0 
                        END
                    ) as monthly_total
                    FROM expenses 
                    WHERE category = ?
                    GROUP BY strftime('%Y-%m', created_at)
                )
            '''

            # Pass the category in as a single-item tuple
            cursor.execute(sql, (category,))

            # Fetch the single number result
            result = cursor.fetchone()[0]

            # round() keeps it to 2 decimal places for clean currency formatting
            return round(result, 2) if result is not None else 0.0

    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
        return 0.0

def get_shared_monthly_totals(year, month):
    """
    Fetches the total shared expenses for a given month, grouped by payer.
    :return a list of tuples: [('Michael', 500.0), ('Ori', 300.0)]
    """
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()
            month_filter = f"{year:04d}-{month:02d}%"

            sql = '''
                SELECT payer, SUM(amount) 
                FROM expenses 
                WHERE split = 'shared' AND created_at LIKE ?
                GROUP BY payer
            '''

            cursor.execute(sql, (month_filter,))
            return cursor.fetchall()

    except sqlite3.Error as e:
        print(f"❌ Database Error in get_shared_monthly_totals: {e}")
        return []

def get_month_locked_weekly_expenses(year, month, week_number):
    """
    Calculates expenses for a 'month-locked' week.
    Week 1: Days 1-7
    Week 2: Days 8-14
    Week 3: Days 15-21
    Week 4: Days 22-28
    Week 5: Days 29+ (End of the month)
    """
    # 1. Figure out the day boundaries based on the week number
    if week_number == 1:
        start_day, end_day = 1, 7
    elif week_number == 2:
        start_day, end_day = 8, 14
    elif week_number == 3:
        start_day, end_day = 15, 21
    elif week_number == 4:
        start_day, end_day = 22, 28
    elif week_number == 5:
        start_day, end_day = 29, 31  # 31 covers the rest of any month safely
    else:
        print("❌ Invalid week number. Please choose 1, 2, 3, 4, or 5.")
        return 0.0

    # 2. Run the database query
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()

            # Filter down to the specific year and month (e.g., "2023-10%")
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
                -- Extract the day (01-31), turn it into a number, and check if it fits our week
                AND CAST(strftime('%d', created_at) AS INTEGER) BETWEEN ? AND ?
            '''

            cursor.execute(sql, (month_filter, start_day, end_day))

            result = cursor.fetchone()[0]

            return round(result, 2) if result is not None else 0.0

    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
        return 0.0

# ==============================================================================================================#
#                              BUDGET DATABASE ANALYTICS                                                        #
# ==============================================================================================================#

def get_total_budget():
    """Calculates the grand total of all category budgets combined."""
    try:
        with sqlite3.connect('finance_bot.db') as conn:
            cursor = conn.cursor()

            # Simply add up every row in the monthly_target column
            sql = "SELECT SUM(monthly_target) FROM budgets"
            cursor.execute(sql)

            result = cursor.fetchone()[0]
            return result if result is not None else 0.0

    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
        return 0.0

def check_total_pacing(year, month):
    """
    Checks if you are on track for the month.
    Returns a simple dictionary with 'status' and the 'amount' off-pace.
    """
    total_budget = get_total_budget()
    total_spent = get_total_monthly_expenses(year, month)

    if total_budget == 0.0:
        return {"status": "No Budget Set", "amount": 0.0}

    today = datetime.date.today()

    # Calculate the difference based on whether it's the current month or a past month
    if today.year == year and today.month == month:
        current_day = today.day
        days_in_month = calendar.monthrange(year, month)[1]

        # Project the end of month total
        projected_total = (total_spent / current_day) * days_in_month
        difference = projected_total - total_budget
    else:
        # If it's a past month, just look at what actually happened
        difference = total_spent - total_budget

    # Return the simplified result
    if difference > 0:
        return {"status": "Over Budget", "amount": round(difference, 2)}
    else:
        # Use abs() to remove the negative sign so it reads cleanly (e.g., "On Track by $150")
        return {"status": "On Track", "amount": round(abs(difference), 2)}

# ==============================================================================================================#
#                              INVESTMENT DATABASE ANALYTICS                                                    #
# ==============================================================================================================#

# ==============================================================================================================#
#                              AI INSIGHTS DATA COLLECTION                                                      #
# ==============================================================================================================#

def get_ai_context_data():
    """
    Gathers a financial snapshot of strictly the last 14 days for the AI Agent.
    """
    # Calculate exactly 14 days ago
    fourteen_days_ago = (datetime.datetime.now() - datetime.timedelta(days=14)).strftime('%Y-%m-%d %H:%M:%S')

    category_breakdown = []
    recent_transactions = []

    try:
        with sqlite3.connect('finance_bot.db') as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # 1. Fetch Budgets (We still need these to know your monthly limits)
            cursor.execute('SELECT category, monthly_target FROM budgets')
            budgets = {row['category']: row['monthly_target'] for row in cursor.fetchall()}

            # 2. Fetch Transactions from ONLY the last 14 days
            cursor.execute('''
                SELECT merchant, amount, category, payer, split, created_at 
                FROM expenses 
                WHERE created_at >= ? 
                ORDER BY created_at DESC
            ''', (fourteen_days_ago,))

            transactions = cursor.fetchall()

            # 3. Process the transactions and tally up the 14-day spend per category
            category_totals = {cat: 0.0 for cat in budgets.keys()}

            for row in transactions:
                cat = row['category']
                amt = row['amount']
                split = row['split']

                # Apply your split logic: if shared, it only costs you half!
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

            # 4. Format the category breakdown for the AI
            for cat, target in budgets.items():
                spent_14_days = round(category_totals.get(cat, 0.0), 2)
                category_breakdown.append({
                    "category": cat,
                    "monthly_budget": target,
                    "spent_last_14_days": spent_14_days
                })

    except sqlite3.Error as e:
        print(f"❌ Database Error in AI context gathering: {e}")

    # The clean, simple briefcase of data
    context = {
        "timeframe": "Last 14 Days",
        "category_breakdown": category_breakdown,
        "recent_transactions": recent_transactions
    }

    return context

if __name__ == '__main__':
    setup_database()