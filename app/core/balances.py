from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import text
from dataclasses import dataclass


@dataclass
class Balance:
    participant_id: int
    display_name: str
    is_guest: bool
    net_inr: Decimal  # positive = owed money, negative = owes money


@dataclass
class DebtInstruction:
    from_id: int
    from_name: str
    to_id: int
    to_name: str
    amount_inr: Decimal


def compute_balances(group_id: int, db: Session) -> list[Balance]:
    """
    Net balance per participant:
      credits     = sum of expense amount_inr where they were the payer
      debits      = sum of their expense_splits amount_owed_inr
      settled_in  = sum of settlements received
      settled_out = sum of settlements sent
      net = credits - debits + settled_in - settled_out
    """
    sql = text("""
        SELECT
            p.id AS participant_id,
            p.display_name,
            p.is_guest,
            COALESCE(credits.total, 0) - COALESCE(debits.total, 0)
                + COALESCE(settled_in.total, 0) - COALESCE(settled_out.total, 0) AS net_inr
        FROM participants p
        LEFT JOIN (
            SELECT e.paid_by_id AS pid, SUM(e.amount_inr) AS total
            FROM expenses e WHERE e.group_id = :gid GROUP BY e.paid_by_id
        ) credits ON credits.pid = p.id
        LEFT JOIN (
            SELECT es.participant_id AS pid, SUM(es.amount_owed_inr) AS total
            FROM expense_splits es
            JOIN expenses e ON es.expense_id = e.id
            WHERE e.group_id = :gid GROUP BY es.participant_id
        ) debits ON debits.pid = p.id
        LEFT JOIN (
            SELECT s.to_participant_id AS pid, SUM(s.amount_inr) AS total
            FROM settlements s WHERE s.group_id = :gid GROUP BY s.to_participant_id
        ) settled_in ON settled_in.pid = p.id
        LEFT JOIN (
            SELECT s.from_participant_id AS pid, SUM(s.amount_inr) AS total
            FROM settlements s WHERE s.group_id = :gid GROUP BY s.from_participant_id
        ) settled_out ON settled_out.pid = p.id
        WHERE p.group_id = :gid
        ORDER BY p.is_guest, p.display_name
    """)
    rows = db.execute(sql, {"gid": group_id}).fetchall()
    return [
        Balance(
            participant_id=r.participant_id,
            display_name=r.display_name,
            is_guest=bool(r.is_guest),
            net_inr=Decimal(str(r.net_inr or "0")).quantize(Decimal("0.01")),
        )
        for r in rows
    ]


def simplify_debts(balances: list[Balance]) -> list[DebtInstruction]:
    """
    Greedy debt simplification. Produces minimum transactions to settle all member debts.
    Guests are always excluded — their debts are handled separately.
    """
    member_balances = {b.participant_id: b for b in balances if not b.is_guest}

    creditors = sorted(
        [b for b in member_balances.values() if b.net_inr > Decimal("0.01")],
        key=lambda b: b.net_inr, reverse=True
    )
    debtors = sorted(
        [b for b in member_balances.values() if b.net_inr < Decimal("-0.01")],
        key=lambda b: b.net_inr
    )

    cred_amounts = {b.participant_id: b.net_inr for b in creditors}
    debt_amounts = {b.participant_id: abs(b.net_inr) for b in debtors}
    cred_ids = [b.participant_id for b in creditors]
    debt_ids = [b.participant_id for b in debtors]

    instructions: list[DebtInstruction] = []
    ci, di = 0, 0

    while ci < len(cred_ids) and di < len(debt_ids):
        cid = cred_ids[ci]
        did = debt_ids[di]
        transfer = min(cred_amounts[cid], debt_amounts[did])

        if transfer > Decimal("0.01"):
            instructions.append(DebtInstruction(
                from_id=did,
                from_name=member_balances[did].display_name,
                to_id=cid,
                to_name=member_balances[cid].display_name,
                amount_inr=transfer.quantize(Decimal("0.01")),
            ))

        cred_amounts[cid] -= transfer
        debt_amounts[did] -= transfer

        if cred_amounts[cid] <= Decimal("0.01"):
            ci += 1
        if debt_amounts[did] <= Decimal("0.01"):
            di += 1

    return instructions
