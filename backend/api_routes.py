import os
import datetime
from flask import Blueprint, request, jsonify
from bff_routes import invalidate_cache
from database_manager import (
    add_expense,
    set_category_budget,
    add_investment,
    add_to_pot,
    log_new_investment,
    get_investments_summary,
    get_all_investments,
    update_investment,
    get_total_monthly_expenses,
    get_average_total_monthly_expenses,
    get_monthly_expenses_by_category,
    get_shared_monthly_totals,
    get_total_budget,
    check_total_pacing,
    get_ai_context_data,
    get_all_budgets,
    get_raw_monthly_expenses, get_raw_yearly_expenses, get_yearly_summary,
    get_spending_per_person_per_month, get_monthly_settlement, get_personal_monthly_totals,
    update_expense_category, update_expense
)
import gspread
import calendar

api = Blueprint('api', __name__)

# ==============================================================================================================#
#                                             EXPENSES ROUTES                                                   #
# ==============================================================================================================#

@api.route('/expenses', methods=['POST'])
def api_add_expense():
    """Adds a new expense record via JSON payload."""
    data = request.json
    success = add_expense(
        merchant=data['merchant'],
        amount=data['amount'],
        payer=data['payer'],
        split=data['split'],
        category=data['category']
    )
    if success:
        invalidate_cache()
    return jsonify({"success": success})

@api.route('/expenses/monthly', methods=['GET'])
def api_monthly_expenses():
    """Returns aggregated monthly total for a specific year and month."""
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))
    total = get_total_monthly_expenses(year, month)
    return jsonify({"total": total, "year": year, "month": month})

@api.route('/expenses/raw', methods=['GET'])
def api_raw_expenses():
    """Returns detailed expense records for the Dash DataTable."""
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))
    split = request.args.get('split') # Optional: 'shared' or 'personal'
    data = get_raw_monthly_expenses(year, month, split)
    return jsonify(data)

@api.route('/expenses/average', methods=['GET'])
def api_average_monthly_expenses():
    """Returns the historical average monthly spending."""
    average = get_average_total_monthly_expenses()
    return jsonify({"average": average})

@api.route('/expenses/by-category', methods=['GET'])
def api_expenses_by_category():
    """Returns total spending for a specific category and month."""
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))
    category = request.args.get('category')
    if not category:
        return jsonify({"error": "category is required"}), 400
    total = get_monthly_expenses_by_category(year, month, category)
    return jsonify({"category": category, "total": total, "year": year, "month": month})

@api.route('/expenses/per-person', methods=['GET'])
def api_spending_per_person():
    """Returns total spending per person for a specific month."""
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))
    data = get_spending_per_person_per_month(year, month)
    return jsonify({"year": year, "month": month, "spending": data})

@api.route('/expenses/settlement', methods=['GET'])
def api_monthly_settlement():
    """Returns who owes whom for a specific month based on shared expenses."""
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))
    result = get_monthly_settlement(year, month)
    return jsonify(result)

@api.route('/expenses/personal', methods=['GET'])
def api_personal_monthly_totals():
    """Returns total personal spending per person for a specific month."""
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))
    data = get_personal_monthly_totals(year, month)
    return jsonify({"year": year, "month": month, "spending": data})

@api.route('/expenses/shared', methods=['GET'])
def api_shared_monthly_totals():
    """Returns the actual shared expense burden per person (total shared / 2)."""
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))
    per_person = get_shared_monthly_totals(year, month)
    return jsonify({"per_person_share": per_person, "year": year, "month": month})

# ==============================================================================================================#
#                                             BUDGET ROUTES                                                     #
# ==============================================================================================================#

@api.route('/budget', methods=['POST'])
def api_set_budget():
    """Sets or updates a budget target for a specific category."""
    data = request.json
    success = set_category_budget(
        category=data['category'],
        monthly_target=data['monthly_target']
    )
    return jsonify({"success": success})

@api.route('/budget/all', methods=['GET'])
def api_all_budgets():
    """Returns all category-specific budget targets."""
    data = get_all_budgets()
    return jsonify(data)

