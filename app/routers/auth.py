from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db, User
from app.auth import verify_password, create_access_token, get_current_user, get_user_permissions

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: str
    is_active: bool
    role_name: str | None = None
    permissions: dict | None = None


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == body.email).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Неверный логин или пароль")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Аккаунт деактивирован")

    perms = get_user_permissions(user, db)
    role_name = user.position.name if user.position else ("Администратор" if user.role == "admin" else "Инспектор")

    token = create_access_token({"sub": user.id, "role": user.role})
    return TokenResponse(
        access_token=token,
        user={
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "role": user.role,
            "role_name": role_name,
            "permissions": perms,
        },
    )


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    perms = get_user_permissions(user, db)
    role_name = user.position.name if user.position else ("Администратор" if user.role == "admin" else "Инспектор")
    return UserResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        role_name=role_name,
        permissions=perms,
    )
