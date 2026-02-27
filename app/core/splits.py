from decimal import Decimal, ROUND_HALF_UP
from typing import Any

SplitResult = list[tuple[int, Decimal]]  # (participant_id, amount_owed_inr)


def calculate_splits(
    total_amount_inr: Decimal,
    participant_ids: list[int],
    split_type: str,
    split_input: dict[str, Any],
) -> SplitResult:
    """
    Compute per-participant splits. Sum of outputs always equals total_amount_inr exactly.
    Rounding remainder is assigned to the first participant.

    split_type values: 'equal' | 'exact' | 'percentage' | 'shares'

    split_input shapes:
      equal:      {}
      exact:      {"amounts": {"1": "500.00", "2": "250.00"}}   # keys are str(participant_id)
      percentage: {"percentages": {"1": "50.0", "2": "50.0"}}   # must sum to 100
      shares:     {"shares": {"1": 2, "2": 1}}                   # any positive integers
    """
    if not participant_ids:
        raise ValueError("At least one participant required")
    if total_amount_inr <= 0:
        raise ValueError("Total amount must be positive")

    match split_type:
        case "equal":
            return _equal(total_amount_inr, participant_ids)
        case "exact":
            return _exact(total_amount_inr, participant_ids, split_input)
        case "percentage":
            return _percentage(total_amount_inr, participant_ids, split_input)
        case "shares":
            return _shares(total_amount_inr, participant_ids, split_input)
        case _:
            raise ValueError(f"Unknown split_type: {split_type}")


def _equal(total: Decimal, participant_ids: list[int]) -> SplitResult:
    n = len(participant_ids)
    per_person = (total / n).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    result = [(pid, per_person) for pid in participant_ids]
    return _fix_rounding(result, total)


def _exact(total: Decimal, participant_ids: list[int], split_input: dict) -> SplitResult:
    amounts_raw = split_input.get("amounts", {})
    result = []
    for pid in participant_ids:
        amt = Decimal(str(amounts_raw.get(str(pid), amounts_raw.get(pid, "0"))))
        result.append((pid, amt.quantize(Decimal("0.01"))))
    actual_sum = sum(a for _, a in result)
    if abs(actual_sum - total) > Decimal("0.10"):
        raise ValueError(
            f"Exact amounts sum ({actual_sum}) doesn't match total ({total})."
        )
    return _fix_rounding(result, total)


def _percentage(total: Decimal, participant_ids: list[int], split_input: dict) -> SplitResult:
    percentages_raw = split_input.get("percentages", {})
    result = []
    pct_sum = Decimal("0")
    for pid in participant_ids:
        pct = Decimal(str(percentages_raw.get(str(pid), percentages_raw.get(pid, "0"))))
        pct_sum += pct
        amt = (total * pct / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        result.append((pid, amt))
    if abs(pct_sum - Decimal("100")) > Decimal("0.01"):
        raise ValueError(f"Percentages must sum to 100, got {pct_sum}")
    return _fix_rounding(result, total)


def _shares(total: Decimal, participant_ids: list[int], split_input: dict) -> SplitResult:
    shares_raw = split_input.get("shares", {})
    share_values = {}
    total_shares = Decimal("0")
    for pid in participant_ids:
        s = Decimal(str(shares_raw.get(str(pid), shares_raw.get(pid, "1"))))
        if s <= 0:
            raise ValueError(f"Shares must be positive, got {s} for participant {pid}")
        share_values[pid] = s
        total_shares += s
    result = []
    for pid in participant_ids:
        amt = (total * share_values[pid] / total_shares).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        result.append((pid, amt))
    return _fix_rounding(result, total)


def _fix_rounding(result: SplitResult, total: Decimal) -> SplitResult:
    """Assign any rounding difference to the first participant."""
    current_sum = sum(a for _, a in result)
    diff = total - current_sum
    if diff != Decimal("0"):
        first_pid, first_amt = result[0]
        result[0] = (first_pid, first_amt + diff)
    return result


def validate_splits(splits: SplitResult, total: Decimal) -> bool:
    return sum(a for _, a in splits) == total
