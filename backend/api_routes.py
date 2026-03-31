import os
import datetime
from flask import Blueprint, request, jsonify
from database_manager import (
    add_expense,
    set_category_budget,
    add_investment,
    get_total_monthly_expenses,
    get_average_total_monthly_expenses,
    get_monthly_expenses_by_category,
    get_average_monthly_spend_by_category,
    get_shared_monthly_totals,
    get_month_locked_weekly_expenses,
    get_total_budget,
    check_total_pacing,
    get_ai_context_data,
    get_all_budgets,
    get_raw_monthly_expenses, get_raw_yearly_expenses, get_yearly_summary,
    get_spending_per_person_per_month, get_monthly_settlement, get_personal_monthly_totals,
    update_expense_category, update_expense
)

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
    """Adds a new investment record."""
    data = request.json
    success = add_investment(
        category=data['category'],
        amount=data['amount'],
        name=data['name'],
        ticker=data.get('ticker'),
        expense_ratio=data.get('expense_ratio')
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

    today_ordinal = datetime.date.today().toordinal()
    if today_ordinal % 3 != 0:
        return jsonify({"message": "Not the 3rd day, skipping."}), 200

    agent = FinancialInsightsAgent()
    agent.generate_insight()
    return jsonify({"message": "Insight generated successfully."})


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
    return jsonify({"success": True})
