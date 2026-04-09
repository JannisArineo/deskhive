from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse

from app.routers import auth, tickets, portal, users
from app.middleware.auth_middleware import get_current_user

BASE_DIR = Path(__file__).resolve().parent.parent

app = FastAPI(title="DeskHive", version="0.1.0")

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

# routers
app.include_router(auth.router)
app.include_router(tickets.router)
app.include_router(portal.router)
app.include_router(users.router)


# --- page routes ---

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})


@app.get("/tickets", response_class=HTMLResponse)
async def tickets_page(request: Request):
    return templates.TemplateResponse("tickets.html", {"request": request})


@app.get("/tickets/{ticket_id}", response_class=HTMLResponse)
async def ticket_detail_page(request: Request, ticket_id: str):
    return templates.TemplateResponse("ticket_detail.html", {"request": request, "ticket_id": ticket_id})


@app.get("/team", response_class=HTMLResponse)
async def team_page(request: Request):
    return templates.TemplateResponse("team.html", {"request": request})


@app.get("/invite/{token}", response_class=HTMLResponse)
async def invite_page(request: Request, token: str):
    return templates.TemplateResponse("invite.html", {"request": request, "token": token})


@app.get("/portal/{slug}", response_class=HTMLResponse)
async def portal_page(request: Request, slug: str):
    return templates.TemplateResponse("portal/submit.html", {"request": request, "slug": slug})


@app.get("/portal/{slug}/track", response_class=HTMLResponse)
async def portal_track_page(request: Request, slug: str):
    return templates.TemplateResponse("portal/track.html", {"request": request, "slug": slug})


@app.get("/health")
async def health():
    return {"status": "ok"}
