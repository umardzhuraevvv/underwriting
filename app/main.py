from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db
from app.routers import auth, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Fintech Drive — Андеррайтинг", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(admin.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/login")
def login_page():
    return FileResponse("app/static/pages/login.html")


@app.get("/")
def index_page():
    return FileResponse("app/static/pages/index.html")


@app.get("/admin")
def admin_page():
    return FileResponse("app/static/pages/index.html")


@app.get("/dashboard")
def dashboard_page():
    return FileResponse("app/static/pages/index.html")
