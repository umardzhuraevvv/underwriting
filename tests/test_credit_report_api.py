"""Тесты API эндпоинта парсинга кредитных историй."""

import os
from io import BytesIO

import pytest

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "credit_reports")


class TestCreditReportParse:
    """POST /api/v1/credit-report/parse"""

    def test_parse_individual_report(self, client, admin_headers, seeded_db):
        """Парсинг HTML физлица — возвращает корректные данные."""
        filepath = os.path.join(FIXTURES_DIR, "01_ru_individual_clean.html")
        with open(filepath, "rb") as f:
            resp = client.post(
                "/api/v1/credit-report/parse",
                files={"file": ("report.html", f, "text/html")},
                headers=admin_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "individual"
        assert data["ki_score"] == "B1 / 322"
        assert data["obligations_count"] == 2

    def test_parse_legal_entity_report(self, client, admin_headers, seeded_db):
        """Парсинг HTML юрлица — возвращает корректные данные."""
        filepath = os.path.join(FIXTURES_DIR, "02_uz_legal_entity.html")
        with open(filepath, "rb") as f:
            resp = client.post(
                "/api/v1/credit-report/parse",
                files={"file": ("report.html", f, "text/html")},
                headers=admin_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["entity_type"] == "legal_entity"
        assert "company_name" in data

    def test_parse_no_obligations(self, client, admin_headers, seeded_db):
        """Парсинг отчёта без обязательств."""
        filepath = os.path.join(FIXTURES_DIR, "03_uz_no_obligations.html")
        with open(filepath, "rb") as f:
            resp = client.post(
                "/api/v1/credit-report/parse",
                files={"file": ("report.html", f, "text/html")},
                headers=admin_headers,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_current_obligations"] == "нет"

    def test_parse_no_auth(self, client, seeded_db):
        """Без авторизации → 403."""
        resp = client.post(
            "/api/v1/credit-report/parse",
            files={"file": ("report.html", BytesIO(b"<html></html>"), "text/html")},
        )
        assert resp.status_code == 401

    def test_parse_empty_file(self, client, admin_headers, seeded_db):
        """Пустой файл → 422."""
        resp = client.post(
            "/api/v1/credit-report/parse",
            files={"file": ("empty.html", BytesIO(b""), "text/html")},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "пустой" in resp.json()["detail"].lower()

    def test_parse_oversize_file(self, client, admin_headers, seeded_db):
        """Файл > 5MB → 422."""
        big = BytesIO(b"x" * (6 * 1024 * 1024))
        resp = client.post(
            "/api/v1/credit-report/parse",
            files={"file": ("huge.html", big, "text/html")},
            headers=admin_headers,
        )
        assert resp.status_code == 422
        assert "большой" in resp.json()["detail"].lower()

    def test_parse_inspector_can_use(self, client, inspector_headers, seeded_db):
        """Инспектор тоже может парсить."""
        filepath = os.path.join(FIXTURES_DIR, "01_ru_individual_clean.html")
        with open(filepath, "rb") as f:
            resp = client.post(
                "/api/v1/credit-report/parse",
                files={"file": ("report.html", f, "text/html")},
                headers=inspector_headers,
            )
        assert resp.status_code == 200

    def test_freshness_fields_present(self, client, admin_headers, seeded_db):
        """Ответ содержит is_fresh и freshness_warning."""
        filepath = os.path.join(FIXTURES_DIR, "01_ru_individual_clean.html")
        with open(filepath, "rb") as f:
            resp = client.post(
                "/api/v1/credit-report/parse",
                files={"file": ("report.html", f, "text/html")},
                headers=admin_headers,
            )
        data = resp.json()
        assert "is_fresh" in data
        assert "freshness_warning" in data
        # Fixture report_date is 2025-10-22, not today → not fresh
        assert data["is_fresh"] is False
        assert "не сегодняшняя" in data["freshness_warning"]

    def test_overdue_summary_in_response(self, client, admin_headers, seeded_db):
        """Ответ содержит overdue_summary."""
        filepath = os.path.join(FIXTURES_DIR, "06_ru_d2_class.html")
        with open(filepath, "rb") as f:
            resp = client.post(
                "/api/v1/credit-report/parse",
                files={"file": ("report.html", f, "text/html")},
                headers=admin_headers,
            )
        data = resp.json()
        assert "overdue_summary" in data
        assert "до 30 дней" in data["overdue_summary"]

    def test_credit_type_in_contracts(self, client, admin_headers, seeded_db):
        """contracts_detail содержит credit_type."""
        filepath = os.path.join(FIXTURES_DIR, "06_ru_d2_class.html")
        with open(filepath, "rb") as f:
            resp = client.post(
                "/api/v1/credit-report/parse",
                files={"file": ("report.html", f, "text/html")},
                headers=admin_headers,
            )
        data = resp.json()
        assert len(data["contracts_detail"]) > 0
        for c in data["contracts_detail"]:
            assert "credit_type" in c
