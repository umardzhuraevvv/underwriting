from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.database import init_db
from app.routers import auth, admin

app = FastAPI(title="Fintech Drive — Андеррайтинг", version="1.0.0")

app.include_router(auth.router)
app.include_router(admin.router)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def startup():
    init_db()


@app.get("/")
def root():
    return FileResponse(os.path.join(STATIC_DIR, "pages", "login.html"))


@app.get("/login")
def login_page():
    return FileResponse(os.path.join(STATIC_DIR, "pages", "login.html"))


@app.get("/dashboard")
def dashboard_page():
    return FileResponse(os.path.join(STATIC_DIR, "pages", "index.html"))


@app.get("/admin")
def admin_page():
    return FileResponse(os.path.join(STATIC_DIR, "pages", "index.html"))
