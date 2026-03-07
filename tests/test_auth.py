"""Тесты аутентификации: JWT, логин, пермишены, пароли."""

import string
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.auth import (
    create_access_token,
    hash_password,
    verify_password,
    generate_password,
    get_user_permissions,
    SECRET_KEY,
    ALGORITHM,
)


# ===== JWT =====

class TestJWT:

    def test_create_token(self):
        token = create_access_token({"sub": 42})
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        assert payload["sub"] == "42", f"sub должен быть '42', получили {payload['sub']}"
        assert "exp" in payload, "Токен должен содержать exp"

    def test_token_expired(self, client, seeded_db):
        expired_token = jwt.encode(
            {"sub": "1", "exp": datetime.now(timezone.utc) - timedelta(hours=1)},
            SECRET_KEY, algorithm=ALGORITHM,
        )
        resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {expired_token}"})
        assert resp.status_code == 401, f"Просроченный токен → 401, получили {resp.status_code}"

    def test_invalid_token(self, client, seeded_db):
        resp = client.get("/api/auth/me", headers={"Authorization": "Bearer invalid_random_string"})
        assert resp.status_code == 401, f"Невалидный токен → 401, получили {resp.status_code}"


# ===== Логин API =====

class TestLogin:

    def test_login_success(self, client, seeded_db):
        resp = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "Admin123!"})
        assert resp.status_code == 200, f"Успешный логин → 200, получили {resp.status_code}"
        data = resp.json()
        assert "access_token" in data, "Ответ должен содержать access_token"
        assert data["user"]["email"] == "admin@test.com", "Email в ответе должен совпадать"

    def test_login_wrong_password(self, client, seeded_db):
        resp = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "WrongPass!"})
        assert resp.status_code == 401, f"Неверный пароль → 401, получили {resp.status_code}"

    def test_login_nonexistent_user(self, client, seeded_db):
        resp = client.post("/api/auth/login", json={"email": "noone@test.com", "password": "Anything1!"})
        assert resp.status_code == 401, f"Несуществующий юзер → 401, получили {resp.status_code}"

    def test_login_inactive_user(self, client, seeded_db):
        db = seeded_db["session"]
        inspector = seeded_db["inspector"]
        inspector.is_active = False
        db.commit()
        resp = client.post("/api/auth/login", json={"email": "inspector@test.com", "password": "Inspector123!"})
        assert resp.status_code == 403, f"Деактивированный юзер → 403, получили {resp.status_code}"


# ===== Пермишены =====

class TestPermissions:

    def test_superadmin_all_permissions(self, seeded_db):
        db = seeded_db["session"]
        admin = seeded_db["admin"]
        perms = get_user_permissions(admin, db)
        for key, value in perms.items():
            assert value is True, f"Суперадмин: {key} должен быть True, получили {value}"
        assert len(perms) == 9, f"Должно быть 9 пермишенов, получили {len(perms)}"

    def test_inspector_limited_permissions(self, seeded_db):
        db = seeded_db["session"]
        inspector = seeded_db["inspector"]
        perms = get_user_permissions(inspector, db)
        assert perms["anketa_create"] is True, "Инспектор: anketa_create=True"
        assert perms["user_manage"] is False, "Инспектор: user_manage=False"
        assert perms["anketa_view_all"] is False, "Инспектор: anketa_view_all=False"

    def test_require_permission_denied(self, client, inspector_headers, seeded_db):
        resp = client.get("/api/admin/users", headers=inspector_headers)
        assert resp.status_code == 403, f"Инспектор → /api/admin/users → 403, получили {resp.status_code}"

    def test_require_permission_allowed(self, client, admin_headers, seeded_db):
        resp = client.get("/api/admin/users", headers=admin_headers)
        assert resp.status_code == 200, f"Админ → /api/admin/users → 200, получили {resp.status_code}"


# ===== Пароли =====

class TestPasswords:

    def test_hash_and_verify_password(self):
        hashed = hash_password("test123")
        assert verify_password("test123", hashed), "Верный пароль должен проходить верификацию"

    def test_verify_wrong_password(self):
        hashed = hash_password("test123")
        assert not verify_password("wrong", hashed), "Неверный пароль не должен проходить верификацию"

    def test_generate_password_strength(self):
        pwd = generate_password()
        has_lower = any(c in string.ascii_lowercase for c in pwd)
        has_upper = any(c in string.ascii_uppercase for c in pwd)
        has_digit = any(c in string.digits for c in pwd)
        has_special = any(c in "!@#$%&*" for c in pwd)
        assert has_lower, "Пароль должен содержать строчную букву"
        assert has_upper, "Пароль должен содержать заглавную букву"
        assert has_digit, "Пароль должен содержать цифру"
        assert has_special, "Пароль должен содержать спецсимвол"
