"""Тесты API эндпоинтов: CRUD анкет, бизнес-флоу, публичный доступ."""


# ===== CRUD =====

class TestAnketaCRUD:

    def test_create_anketa(self, client, admin_headers, seeded_db):
        resp = client.post("/api/anketas?client_type=individual", headers=admin_headers)
        assert resp.status_code == 200, f"Создание анкеты → 200, получили {resp.status_code}"
        data = resp.json()
        assert "id" in data, "Ответ должен содержать id"
        assert data["status"] == "draft", f"Статус новой анкеты = draft, получили {data['status']}"

    def test_get_anketa(self, client, admin_headers, seeded_db):
        # Создаём анкету
        create_resp = client.post("/api/anketas?client_type=individual", headers=admin_headers)
        anketa_id = create_resp.json()["id"]

        resp = client.get(f"/api/anketas/{anketa_id}", headers=admin_headers)
        assert resp.status_code == 200, f"Получение анкеты → 200, получили {resp.status_code}"
        data = resp.json()
        assert data["id"] == anketa_id, f"ID должен совпадать: {anketa_id}"
        assert data["status"] == "draft", "Статус должен быть draft"

    def test_list_anketas(self, client, admin_headers, seeded_db):
        # Создаём анкету
        client.post("/api/anketas?client_type=individual", headers=admin_headers)

        resp = client.get("/api/anketas", headers=admin_headers)
        assert resp.status_code == 200, f"Список анкет → 200, получили {resp.status_code}"
        data = resp.json()
        assert isinstance(data, list), "Ответ должен быть списком"
        assert len(data) >= 1, "Список должен содержать хотя бы одну анкету"

    def test_update_anketa(self, client, admin_headers, sample_anketa_data, seeded_db):
        create_resp = client.post("/api/anketas?client_type=individual", headers=admin_headers)
        anketa_id = create_resp.json()["id"]

        resp = client.patch(
            f"/api/anketas/{anketa_id}",
            json={"full_name": "НОВОЕ ИМЯ ТЕСТОВИЧ", "purchase_price": 5_000_000},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Обновление анкеты → 200, получили {resp.status_code}"
        data = resp.json()
        assert data["full_name"] == "НОВОЕ ИМЯ ТЕСТОВИЧ", "ФИО должно обновиться"
        assert data["purchase_price"] == 5_000_000, "Цена должна обновиться"

    def test_delete_anketa(self, client, admin_headers, seeded_db):
        create_resp = client.post("/api/anketas?client_type=individual", headers=admin_headers)
        anketa_id = create_resp.json()["id"]

        resp = client.request(
            "DELETE",
            f"/api/anketas/{anketa_id}",
            json={"reason": "Тестовое удаление"},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Удаление анкеты → 200, получили {resp.status_code}"

        # Проверяем что анкета помечена удалённой
        get_resp = client.get(f"/api/anketas/{anketa_id}", headers=admin_headers)
        data = get_resp.json()
        assert data["status"] == "deleted", f"Статус после удаления = deleted, получили {data['status']}"
        assert data["deleted_at"] is not None, "deleted_at должен быть заполнен"


# ===== Бизнес-флоу =====

class TestAnketaBusinessFlow:

    def test_save_anketa(self, client, admin_headers, sample_anketa_data, seeded_db):
        # Создать и заполнить анкету
        create_resp = client.post("/api/anketas?client_type=individual", headers=admin_headers)
        anketa_id = create_resp.json()["id"]

        # Обновить все обязательные поля
        client.patch(f"/api/anketas/{anketa_id}", json=sample_anketa_data, headers=admin_headers)

        # Сохранить
        resp = client.post(f"/api/anketas/{anketa_id}/save", headers=admin_headers)
        assert resp.status_code == 200, f"Сохранение анкеты → 200, получили {resp.status_code}"
        data = resp.json()
        assert data["status"] == "saved", f"Статус после сохранения = saved, получили {data['status']}"
        assert data["monthly_payment"] is not None, "Ежемесячный платёж должен быть рассчитан"

    def test_conclude_anketa(self, client, admin_headers, sample_anketa_data, seeded_db):
        # Создать → заполнить → сохранить → заключить
        create_resp = client.post("/api/anketas?client_type=individual", headers=admin_headers)
        anketa_id = create_resp.json()["id"]
        client.patch(f"/api/anketas/{anketa_id}", json=sample_anketa_data, headers=admin_headers)
        client.post(f"/api/anketas/{anketa_id}/save", headers=admin_headers)

        resp = client.post(
            f"/api/anketas/{anketa_id}/conclude",
            json={"decision": "approved", "comment": "Одобрено тестом", "final_pv": 20},
            headers=admin_headers,
        )
        assert resp.status_code == 200, f"Заключение → 200, получили {resp.status_code}"
        data = resp.json()
        assert data["decision"] == "approved", f"Решение = approved, получили {data['decision']}"
        assert data["concluded_by"] is not None, "concluded_by должен быть заполнен"

    def test_conclude_without_permission(self, client, inspector_headers, admin_headers, sample_anketa_data, seeded_db):
        # Создаём анкету от админа, сохраняем
        create_resp = client.post("/api/anketas?client_type=individual", headers=admin_headers)
        anketa_id = create_resp.json()["id"]
        client.patch(f"/api/anketas/{anketa_id}", json=sample_anketa_data, headers=admin_headers)
        client.post(f"/api/anketas/{anketa_id}/save", headers=admin_headers)

        # Убираем право anketa_conclude у инспектора
        db = seeded_db["session"]
        inspector_role = seeded_db["inspector_role"]
        inspector_role.anketa_conclude = False
        db.commit()

        resp = client.post(
            f"/api/anketas/{anketa_id}/conclude",
            json={"decision": "approved", "comment": "Тест", "final_pv": 20},
            headers=inspector_headers,
        )
        assert resp.status_code == 403, f"Инспектор без anketa_conclude → 403, получили {resp.status_code}"


# ===== Публичный доступ =====

class TestPublicAccess:

    def test_public_anketa(self, client, admin_headers, sample_anketa_data, seeded_db):
        # Создать → заполнить → сохранить → заключить (для генерации share_token)
        create_resp = client.post("/api/anketas?client_type=individual", headers=admin_headers)
        anketa_id = create_resp.json()["id"]
        client.patch(f"/api/anketas/{anketa_id}", json=sample_anketa_data, headers=admin_headers)
        client.post(f"/api/anketas/{anketa_id}/save", headers=admin_headers)
        client.post(
            f"/api/anketas/{anketa_id}/conclude",
            json={"decision": "approved", "comment": "Тест", "final_pv": 20},
            headers=admin_headers,
        )

        # Получить share_token
        detail = client.get(f"/api/anketas/{anketa_id}", headers=admin_headers).json()
        token = detail["share_token"]
        assert token is not None, "share_token должен быть сгенерирован после заключения"

        # Получить анкету по публичной ссылке (без авторизации)
        resp = client.get(f"/api/public/anketa/{token}")
        assert resp.status_code == 200, f"Публичная анкета → 200, получили {resp.status_code}"

    def test_public_anketa_invalid_token(self, client, seeded_db):
        resp = client.get("/api/public/anketa/invalid_random_token_12345")
        assert resp.status_code == 404, f"Невалидный токен → 404, получили {resp.status_code}"
