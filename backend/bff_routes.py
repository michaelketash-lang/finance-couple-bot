import datetime
from flask import Blueprint, request, jsonify
from database_manager import (
    get_raw_monthly_expenses,
    get_raw_yearly_expenses,
    get_total_monthly_expenses,
    get_average_total_monthly_expenses,
    check_total_pacing,
    get_spending_per_person_per_month,
    get_personal_monthly_totals,
    get_monthly_settlement,
    get_all_budgets,
)

bff = Blueprint('bff', __name__)

# In-process cache: { cache_key: data }
# Each entry is a fully-assembled response dict, ready to jsonify.
# Invalidated on any expense mutation (add or update).
_cache: dict = {}


def invalidate_cache() -> None:
    """Clears the BFF cache. Must be called after any expense is added or edited."""
    _cache.clear()


# ==============================================================================================================#
#                                         DASHBOARD DATA ENDPOINT                                              #
# Replaces 7 individual API calls with a single round-trip.                                                    #
# Returns everything the Expenses tab needs: raw rows, yearly summaries, KPIs, and payer breakdown.            #
# ==============================================================================================================#

@bff.route('/dashboard-data', methods=['GET'])
def dashboard_data():
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))

    cache_key = f'dashboard:{year}:{month}'
    if cache_key in _cache:
        return jsonify(_cache[cache_key])

    # 1. Raw rows for the month — the table needs the full list including ids.
    #    No split filter: the frontend filters by split value from this single payload.
    expenses = get_raw_monthly_expenses(year, month)

    # 2. All rows for the full year (no split filter) — a single query.
    #    The master callback filters/aggregates in-memory for charts.
    #    No id needed here; yearly_raw is only used for trend and pie charts.
    yearly_raw = get_raw_yearly_expenses(year)

    # 3. KPI aggregates — fast single-pass SQL queries on the backend.
    kpis = {
        'total_spent': get_total_monthly_expenses(year, month),
        'monthly_average': get_average_total_monthly_expenses(),
        'budget_pacing': check_total_pacing(year, month),
    }

    # 4. Payer summary — previously required 3 separate API round-trips.
    payer_summary = {
        'per_person': get_spending_per_person_per_month(year, month),
        'personal_totals': get_personal_monthly_totals(year, month),
        'settlement': get_monthly_settlement(year, month),
    }

    data = {
        'year': year,
        'month': month,
        'expenses': expenses,
        'yearly_raw': yearly_raw,
        'kpis': kpis,
        'payer_summary': payer_summary,
    }

    _cache[cache_key] = data
    return jsonify(data)


# ==============================================================================================================#
#                                          BUDGET DATA ENDPOINT                                                #
# Replaces 2 API calls (budget/all + expenses/raw) with a single round-trip.                                  #
# Returns budget targets, per-category actuals, and pacing status together.                                    #
# ==============================================================================================================#

@bff.route('/budget-data', methods=['GET'])
def budget_data():
    year = int(request.args.get('year', datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))

    cache_key = f'budget:{year}:{month}'
    if cache_key in _cache:
        return jsonify(_cache[cache_key])

    # 1. Budget targets — static, rarely changes.
    budgets = get_all_budgets()

    # 2. One raw expense query, then aggregate by category in Python.
    #    Raw sum (no shared/2 weighting) — matches existing budget_layout.py behaviour.
    raw = get_raw_monthly_expenses(year, month)
    category_actuals: dict = {}
    for row in raw:
        cat = row['category']
        category_actuals[cat] = round(
            category_actuals.get(cat, 0.0) + float(row['amount']), 2
        )

    # 3. Overall pacing status.
    pacing = check_total_pacing(year, month)

    data = {
        'budgets': budgets,
        'category_actuals': category_actuals,
        'pacing': pacing,
    }

    _cache[cache_key] = data
    return jsonify(data)
