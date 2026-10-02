"""
tests/test_settlement.py
========================

Unit tests for the settlement calculator.

The settlement logic is pure arithmetic — no database, no network, no API keys.
These tests cover the cases where a bug would silently cost real money.

Run with:
    cd backend
    pytest tests/test_settlement.py -v
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db_expenses import _calculate_settlement


def test_both_paid_equally_is_balanced():
    """When both people paid the same amount, nobody owes anything."""
    payments = {"Michael": 500.0, "Ofri": 500.0}
    result = _calculate_settlement(payments)
    assert result == {"balanced": True, "amount": 0.0}


def test_one_person_paid_everything():
    """When one person paid all shared expenses, the other owes exactly half."""
    payments = {"Michael": 1000.0, "Ofri": 0.0}
    result = _calculate_settlement(payments)
    assert result["debtor"] == "Ofri"
    assert result["creditor"] == "Michael"
    assert result["amount"] == 500.0


def test_no_transactions_returns_balanced():
    """An empty month must return balanced and not crash."""
    payments = {}
    result = _calculate_settlement(payments)
    assert result == {"balanced": True, "amount": 0.0}


def test_personal_expenses_excluded_from_settlement():
    """Settlement is based only on shared expenses passed in.

    Personal expenses are filtered out before calling this function,
    so passing only shared payments must produce the correct result.
    """
    # Michael paid 800 shared, Ofri paid 200 shared.
    # Personal expenses for either person are not included.
    # Total shared = 1000, fair share = 500.
    # Ofri underpaid by 300 → owes Michael 300.
    payments = {"Michael": 800.0, "Ofri": 200.0}
    result = _calculate_settlement(payments)
    assert result["debtor"] == "Ofri"
    assert result["creditor"] == "Michael"
    assert result["amount"] == 300.0


def test_amount_that_does_not_divide_evenly():
    """An odd amount like 33.33 NIS rounds down, leaving 1 agora unaccounted for.

    33.33 / 2 = 16.665. Python uses banker's rounding (round half to even):
    the digit before the 5 is 6 (even), so -16.665 rounds to -16.66, not -16.67.
    Ofri therefore owes 16.66 and 0.01 NIS is absorbed by rounding.
    This is a known limitation of storing amounts as floats.
    """
    payments = {"Michael": 33.33, "Ofri": 0.0}
    result = _calculate_settlement(payments)
    assert result["debtor"] == "Ofri"
    assert result["creditor"] == "Michael"
    assert result["amount"] == 16.66
