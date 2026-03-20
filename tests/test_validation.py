"""Тесты валидации Pydantic-схем: невалидные данные → 422."""


class TestLoginValidation:

    def test_login_invalid_email(self, client, seeded_db):
        """Невалидный email при логине → 422."""
        resp = client.post("/api/v1/auth/login", json={"email": "not-an-email", "password": "Test123!"})
        assert resp.status_code == 422, f"Невалидный email → 422, получили {resp.status_code}"

    def test_login_empty_password(self, client, seeded_db):
        """Пустой пароль при логине → 422."""
        resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com", "password": ""})
        assert resp.status_code == 422, f"Пустой пароль → 422, получили {resp.status_code}"

    def test_login_missing_email(self, client, seeded_db):
        """Отсутствующий email при логине → 422."""
        resp = client.post("/api/v1/auth/login", json={"password": "Test123!"})
        assert resp.status_code == 422, f"Отсутствующий email → 422, получили {resp.status_code}"

    def test_login_missing_password(self, client, seeded_db):
        """Отсутствующий пароль при логине → 422."""
        resp = client.post("/api/v1/auth/login", json={"email": "admin@test.com"})
        assert resp.status_code == 422, f"Отсутствующий пароль → 422, получили {resp.status_code}"


class TestAnketaValidation:

    def test_create_anketa_empty_client_type(self, client, admin_headers, seeded_db):
        """Пустой client_type при создании — используется дефолт, не ошибка."""
        resp = client.post("/api/v1/anketas", headers=admin_headers)
        assert resp.status_code == 200, f"Дефолтный client_type → 200, получили {resp.status_code}"
        data = resp.json()
        assert data["status"] == "draft"

    def test_delete_anketa_empty_reason(self, client, admin_headers, seeded_db):
        """Пустая причина удаления → 400."""
        create_resp = client.post("/api/v1/anketas?client_type=individual", headers=admin_headers)
        anketa_id = create_resp.json()["id"]
        resp = client.request(
            "DELETE",
            f"/api/v1/anketas/{anketa_id}",
            json={"reason": "   "},
            headers=admin_headers,
        )
        assert resp.status_code == 400, f"Пустая причина → 400, получили {resp.status_code}"


class TestWebhookValidation:

    def test_create_webhook_invalid_url(self, client, admin_headers, seeded_db):
        """Невалидный URL вебхука → 422."""
        resp = client.post(
            "/api/v1/admin/webhooks",
            json={"name": "Test", "url": "not-a-url"},
            headers=admin_headers,
        )
        assert resp.status_code == 422, f"Невалидный URL → 422, получили {resp.status_code}"

    def test_create_webhook_empty_name(self, client, admin_headers, seeded_db):
        """Пустое имя вебхука → 422."""
        resp = client.post(
            "/api/v1/admin/webhooks",
            json={"name": "", "url": "https://example.com/hook"},
            headers=admin_headers,
        )
        assert resp.status_code == 422, f"Пустое имя → 422, получили {resp.status_code}"

    def test_create_webhook_valid(self, client, admin_headers, seeded_db):
        """Валидный вебхук → 200."""
        resp = client.post(
            "/api/v1/admin/webhooks",
            json={"name": "Test Hook", "url": "https://example.com/hook"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Валидный вебхук → 200, получили {resp.status_code}"
        data = resp.json()
        assert data["name"] == "Test Hook"
        assert data["url"] == "https://example.com/hook"

    def test_update_webhook_invalid_url(self, client, admin_headers, seeded_db):
        """Невалидный URL при обновлении вебхука → 422."""
        # Создаём валидный вебхук
        create_resp = client.post(
            "/api/v1/admin/webhooks",
            json={"name": "Test", "url": "https://example.com/hook"},
            headers=admin_headers,
        )
        webhook_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/v1/admin/webhooks/{webhook_id}",
            json={"url": "ftp://invalid"},
            headers=admin_headers,
        )
        assert resp.status_code == 422, f"Невалидный URL при обновлении → 422, получили {resp.status_code}"


class TestUserValidation:

    def test_create_user_invalid_email(self, client, admin_headers, seeded_db):
        """Невалидный email при создании пользователя → 422."""
        resp = client.post(
            "/api/v1/admin/users",
            json={"email": "not-email", "full_name": "Тест Тестов", "role_id": 1},
            headers=admin_headers,
        )
        assert resp.status_code == 422, f"Невалидный email → 422, получили {resp.status_code}"

    def test_create_user_short_name(self, client, admin_headers, seeded_db):
        """Слишком короткое имя при создании пользователя → 422."""
        resp = client.post(
            "/api/v1/admin/users",
            json={"email": "valid@test.com", "full_name": "A", "role_id": 1},
            headers=admin_headers,
        )
        assert resp.status_code == 422, f"Короткое имя → 422, получили {resp.status_code}"


class TestHealthEndpoint:

    def test_health(self, client, seeded_db):
        """Health endpoint возвращает {status: ok}."""
        resp = client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