@api.route('/budget/pacing', methods=['GET'])
def api_budget_pacing():
    """Returns progress toward the total monthly budget."""
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))
    result = check_total_pacing(year, month)
    return jsonify(result)

# ==============================================================================================================#
#                                             OTHER SERVICES                                                    #
# ==============================================================================================================#

@api.route('/investments', methods=['POST'])
def api_add_investment():
    """Adds a new investment record (legacy, no pot deduction)."""
    data = request.json
    success = add_investment(
        category=data['category'],
        amount=data['amount'],
        name=data['name'],
        ticker=data.get('ticker'),
        expense_ratio=data.get('expense_ratio')
    )
    return jsonify({"success": success})


@api.route('/investments/summary', methods=['GET'])
def api_investments_summary():
    """Returns total_invested, pot_balance, net_worth, and allocation — filtered by payer."""
    payer = request.args.get('payer', 'Michael')
    return jsonify(get_investments_summary(payer))


@api.route('/investments/all', methods=['GET'])
def api_get_all_investments():
    """Returns all investment records for a specific payer."""
    payer = request.args.get('payer', 'Michael')
    return jsonify(get_all_investments(payer))


@api.route('/investments/<int:inv_id>', methods=['PUT'])
def api_update_investment(inv_id):
    """Updates an investment's amount, name, and ticker (no pot adjustment)."""
    data = request.get_json()
    amount = data.get('amount')
    name = data.get('name')
    if not all([amount is not None, name]):
        return jsonify({"error": "amount and name are required"}), 400
    success = update_investment(
        inv_id=inv_id,
        amount=float(amount),
        name=name,
        ticker=data.get('ticker'),
    )
    if not success:
        return jsonify({"error": "Investment not found"}), 404
    return jsonify({"success": True})


@api.route('/investments/add-funds', methods=['POST'])
def api_add_funds_to_pot():
    """Adds funds to a specific payer's Pot."""
    data = request.json
    amount = data.get('amount')
    payer = data.get('payer', 'Michael')
    if not amount or float(amount) <= 0:
        return jsonify({"error": "amount must be a positive number"}), 400
    success = add_to_pot(amount=float(amount), payer=payer, note=data.get('note'))
    return jsonify({"success": success})


@api.route('/investments/new', methods=['POST'])
def api_log_new_investment():
    """Logs a new investment and atomically deducts from the payer's Pot."""
    data = request.json
    category = data.get('category')
    amount = data.get('amount')
    name = data.get('name')
    payer = data.get('payer', 'Michael')
    if not all([category, amount, name]):
        return jsonify({"error": "category, amount, and name are required"}), 400
    success = log_new_investment(
        category=category,
        amount=float(amount),
        name=name,
        payer=payer,
        ticker=data.get('ticker'),
        expense_ratio=data.get('expense_ratio'),
    )
    return jsonify({"success": success})

@api.route('/insights', methods=['GET'])
def api_ai_insights():
    """Returns context data for AI financial analysis."""
    return jsonify(get_ai_context_data())

@api.route('/insights/generate', methods=['POST'])
def api_generate_insight():
    """Triggers the AI insights agent. Protected by a secret token."""
    from ai_insights import FinancialInsightsAgent

    token = request.args.get('token')
    if token != os.getenv('CRON_SECRET'):
        return jsonify({"error": "Unauthorized"}), 401

    agent = FinancialInsightsAgent()
    agent.generate_insight()
    return jsonify({"message": "Insight generated successfully."})


