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
    get_ai_context_data
)

api = Blueprint('api', __name__)

# ==============================================================================================================#
#                              EXPENSES                                                                         #
# ==============================================================================================================#

@api.route('/expenses', methods=['POST'])
def api_add_expense():
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
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))
    total = get_total_monthly_expenses(year, month)
    return jsonify({"total": total, "year": year, "month": month})


@api.route('/expenses/average', methods=['GET'])
def api_average_monthly_expenses():
    average = get_average_total_monthly_expenses()
    return jsonify({"average": average})


@api.route('/expenses/by-category', methods=['GET'])
def api_expenses_by_category():
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))
    category = request.args.get('category')
    if not category:
        return jsonify({"error": "category is required"}), 400
    total = get_monthly_expenses_by_category(year, month, category)
    return jsonify({"category": category, "total": total, "year": year, "month": month})


@api.route('/expenses/average-by-category', methods=['GET'])
def api_average_by_category():
    category = request.args.get('category')
    if not category:
        return jsonify({"error": "category is required"}), 400
    average = get_average_monthly_spend_by_category(category)
    return jsonify({"category": category, "average": average})


@api.route('/expenses/shared', methods=['GET'])
def api_shared_monthly_totals():
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))
    totals = get_shared_monthly_totals(year, month)
    return jsonify({"totals": [{"payer": row[0], "total": row[1]} for row in totals]})


@api.route('/expenses/weekly', methods=['GET'])
def api_weekly_expenses():
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))
    week = int(request.args.get('week'))
    if not week:
        return jsonify({"error": "week is required (1-5)"}), 400
    total = get_month_locked_weekly_expenses(year, month, week)
    return jsonify({"total": total, "year": year, "month": month, "week": week})

# ==============================================================================================================#
#                              BUDGETS                                                                          #
# ==============================================================================================================#

@api.route('/budget', methods=['POST'])
def api_set_budget():
    data = request.json
    success = set_category_budget(
        category=data['category'],
        monthly_target=data['monthly_target']
    )
    return jsonify({"success": success})


@api.route('/budget/total', methods=['GET'])
def api_total_budget():
    total = get_total_budget()
    return jsonify({"total": total})


@api.route('/budget/pacing', methods=['GET'])
def api_budget_pacing():
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))
    result = check_total_pacing(year, month)
    return jsonify(result)

# ==============================================================================================================#
#                              INVESTMENTS                                                                      #
# ==============================================================================================================#

@api.route('/investments', methods=['POST'])
def api_add_investment():
    data = request.json
    success = add_investment(
        category=data['category'],
        amount=data['amount'],
        name=data['name'],
        ticker=data.get('ticker'),
        expense_ratio=data.get('expense_ratio')
    )
    return jsonify({"success": success})

# ==============================================================================================================#
#                              AI INSIGHTS                                                                      #
# ==============================================================================================================#

@api.route('/insights', methods=['GET'])
def api_ai_insights():
    return jsonify(get_ai_context_data())
