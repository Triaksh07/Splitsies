from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.group import GroupMember
from app.core.auth import get_current_user
from app.analytics import engine
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/groups/{group_id}/analytics", tags=["analytics"])
templates = Jinja2Templates(directory="templates")

def verify_membership(group_id: int, db: Session, current_user: User):
    if not db.query(GroupMember).filter_by(group_id=group_id, user_id=current_user.id).first():
        raise HTTPException(status_code=403, detail="Not a member of this group")

@router.get("/", response_class=HTMLResponse)
async def analytics_dashboard(
    group_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_membership(group_id, db, current_user)
    
    velocity = engine.spending_velocity(group_id, db)
    fairness = engine.fairness_score(group_id, db)
    spender = engine.top_spender(group_id, db)
    flags = engine.anomaly_flags(group_id, db)
    summary = engine.natural_language_summary(group_id, db)

    return templates.TemplateResponse(
        "analytics/dashboard.html",
        {
            "request": request,
            "group_id": group_id,
            "velocity": velocity,
            "fairness": fairness,
            "spender": spender,
            "flags": flags,
            "summary": summary,
            "user": current_user
        }
    )

@router.get("/charts/trend", response_class=HTMLResponse)
async def chart_trend(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_membership(group_id, db, current_user)
    return HTMLResponse(engine.monthly_spend_trend(group_id, db))

@router.get("/charts/categories", response_class=HTMLResponse)
async def chart_categories(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_membership(group_id, db, current_user)
    return HTMLResponse(engine.category_breakdown(group_id, db))

@router.get("/charts/contributions", response_class=HTMLResponse)
async def chart_contributions(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    verify_membership(group_id, db, current_user)
    return HTMLResponse(engine.per_person_contribution(group_id, db))
