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
    paid_by_guest_name: str = Form(""),
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

    # Handle guest payer
    paid_by_guest_name = paid_by_guest_name.strip() if paid_by_guest_name else ""
    if paid_by_guest_name and (not paid_by_id or paid_by_id == 0):
        existing_guest = db.query(Participant).filter(
            Participant.group_id == group_id,
            Participant.display_name == paid_by_guest_name,
            Participant.is_guest == True,
        ).first()
        if existing_guest:
            paid_by_id = existing_guest.id
        else:
            new_guest = Participant(
                group_id=group_id,
                display_name=paid_by_guest_name,
                is_guest=True,
            )
            db.add(new_guest)
            db.flush()
            paid_by_id = new_guest.id

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
    
    participants = db.query(Participant).filter(Participant.group_id == group_id).all()

    return templates.TemplateResponse("groups/partials/expense_list.html", {
        "request": request,
        "expenses": expenses,
        "group_id": group_id,
        "participants": participants,
        "user": current_user,
    })

@router.get("/{expense_id}/edit", response_class=HTMLResponse)
async def edit_expense_form(
    group_id: int,
    expense_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from datetime import date
    if not db.query(GroupMember).filter_by(group_id=group_id, user_id=current_user.id).first():
        raise HTTPException(status_code=403, detail="Not a member of this group")
    expense = db.get(Expense, expense_id)
    if not expense or expense.group_id != group_id:
        raise HTTPException(status_code=404)
    participants = db.query(Participant).filter(
        Participant.group_id == group_id
    ).all()
    return templates.TemplateResponse(
        "groups/partials/edit_expense_form.html",
        {
            "request": request,
            "expense": expense,
            "participants": participants,
            "group_id": group_id,
            "user": current_user,
            "today": date.today().isoformat(),
        }
    )


@router.post("/{expense_id}/edit")
async def edit_expense(
    group_id: int,
    expense_id: int,
    request: Request,
    description: str = Form(...),
    amount: str = Form(...),
    currency: str = Form("INR"),
    paid_by_id: int = Form(...),
    split_type: str = Form("equal"),
    category: str = Form("other"),
    expense_date: str = Form(...),
    notes: str = Form(""),
    split_data: str = Form("{}"),
    participant_ids: str = Form(""),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not db.query(GroupMember).filter_by(group_id=group_id, user_id=current_user.id).first():
        raise HTTPException(status_code=403, detail="Not a member of this group")
    expense = db.get(Expense, expense_id)
    if not expense or expense.group_id != group_id:
        raise HTTPException(status_code=404)

    # Parse and recalculate
    p_ids = [int(x) for x in participant_ids.split(",") if x.strip()]
    amount_decimal = Decimal(amount)
    amount_inr = convert_to_inr(amount_decimal, currency, db)
    split_input = json.loads(split_data) if split_data else {}
    splits = calculate_splits(amount_inr, p_ids, split_type, split_input)

    # Update expense fields
    from datetime import date
    expense.description = description.strip()
    expense.amount = amount_decimal
    expense.currency = currency
    expense.amount_inr = amount_inr
    expense.paid_by_id = paid_by_id
    expense.split_type = split_type
    expense.category = category
    expense.date = date.fromisoformat(expense_date)
    expense.notes = notes.strip() or None

    # Delete old splits and create new ones
    for split in expense.splits:
        db.delete(split)
    db.flush()

    for participant_id, amount_owed in splits:
        db.add(ExpenseSplit(
            expense_id=expense.id,
            participant_id=participant_id,
            amount_owed_inr=amount_owed,
        ))

    db.commit()

    # Return updated expense list
    expenses = (
        db.query(Expense)
        .filter(Expense.group_id == group_id)
        .order_by(Expense.date.desc(), Expense.created_at.desc())
        .limit(50).all()
    )
    participants = db.query(Participant).filter(
        Participant.group_id == group_id
    ).all()
    from app.core.balances import compute_balances, simplify_debts
    from datetime import date as date_cls
    balances = compute_balances(group_id, db)
    debt_instructions = simplify_debts(balances)

    return templates.TemplateResponse(
        "groups/partials/expense_list.html",
        {
            "request": request,
            "group_id": group_id,
            "expenses": expenses,
            "participants": participants,
            "balances": balances,
            "debt_instructions": debt_instructions,
            "user": current_user,
            "today": date_cls.today().isoformat(),
        }
    )


@router.get("/{expense_id}/comments", response_class=HTMLResponse)
async def get_comments(
    group_id: int,
    expense_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not db.query(GroupMember).filter_by(group_id=group_id, user_id=current_user.id).first():
        raise HTTPException(status_code=403, detail="Not a member of this group")
    expense = db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "groups/partials/comments.html",
        {
            "request": request,
            "expense": expense,
            "group_id": group_id,
            "user": current_user,
        }
    )


@router.post("/{expense_id}/comments", response_class=HTMLResponse)
async def add_comment(
    group_id: int,
    expense_id: int,
    request: Request,
    content: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.models.comment import ExpenseComment
    if not db.query(GroupMember).filter_by(group_id=group_id, user_id=current_user.id).first():
        raise HTTPException(status_code=403, detail="Not a member of this group")
    expense = db.get(Expense, expense_id)
    if not expense:
        raise HTTPException(status_code=404)
    comment = ExpenseComment(
        expense_id=expense_id,
        user_id=current_user.id,
        content=content.strip(),
    )
    db.add(comment)
    db.commit()
    db.refresh(expense)
    return templates.TemplateResponse(
        "groups/partials/comments.html",
        {
            "request": request,
            "expense": expense,
            "group_id": group_id,
            "user": current_user,
        }
    )


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
