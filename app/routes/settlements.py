from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.group import GroupMember
from app.models.settlement import Settlement
from app.models.expense import GuestCollection, ExpenseSplit
from app.core.auth import get_current_user
from app.core.currency import convert_to_inr
from app.core.balances import compute_balances, simplify_debts
from fastapi.templating import Jinja2Templates
from datetime import date
from decimal import Decimal

router = APIRouter(prefix="/groups/{group_id}/settlements", tags=["settlements"])
templates = Jinja2Templates(directory="templates")

@router.post("/", response_class=HTMLResponse)
async def create_settlement(
    group_id: int,
    request: Request,
    from_participant_id: int = Form(...),
    to_participant_id: int = Form(...),
    amount: Decimal = Form(...),
    currency: str = Form(...),
    notes: str = Form(None),
    settlement_date: date = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not db.query(GroupMember).filter_by(group_id=group_id, user_id=current_user.id).first():
        return HTMLResponse('<div class="alert alert-error">Not a member of this group.</div>')

    amount_inr = convert_to_inr(amount, currency, db)

    settlement = Settlement(
        group_id=group_id,
        from_participant_id=from_participant_id,
        to_participant_id=to_participant_id,
        amount_inr=amount_inr,
        currency=currency,
        amount_original=amount if currency != "INR" else None,
        notes=notes,
        date=settlement_date,
        created_by=current_user.id
    )
    db.add(settlement)
    db.commit()

    # Need fresh balances
    balances = compute_balances(group_id, db)
    debt_instructions = simplify_debts(balances)

    return templates.TemplateResponse(
        "groups/partials/balance_panel.html", 
        {"request": request, "balances": balances, "debt_instructions": debt_instructions}
    )

@router.post("/guest-collect/{split_id}", response_class=HTMLResponse)
async def collect_guest_debt(
    group_id: int,
    split_id: int,
    request: Request,
    notes: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not db.query(GroupMember).filter_by(group_id=group_id, user_id=current_user.id).first():
        return HTMLResponse('<span class="badge badge-error">Not a member</span>')
    
    gc = GuestCollection(expense_split_id=split_id, collected_by=current_user.id, notes=notes)
    db.add(gc)
    db.commit()
    
    return HTMLResponse('<span class="badge badge-success">Collected ✓</span>')