@api.route('/gmail/renew-watch', methods=['POST'])
def api_renew_gmail_watch():
    """Renews the Gmail push notification watch for all users."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    token = request.args.get('token')
    if token != os.getenv('CRON_SECRET'):
        return jsonify({"error": "Unauthorized"}), 401

    project_id = os.getenv('GOOGLE_PROJECT_ID')
    topic_name = f"projects/{project_id}/topics/gmail-notifications"
    watch_request = {'labelIds': ['INBOX'], 'topicName': topic_name}

    results = {}
    for user in [os.getenv('PAYER_1', 'Michael').lower(), os.getenv('PAYER_2', 'Ori').lower()]:
        try:
            creds = Credentials.from_authorized_user_file(f'token_{user}.json', ['https://www.googleapis.com/auth/gmail.readonly'])
            service = build('gmail', 'v1', credentials=creds)
            response = service.users().watch(userId='me', body=watch_request).execute()
            results[user] = {"status": "ok", "expiration": response.get('expiration')}
        except Exception as e:
            results[user] = {"status": "error", "message": str(e)}

    return jsonify(results)


@api.route('/expenses/yearly/raw', methods=['GET'])
def api_raw_yearly_expenses():
    """Returns detailed expense records for an entire year."""
    year = int(request.args.get('year', datetime.date.today().year))
    split = request.args.get('split')  # Can be None, 'shared', or 'personal'

    data = get_raw_yearly_expenses(year, split)
    return jsonify(data)


@api.route('/expenses/yearly/summary', methods=['GET'])
def api_yearly_summary():
    """Returns aggregated summaries for charts in one year."""
    year = int(request.args.get('year', datetime.date.today().year))
    split = request.args.get('split')
    data = get_yearly_summary(year, split)
    return jsonify(data)

@api.route('/expenses/<int:expense_id>/category', methods=['PUT'])
def api_update_category(expense_id):
    """Updates the category of a specific expense."""
    data = request.get_json()
    new_category = data.get('category')
    if not new_category:
        return jsonify({"error": "category is required"}), 400
    success = update_expense_category(expense_id, new_category)
    if not success:
        return jsonify({"error": "Expense not found"}), 404
    return jsonify({"message": "Category updated"})


@api.route('/expenses/<int:expense_id>', methods=['PUT'])
def api_update_expense(expense_id):
    """Updates all editable fields of a specific expense (merchant, amount, category, payer)."""
    data = request.get_json()
    merchant = data.get('merchant')
    amount = data.get('amount')
    category = data.get('category')
    payer = data.get('payer')

    if not all([merchant, amount is not None, category, payer]):
        return jsonify({"error": "merchant, amount, category and payer are all required"}), 400

    success = update_expense(expense_id, merchant, amount, category, payer)
    if not success:
        return jsonify({"error": "Expense not found"}), 404
    invalidate_cache()
    return jsonify({"success": True})


@api.route('/expenses/export-sheets', methods=['POST'])
def api_export_to_sheets():
    data = request.get_json()
    year = int(data.get('year'))
    month = int(data.get('month'))
    split = data.get('split', 'shared')

    spreadsheet_id = os.getenv('SHEETS_SPREADSHEET_ID')
    if not spreadsheet_id:
        return jsonify({"error": "SHEETS_SPREADSHEET_ID not set"}), 500

    payer_1 = os.getenv('PAYER_1', 'Michael').lower()
    payer_2 = os.getenv('PAYER_2', 'Ori').lower()
    if split in (payer_1, payer_2):
        rows = get_raw_monthly_expenses(year, month, 'personal')
        rows = [r for r in rows if r.get('payer', '').lower() == split.lower()]
    else:
        rows = get_raw_monthly_expenses(year, month, split)

    if not rows:
        return jsonify({"error": "No data for this month"}), 404

    tab_name = f"{calendar.month_abbr[month]} {year} ({split})"

    try:
        gc = gspread.service_account(filename='service_account.json')
        spreadsheet = gc.open_by_key(spreadsheet_id)

        try:
            existing = spreadsheet.worksheet(tab_name)
            spreadsheet.del_worksheet(existing)
        except gspread.exceptions.WorksheetNotFound:
            pass

        ws = spreadsheet.add_worksheet(title=tab_name, rows=len(rows) + 5, cols=10)

        headers = ["ID", "Date", "Merchant", "Amount (₪)", "Category", "Payer", "Split"]
        ws.append_row(headers)

        for row in rows:
            ws.append_row([
                row.get("id", ""),
                row.get("date", ""),
                row.get("merchant", ""),
                row.get("amount", 0),
                row.get("category", ""),
                row.get("payer", ""),
                row.get("split", ""),
            ])

        sheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        return jsonify({"success": True, "url": sheet_url, "tab": tab_name, "rows": len(rows)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500
