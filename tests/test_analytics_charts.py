"""Тесты эндпоинтов аналитики дашборда (ТЗ 011)."""

from datetime import datetime

from app.database import Anketa


def _create_anketa(db, user_id, status="approved", dti=45.0, price=5_000_000):
    """Хелпер: создать анкету с нужными полями."""
    a = Anketa(
        created_by=user_id,
        status=status,
        dti=dti,
        purchase_price=price,
        full_name="Тест Тестов",
    )
    db.add(a)
    db.commit()
    return a


class TestMonthlyTrend:

    def test_returns_200_and_list(self, client, admin_headers, seeded_db):
        resp = client.get("/api/v1/anketas/analytics/monthly-trend", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_contains_month_fields(self, client, admin_headers, seeded_db):
        db = seeded_db["session"]
        _create_anketa(db, seeded_db["admin"].id)

        resp = client.get("/api/v1/anketas/analytics/monthly-trend", headers=admin_headers)
        data = resp.json()
        assert len(data) >= 1
        item = data[0]
        assert "month" in item
        assert "total" in item
        assert "approved" in item
        assert "rejected" in item
        assert "review" in item

    def test_forbidden_without_analytics_view(self, client, inspector_headers, seeded_db):
        resp = client.get("/api/v1/anketas/analytics/monthly-trend", headers=inspector_headers)
        assert resp.status_code == 403


class TestDtiDistribution:

    def test_returns_200_and_list(self, client, admin_headers, seeded_db):
        resp = client.get("/api/v1/anketas/analytics/dti-distribution", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 4  # 4 диапазона

    def test_ranges_correct(self, client, admin_headers, seeded_db):
        db = seeded_db["session"]
        _create_anketa(db, seeded_db["admin"].id, status="saved", dti=25.0)
        _create_anketa(db, seeded_db["admin"].id, status="saved", dti=55.0)

        resp = client.get("/api/v1/anketas/analytics/dti-distribution", headers=admin_headers)
        data = resp.json()
        ranges = [d["range"] for d in data]
        assert ranges == ["0-30%", "30-50%", "50-60%", "60%+"]

    def test_forbidden_without_analytics_view(self, client, inspector_headers, seeded_db):
        resp = client.get("/api/v1/anketas/analytics/dti-distribution", headers=inspector_headers)
        assert resp.status_code == 403


class TestInspectorStats:

    def test_returns_200_and_list(self, client, admin_headers, seeded_db):
        resp = client.get("/api/v1/anketas/analytics/inspector-stats", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_contains_inspector_fields(self, client, admin_headers, seeded_db):
        db = seeded_db["session"]
        _create_anketa(db, seeded_db["admin"].id)

        resp = client.get("/api/v1/anketas/analytics/inspector-stats", headers=admin_headers)
        data = resp.json()
        assert len(data) >= 1
        item = data[0]
        assert "name" in item
        assert "total" in item
        assert "approved" in item
        assert "avg_dti" in item

    def test_forbidden_without_analytics_view(self, client, inspector_headers, seeded_db):
        resp = client.get("/api/v1/anketas/analytics/inspector-stats", headers=inspector_headers)
        assert resp.status_code == 403


class TestAmountTrend:

    def test_returns_200_and_list(self, client, admin_headers, seeded_db):
        resp = client.get("/api/v1/anketas/analytics/amount-trend", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_contains_amount_fields(self, client, admin_headers, seeded_db):
        db = seeded_db["session"]
        _create_anketa(db, seeded_db["admin"].id, price=10_000_000)

        resp = client.get("/api/v1/anketas/analytics/amount-trend", headers=admin_headers)
        data = resp.json()
        assert len(data) >= 1
        item = data[0]
        assert "month" in item
        assert "avg_amount" in item

    def test_forbidden_without_analytics_view(self, client, inspector_headers, seeded_db):
        resp = client.get("/api/v1/anketas/analytics/amount-trend", headers=inspector_headers)
        assert resp.status_code == 403
