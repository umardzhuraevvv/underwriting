from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from app.database import get_db
from app.auth import require_admin, hash_password, get_current_user

router = APIRouter(prefix="/api/admin", tags=["admin"])


class CreateUserRequest(BaseModel):
    username: str
    password: str
    full_name: str
    role: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v not in ("admin", "inspector"):
            raise ValueError("Роль должна быть admin или inspector")
        return v

    @field_validator("username")
    @classmethod
    def validate_username(cls, v):
        if len(v) < 3:
            raise ValueError("Логин должен быть не менее 3 символов")
        return v

    @field_validator("password")
    @classmethod
    def validate_password(cls, v):
        if len(v) < 6:
            raise ValueError("Пароль должен быть не менее 6 символов")
        return v


class UpdateUserRequest(BaseModel):
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v):
        if v is not None and v not in ("admin", "inspector"):
            raise ValueError("Роль должна быть admin или inspector")
        return v


@router.get("/users")
def list_users(current_user: dict = Depends(require_admin), db=Depends(get_db)):
    rows = db.execute(
        "SELECT id, username, full_name, role, is_active, created_at FROM users ORDER BY id"
    ).fetchall()
    return [dict(r) for r in rows]


@router.post("/users")
def create_user(
    data: CreateUserRequest,
    current_user: dict = Depends(require_admin),
    db=Depends(get_db),
):
    existing = db.execute(
        "SELECT id FROM users WHERE username = ?", (data.username,)
    ).fetchone()
    if existing:
        raise HTTPException(status_code=400, detail="Пользователь с таким логином уже существует")

    pw_hash = hash_password(data.password)
    cursor = db.execute(
        "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
        (data.username, pw_hash, data.full_name, data.role),
    )
    db.commit()
    new_id = cursor.lastrowid

    user = db.execute(
        "SELECT id, username, full_name, role, is_active, created_at FROM users WHERE id = ?",
        (new_id,),
    ).fetchone()
    return dict(user)


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    data: UpdateUserRequest,
    current_user: dict = Depends(require_admin),
    db=Depends(get_db),
):
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if data.full_name is not None:
        db.execute("UPDATE users SET full_name = ? WHERE id = ?", (data.full_name, user_id))
    if data.role is not None:
        db.execute("UPDATE users SET role = ? WHERE id = ?", (data.role, user_id))
    if data.is_active is not None:
        db.execute("UPDATE users SET is_active = ? WHERE id = ?", (int(data.is_active), user_id))
    if data.password is not None and len(data.password) >= 6:
        pw_hash = hash_password(data.password)
        db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (pw_hash, user_id))

    db.commit()

    updated = db.execute(
        "SELECT id, username, full_name, role, is_active, created_at FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    return dict(updated)


@router.get("/stats")
def get_stats(current_user: dict = Depends(get_current_user), db=Depends(get_db)):
    return {
        "total_ankety": 0,
        "approved": 0,
        "pending": 0,
        "rejected": 0,
    }
