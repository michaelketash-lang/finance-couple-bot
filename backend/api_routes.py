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
    get_raw_monthly_expenses, get_raw_yearly_expenses
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

@api.route('/expenses/shared', methods=['GET'])
def api_shared_monthly_totals():
    """Returns shared expense totals grouped by payer."""
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))
    totals = get_shared_monthly_totals(year, month)
    return jsonify({"totals": [{"payer": row[0], "total": row[1]} for row in totals]})

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

@api.route('/expenses/yearly/raw', methods=['GET'])
def api_raw_yearly_expenses():
    """Returns detailed expense records for an entire year."""
    year = int(request.args.get('year', datetime.date.today().year))
    split = request.args.get('split')  # Can be None, 'shared', or 'personal'

    data = get_raw_yearly_expenses(year, split)
    return jsonify(data)