import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from slowapi.errors import RateLimitExceeded

from app.database import init_db
from app.limiter import limiter
from app.logging_config import setup_logging
from app.schemas import HealthResponse
from app.routers import auth, admin, anketa, credit_report
from app.routers.anketa import public_router as anketa_public_router

logger = logging.getLogger("app")


def _rate_limit_handler(request, exc):
    return JSONResponse(
        status_code=429,
        content={"detail": "Слишком много попыток входа. Попробуйте через минуту."},
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    try:
        init_db()
    except Exception:
        logger.exception("Ошибка инициализации БД")
    yield


app = FastAPI(title="Fintech Drive — Андеррайтинг", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_handler)


@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration_ms = round((time.time() - start) * 1000)

    # Extract user id from JWT if available
    user_info = ""
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        try:
            from jose import jwt as jose_jwt
            from app.auth import SECRET_KEY, ALGORITHM
            payload = jose_jwt.decode(auth_header.split(" ", 1)[1], SECRET_KEY, algorithms=[ALGORITHM])
            user_info = f" user_id={payload.get('sub', '?')}"
        except Exception:
            pass

    logger.info(
        "%s %s -> %s (%dms)%s",
        request.method, request.url.path, response.status_code, duration_ms, user_info
    )
    return response


app.include_router(auth.router)
app.include_router(admin.router)
app.include_router(anketa.router)
app.include_router(anketa_public_router)
app.include_router(credit_report.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/api/health", response_model=HealthResponse)
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
