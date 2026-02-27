from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.group import Group, GroupMember
from app.models.participant import Participant
from app.models.expense import Expense
from app.core.auth import get_current_user
from app.core.balances import compute_balances, simplify_debts
from fastapi.templating import Jinja2Templates
from datetime import date

router = APIRouter(prefix="/groups", tags=["groups"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def list_groups(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    all_groups = [member.group for member in current_user.group_memberships]
    personal_group = next((g for g in all_groups if g.is_personal), None)
    regular_groups = [g for g in all_groups if not g.is_personal]
    return templates.TemplateResponse("groups/list.html", {
        "request": request,
        "groups": regular_groups,
        "personal_group": personal_group,
        "user": current_user
    })


@router.post("/")
async def create_group(
    request: Request,
    name: str = Form(...),
    description: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    new_group = Group(name=name, description=description, created_by=current_user.id)
    db.add(new_group)
    db.commit()
    db.refresh(new_group)

    member = GroupMember(group_id=new_group.id, user_id=current_user.id)
    participant = Participant(
        group_id=new_group.id,
        display_name=current_user.name,
        linked_user_id=current_user.id,
        is_guest=False
    )
    db.add(member)
    db.add(participant)
    db.commit()

    return RedirectResponse(url=f"/groups/{new_group.id}", status_code=303)


@router.get("/{group_id}", response_class=HTMLResponse)
async def group_detail(group_id: int, request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    member = db.query(GroupMember).filter(GroupMember.group_id == group_id, GroupMember.user_id == current_user.id).first()
    if not member:
        raise HTTPException(status_code=403, detail="Not a member of this group")

    group = db.get(Group, group_id)
    participants = db.query(Participant).filter(Participant.group_id == group_id).all()
    expenses = db.query(Expense).filter(Expense.group_id == group_id).order_by(Expense.date.desc()).limit(50).all()

    balances = compute_balances(group_id, db)
    debt_instructions = simplify_debts(balances)

    return templates.TemplateResponse(
        "groups/detail.html",
        {
            "request": request,
            "group": group,
            "participants": participants,
            "expenses": expenses,
            "balances": balances,
            "debt_instructions": debt_instructions,
            "today": date.today().isoformat(),
            "user": current_user
        }
    )


@router.post("/{group_id}/invite", response_class=HTMLResponse)
async def invite_member(
    group_id: int,
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    # Verify inviter is a member
    if not db.query(GroupMember).filter_by(group_id=group_id, user_id=current_user.id).first():
        return HTMLResponse('<div class="alert alert-error">You are not a member of this group.</div>')

    user_to_invite = db.query(User).filter(User.email == email).first()
    if not user_to_invite:
        return HTMLResponse('<div class="alert alert-error">User not found with that email.</div>')

    existing_member = db.query(GroupMember).filter_by(group_id=group_id, user_id=user_to_invite.id).first()
    if existing_member:
        return HTMLResponse('<div class="alert alert-warning">User is already in the group.</div>')

    new_member = GroupMember(group_id=group_id, user_id=user_to_invite.id)
    db.add(new_member)
    
    # Check if participant already exists (maybe they were a guest but this isn't handled strictly here, 
    # we just create a tied participant)
    existing_participant = db.query(Participant).filter_by(group_id=group_id, linked_user_id=user_to_invite.id).first()
    if not existing_participant:
       db.add(Participant(
            group_id=group_id,
            display_name=user_to_invite.name,
            linked_user_id=user_to_invite.id,
           is_guest=False
        ))

    db.commit()
    return HTMLResponse('<div class="alert alert-success">Successfully added member!</div>')
