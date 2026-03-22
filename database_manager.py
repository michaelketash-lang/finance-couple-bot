import sqlite3
#sqlite3 is unuique in that it the database is serverless, the database is saved locally, perfect for small to medium sized projects
# creates a connection to the database file itself
connection = sqlite3.connect('expenses.db')
# a cursor runs the commands we want to run in the database
cursor = connection.cursor()

#creates the table
cursor.execute('''CREATE TABLE IF NOT EXISTS expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    merchant TEXT,
                    amount REAL,
                    payer TEXT,
                    split TEXT CHECK(split IN('shared', 'personal')),
                    category TEXT CHECK(category IN ('Rent', 'Bills', 'Food', 'Transport', 'Home', 'Shopping', 'Health', 'Leisure', 'Other')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')

#saves the changes - commit tells sqlite- update the db file.
connection.commit()

# add expense function inserts the expense into the database
def add_expense(merchant, amount, payer, split, category):
    try:
        with sqlite3.connect('expenses.db') as conn:
            cursor = conn.cursor()
            #we use ? ? ? ? ? for security - it makes sure that we (or a user) can't trick the database with a command, it means that only text/numebers are expected her
            #it also deals with the messy formatting, sql requires strings to be in quotes, so names of places with strings can break the code. not when using ?.
            sql = '''INSERT INTO expenses (merchant, amount, payer, split, category) 
                     VALUES (?, ?, ?, ?, ?)'''

            cursor.execute(sql, (merchant, amount, payer, split, category))
            conn.commit()
            return True

    except sqlite3.IntegrityError as e:
        print(f"❌ Validation Error: Did you use a wrong category or split type? ({e})")
    except sqlite3.Error as e:
        print(f"❌ Database Error: {e}")
    return False


