from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db
from app.routers import auth, admin, anketa
from app.routers.anketa import public_router as anketa_public_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    import traceback
    try:
        init_db()
    except Exception as e:
        print(f"[INIT_DB ERROR] {e}")
        traceback.print_exc()
    yield


app = FastAPI(title="Fintech Drive — Андеррайтинг", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(anketa.router)
app.include_router(anketa_public_router)

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


@app.get("/anketa/{anketa_id}")
def anketa_page(anketa_id: int):
    return FileResponse("app/static/pages/index.html")


@app.get("/ankety")
def ankety_page():
    return FileResponse("app/static/pages/index.html")


@app.get("/new-anketa")
def new_anketa_page():
    return FileResponse("app/static/pages/index.html")


@app.get("/approvals")
def approvals_page():
    return FileResponse("app/static/pages/index.html")


@app.get("/admin/rules")
def rules_page():
    return FileResponse("app/static/pages/index.html")


@app.get("/admin/risk-rules")
def risk_rules_page():
    return FileResponse("app/static/pages/index.html")


@app.get("/calculator")
def calculator_page():
    return FileResponse("app/static/pages/index.html")


@app.get("/public/anketa/{token}")
def public_anketa_page(token: str):
    return FileResponse("app/static/pages/public-anketa.html")
