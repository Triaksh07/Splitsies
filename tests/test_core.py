import pytest
from decimal import Decimal
from app.core.splits import calculate_splits, validate_splits
from app.core.balances import compute_balances, simplify_debts, Balance

# --- SPLITS TESTS ---

def test_split_equal_clean():
    splits = calculate_splits(Decimal("300.00"), [1, 2, 3], "equal", {})
    assert len(splits) == 3
    for _, amt in splits:
        assert amt == Decimal("100.00")
    assert validate_splits(splits, Decimal("300.00"))

def test_split_equal_rounding():
    splits = calculate_splits(Decimal("100.00"), [1, 2, 3], "equal", {})
    assert len(splits) == 3
    assert validate_splits(splits, Decimal("100.00"))
    # First pid gets the +0.01 fix
    assert splits[0][1] == Decimal("33.34")
    assert splits[1][1] == Decimal("33.33")
    assert splits[2][1] == Decimal("33.33")

def test_split_exact_valid():
    splits = calculate_splits(
        Decimal("750.00"), 
        [1, 2], 
        "exact", 
        {"amounts": {"1": "500.00", "2": "250.00"}}
    )
    assert len(splits) == 2
    assert validate_splits(splits, Decimal("750.00"))
    assert splits[0][1] == Decimal("500.00")
    assert splits[1][1] == Decimal("250.00")

def test_split_exact_mismatch():
    with pytest.raises(ValueError):
        calculate_splits(
            Decimal("750.00"), 
            [1, 2], 
            "exact", 
            {"amounts": {"1": "400.00", "2": "200.00"}}
        )

def test_split_percentage_valid():
    splits = calculate_splits(
        Decimal("100.00"), 
        [1, 2], 
        "percentage", 
        {"percentages": {"1": "33.3", "2": "66.7"}}
    )
    assert validate_splits(splits, Decimal("100.00"))
    # The first pid gets the rounding diff
    assert splits[0][1] == Decimal("33.30")
    assert splits[1][1] == Decimal("66.70")

def test_split_percentage_invalid():
    with pytest.raises(ValueError):
        calculate_splits(
            Decimal("100.00"), 
            [1, 2], 
            "percentage", 
            {"percentages": {"1": "50.0", "2": "40.0"}}
        )

def test_split_shares_equal():
    splits = calculate_splits(
        Decimal("100.00"), 
        [1, 2], 
        "shares", 
        {"shares": {"1": "1", "2": "1"}}
    )
    assert validate_splits(splits, Decimal("100.00"))
    assert splits[0][1] == Decimal("50.00")
    assert splits[1][1] == Decimal("50.00")

def test_split_shares_unequal():
    splits = calculate_splits(
        Decimal("100.00"), 
        [1, 2, 3], 
        "shares", 
        {"shares": {"1": "2", "2": "2", "3": "1"}}
    )
    assert validate_splits(splits, Decimal("100.00"))
    assert splits[0][1] == Decimal("40.00")
    assert splits[1][1] == Decimal("40.00")
    assert splits[2][1] == Decimal("20.00")

def test_split_shares_zero_raises():
    with pytest.raises(ValueError):
        calculate_splits(
            Decimal("100.00"), 
            [1, 2], 
            "shares", 
            {"shares": {"1": "0", "2": "1"}}
        )

# --- BALANCES / DEBTS TESTS ---

def test_debts_simple():
    # A owes B 100
    balances = [
        Balance(1, "A", False, Decimal("-100.00")),
        Balance(2, "B", False, Decimal("100.00")),
    ]
    debts = simplify_debts(balances)
    assert len(debts) == 1
    assert debts[0].from_id == 1
    assert debts[0].to_id == 2
    assert debts[0].amount_inr == Decimal("100.00")

def test_debts_chain():
    # A owes B 100, B owes C 100 -> A owes C 100
    balances = [
        Balance(1, "A", False, Decimal("-100.00")),
        Balance(2, "B", False, Decimal("0.00")),
        Balance(3, "C", False, Decimal("100.00")),
    ]
    debts = simplify_debts(balances)
    assert len(debts) == 1
    assert debts[0].from_id == 1
    assert debts[0].to_id == 3
    assert debts[0].amount_inr == Decimal("100.00")

def test_debts_all_settled():
    balances = [
        Balance(1, "A", False, Decimal("0.00")),
        Balance(2, "B", False, Decimal("0.00")),
    ]
    debts = simplify_debts(balances)
    assert len(debts) == 0

def test_debts_exclude_guests():
    balances = [
        Balance(1, "A", False, Decimal("-100.00")),
        Balance(2, "Guest", True, Decimal("50.00")),
        Balance(3, "B", False, Decimal("100.00")),
    ]
    debts = simplify_debts(balances)
    assert len(debts) == 1
    assert debts[0].from_id == 1
    assert debts[0].to_id == 3
    assert debts[0].amount_inr == Decimal("100.00")

def test_debts_complex():
     balances = [
         Balance(1, "A", False, Decimal("-150.00")),
         Balance(2, "B", False, Decimal("250.00")),
         Balance(3, "C", False, Decimal("-50.00")),
         Balance(4, "D", False, Decimal("-50.00")),
     ]
     debts = simplify_debts(balances)
     
     # Total owed = 150 + 50 + 50 = 250
     total_transferred = sum(d.amount_inr for d in debts)
     assert total_transferred == Decimal("250.00")
     
     # Everyone who owes should be a 'from_id'
     from_ids = [d.from_id for d in debts]
     assert 1 in from_ids
     assert 3 in from_ids
     assert 4 in from_ids
     
     # Everyone who is owed should be a 'to_id'
     to_ids = [d.to_id for d in debts]
     assert all(tid == 2 for tid in to_ids) # B is the only creditor
