from fastapi import APIRouter, Request, Depends, HTTPException, Form
from fastapi.responses import RedirectResponse, HTMLResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.group import Group, GroupMember
from app.models.participant import Participant
from app.core.auth import hash_password, verify_password, create_session_token, SESSION_COOKIE, SESSION_MAX_AGE
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/auth", tags=["auth"])
templates = Jinja2Templates(directory="templates")

@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("auth/login.html", {"request": request})

@router.post("/login")
async def login(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse("auth/login.html", {"request": request, "error": "Invalid email or password"})
    
    token = create_session_token(user.id)
    response = RedirectResponse(url="/groups", status_code=303)
    response.set_cookie(key=SESSION_COOKIE, value=token, httponly=True, samesite="lax", max_age=SESSION_MAX_AGE)
    return response

@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("auth/register.html", {"request": request})

@router.post("/register")
async def register(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    preferred_currency: str = Form("INR"),
    db: Session = Depends(get_db)
):
    if db.query(User).filter(User.email == email).first():
        return templates.TemplateResponse("auth/register.html", {"request": request, "error": "Email already registered"})
    
    new_user = User(
        name=name,
        email=email,
        password_hash=hash_password(password),
        preferred_currency=preferred_currency
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    personal_group = Group(
        name="Personal",
        description="Non-group expenses",
        created_by=new_user.id,
        is_personal=True,
    )
    db.add(personal_group)
    db.flush()
    db.add(GroupMember(group_id=personal_group.id, user_id=new_user.id))
    db.add(Participant(group_id=personal_group.id, display_name=new_user.name,
                       is_guest=False, linked_user_id=new_user.id))
    db.commit()

    token = create_session_token(new_user.id)
    response = RedirectResponse(url="/groups", status_code=303)
    response.set_cookie(key=SESSION_COOKIE, value=token, httponly=True, samesite="lax", max_age=SESSION_MAX_AGE)
    return response

@router.post("/logout")
async def logout():
    response = RedirectResponse(url="/auth/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response
