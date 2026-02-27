from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.group import GroupMember
from app.models.participant import Participant
from app.models.expense import Expense, ExpenseSplit
from app.core.auth import get_current_user
from app.core.currency import convert_to_inr
from app.core.splits import calculate_splits
from fastapi.templating import Jinja2Templates
from datetime import date
from decimal import Decimal
import json

router = APIRouter(prefix="/groups/{group_id}/expenses", tags=["expenses"])
templates = Jinja2Templates(directory="templates")

@router.post("/", response_class=HTMLResponse)
async def create_expense(
    group_id: int,
    request: Request,
    description: str = Form(...),
    amount: Decimal = Form(...),
    currency: str = Form(...),
    paid_by_id: int = Form(...),
    split_type: str = Form(...),
    category: str = Form(...),
    expense_date: date = Form(...),
    notes: str = Form(None),
    split_data: str = Form(...),
    participant_ids: str = Form(...),
    guest_names: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify group membership
    if not db.query(GroupMember).filter_by(group_id=group_id, user_id=current_user.id).first():
        raise HTTPException(status_code=403, detail="Not a member of this group")

    # Handle new guests
    new_guest_ids = []
    if guest_names:
        for name in guest_names.split(","):
            name = name.strip()
            if name:
                guest = Participant(group_id=group_id, display_name=name, is_guest=True)
                db.add(guest)
                db.flush()  # To get the ID
                new_guest_ids.append(guest.id)

    # Combine existing and new participant IDs
    p_ids = [int(pid) for pid in participant_ids.split(",") if pid.strip()]
    all_pids = p_ids + new_guest_ids

    # Convert split_data string to dict
    try:
        split_input = json.loads(split_data)
        if hasattr(split_input, 'get') and not split_input:
             split_input = {}
    except json.JSONDecodeError:
        split_input = {}

    amount_inr = convert_to_inr(amount, currency, db)

    try:
        splits = calculate_splits(amount_inr, all_pids, split_type, split_input)
    except ValueError as e:
        return HTMLResponse(f'<div class="alert alert-error">{str(e)}</div>')

    expense = Expense(
        group_id=group_id,
        description=description,
        amount=amount,
        currency=currency,
        amount_inr=amount_inr,
        paid_by_id=paid_by_id,
        split_type=split_type,
        category=category,
        date=expense_date,
        notes=notes,
        created_by=current_user.id
    )
    db.add(expense)
    db.flush()

    for pid, amt_owed in splits:
        db.add(ExpenseSplit(
            expense_id=expense.id,
            participant_id=pid,
            amount_owed_inr=amt_owed
        ))

    db.commit()

    # Re-fetch for updated fragment
    expenses = db.query(Expense).filter(Expense.group_id == group_id).order_by(Expense.date.desc()).limit(50).all()
    
    return templates.TemplateResponse("groups/partials/expense_list.html", {"request": request, "expenses": expenses})


@router.delete("/{expense_id}", response_class=HTMLResponse)
async def delete_expense(
    group_id: int,
    expense_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not db.query(GroupMember).filter_by(group_id=group_id, user_id=current_user.id).first():
        raise HTTPException(status_code=403, detail="Not a member of this group")

    expense = db.query(Expense).filter_by(id=expense_id, group_id=group_id).first()
    if expense:
        db.delete(expense)
        db.commit()

    return HTMLResponse("")
