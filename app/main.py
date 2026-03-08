import asyncio
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from app.database import engine
from app.models import *  # noqa: registers all models with Base
from app.database import Base
from app.routes import auth, groups, expenses, settlements, analytics

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Splitsies", version="1.0.0")

# Fix HTTPS scheme behind Railway proxy
@app.middleware("http")
async def force_https_scheme(request: Request, call_next):
    if request.headers.get("x-forwarded-proto") == "https":
        request.scope["scheme"] = "https"
    return await call_next(request)

app.mount("/static", StaticFiles(directory="static"), name="static")

app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(expenses.router)
app.include_router(settlements.router)
app.include_router(analytics.router)


@app.get("/")
def root():
    return RedirectResponse(url="/groups")


@app.exception_handler(401)
def unauthorized(request: Request, exc):
    return RedirectResponse(url="/auth/login")
    