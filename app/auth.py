import os
import secrets
import string
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database import get_db, User, Role

SECRET_KEY = os.getenv("SECRET_KEY", "fintech-drive-underwriting-secret-2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480  # 8 hours

security = HTTPBearer()


def generate_password(length: int = 10) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        has_lower = any(c in string.ascii_lowercase for c in pwd)
        has_upper = any(c in string.ascii_uppercase for c in pwd)
        has_digit = any(c in string.digits for c in pwd)
        has_special = any(c in "!@#$%&*" for c in pwd)
        if has_lower and has_upper and has_digit and has_special:
            return pwd


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode["exp"] = expire
    if "sub" in to_encode:
        to_encode["sub"] = str(to_encode["sub"])
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        if user_id is None:
            raise HTTPException(status_code=401, detail="Недействительный токен")
    except JWTError:
        raise HTTPException(status_code=401, detail="Недействительный токен")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if user is None:
        raise HTTPException(status_code=401, detail="Пользователь не найден или деактивирован")
    return user


PERMISSION_KEYS = [
    "anketa_create", "anketa_edit", "anketa_view_all", "anketa_conclude",
    "anketa_delete", "user_manage", "analytics_view", "export_excel", "rules_manage",
]


def get_user_permissions(user: User, db: Session) -> dict:
    """Get permissions dict for user. Superadmin always gets all. Otherwise reads from Role."""
    if user.is_superadmin:
        return {k: True for k in PERMISSION_KEYS}

    if user.role_id:
        role = db.query(Role).filter(Role.id == user.role_id).first()
        if role:
            return {k: getattr(role, k, False) for k in PERMISSION_KEYS}

    # Fallback: admin gets all, inspector gets basic
    if user.role == "admin":
        return {k: True for k in PERMISSION_KEYS}
    return {
        "anketa_create": True, "anketa_edit": True, "anketa_view_all": False,
        "anketa_conclude": True, "anketa_delete": False, "user_manage": False,
        "analytics_view": False, "export_excel": False, "rules_manage": False,
    }


def require_permission(perm_name: str):
    """FastAPI dependency factory — checks a specific permission."""
    def dependency(
        credentials: HTTPAuthorizationCredentials = Depends(security),
        db: Session = Depends(get_db),
    ) -> User:
        token = credentials.credentials
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            user_id = int(payload.get("sub"))
            if user_id is None:
                raise HTTPException(status_code=401, detail="Недействительный токен")
        except JWTError:
            raise HTTPException(status_code=401, detail="Недействительный токен")

        user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
        if user is None:
            raise HTTPException(status_code=401, detail="Пользователь не найден или деактивирован")

        perms = get_user_permissions(user, db)
        if not perms.get(perm_name, False):
            raise HTTPException(status_code=403, detail=f"Нет права: {perm_name}")
        return user
    return dependency
