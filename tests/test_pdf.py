"""Тесты генерации PDF анкеты."""

import pytest
from app.database import Anketa
from app.auth import create_access_token


@pytest.fixture
def anketa_in_db(seeded_db):
    """Создаёт анкету в БД и возвращает её."""
    db = seeded_db["session"]
    anketa = Anketa(
        created_by=seeded_db["admin"].id,
        status="draft",
        client_type="individual",
        full_name="ТЕСТОВ ТЕСТ ТЕСТОВИЧ",
        phone_numbers="+998901234567",
        car_brand="Chevrolet",
        car_model="Malibu",
        car_year=2024,
        purchase_price=10_000_000,
        down_payment_percent=20,
        down_payment_amount=2_000_000,
        remaining_amount=8_000_000,
        lease_term_months=12,
        interest_rate=24,
        monthly_payment=755_000,
        total_monthly_income=2_000_000,
        monthly_obligations_payment=0,
        dti=37.75,
        auto_decision="approved",
        auto_decision_reasons='["DTI 37.75% ≤ 50% → одобрено"]',
    )
    db.add(anketa)
    db.commit()
    db.refresh(anketa)
    return anketa


def test_pdf_endpoint_returns_pdf(client, admin_headers, anketa_in_db):
    """GET /api/anketas/{id}/pdf → 200, content-type = application/pdf."""
    resp = client.get(f"/api/anketas/{anketa_in_db.id}/pdf", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.headers["content-disposition"] == f'attachment; filename="anketa_{anketa_in_db.id}.pdf"'
    # PDF начинается с %PDF
    assert resp.content[:5] == b"%PDF-"


def test_pdf_unauthorized(client, anketa_in_db):
    """Без токена → 401."""
    resp = client.get(f"/api/anketas/{anketa_in_db.id}/pdf")
    assert resp.status_code in (401, 403)


def test_pdf_not_found(client, admin_headers):
    """Несуществующий id → 404."""
    resp = client.get("/api/anketas/99999/pdf", headers=admin_headers)
    assert resp.status_code == 404


def test_pdf_access_denied_for_other_inspector(client, seeded_db, anketa_in_db):
    """Инспектор без anketa_view_all не может скачать чужую анкету."""
    inspector_token = create_access_token({"sub": seeded_db["inspector"].id})
    headers = {"Authorization": f"Bearer {inspector_token}"}
    resp = client.get(f"/api/anketas/{anketa_in_db.id}/pdf", headers=headers)
    assert resp.status_code == 403


def test_pdf_legal_entity(client, admin_headers, seeded_db):
    """PDF для юрлица генерируется без ошибок."""
    db = seeded_db["session"]
    anketa = Anketa(
        created_by=seeded_db["admin"].id,
        status="draft",
        client_type="legal_entity",
        company_name="ООО Тест",
        company_inn="123456789",
        director_full_name="ДИРЕКТОРОВ ДИРЕКТОР",
        purchase_price=50_000_000,
        down_payment_percent=30,
        lease_term_months=24,
        interest_rate=22,
    )
    db.add(anketa)
    db.commit()
    db.refresh(anketa)

    resp = client.get(f"/api/anketas/{anketa.id}/pdf", headers=admin_headers)
    assert resp.status_code == 200
    assert resp.content[:5] == b"%PDF-"
