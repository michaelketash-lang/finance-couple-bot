"""
bff_routes.py
=============

Backend-for-Frontend (BFF) Flask Blueprint that aggregates multiple database
queries into single endpoints, reducing round-trips from the Dash frontend.

Includes an in-process cache keyed by year and month, invalidated on any
expense mutation via ``invalidate_cache()``.

All routes are registered under the ``bff`` Blueprint and mounted by
``flask_app.py``.
"""

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
    """Clear the BFF response cache.

    Must be called after any expense is added or edited to prevent
    stale data from being served.
    """
    _cache.clear()


# ==============================================================================================================#
#                                         DASHBOARD DATA ENDPOINT                                              #
#         Expenses tab data: raw monthly rows, yearly summaries, KPI aggregates, and payer breakdown.         #
# ==============================================================================================================#

@bff.route('/dashboard-data', methods=['GET'])
def dashboard_data():
    """Return all data needed by the Expenses tab in a single response.

    Replaces 7 individual API calls with one round-trip. The frontend
    filters and aggregates the payload in-memory for charts and KPI cards.

    :query year: Year to query (defaults to current year).
    :query month: Month to query (defaults to current month).
    :returns: JSON with ``expenses``, ``yearly_raw``, ``kpis``, and ``payer_summary``.
    """
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
#         Budget tab data: category targets, per-category actuals, and overall pacing status.                 #
# ==============================================================================================================#

@bff.route('/budget-data', methods=['GET'])
def budget_data():
    """Return budget targets, per-category actuals, and pacing in a single response.

    Actuals are filtered to match the requested payer:
      - ``shared``  → only ``split='shared'`` expenses
      - a payer name → only ``split='personal'`` expenses for that payer

    :query year:  Year to query (defaults to current year).
    :query month: Month to query (defaults to current month).
    :query payer: Whose budget to load — ``'shared'``, ``'Michael'``, ``'Ori'``, etc.
                  Defaults to ``'shared'``.
    :returns: JSON with ``budgets``, ``category_actuals``, and ``pacing``.
    """
    year  = int(request.args.get('year',  datetime.date.today().year))
    month = int(request.args.get('month', datetime.date.today().month))
    payer = request.args.get('payer', 'shared')

    cache_key = f'budget:{year}:{month}:{payer}'
    if cache_key in _cache:
        return jsonify(_cache[cache_key])

    # 1. Budget targets for the requested payer.
    budgets = get_all_budgets(payer)

    # 2. Filter raw expenses by payer, then aggregate by category.
    raw = get_raw_monthly_expenses(year, month)
    if payer == 'shared':
        filtered = [r for r in raw if r.get('split') == 'shared']
    else:
        filtered = [r for r in raw
                    if r.get('split') == 'personal' and r.get('payer') == payer]

    category_actuals: dict = {}
    for row in filtered:
        cat = row['category']
        category_actuals[cat] = round(
            category_actuals.get(cat, 0.0) + float(row['amount']), 2
        )

    # 3. Overall pacing status (always uses the shared budget).
    pacing = check_total_pacing(year, month)

    data = {
        'budgets': budgets,
        'category_actuals': category_actuals,
        'pacing': pacing,
    }

    _cache[cache_key] = data
    return jsonify(data)
