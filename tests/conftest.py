"""Фикстуры для тестов: тестовая БД (SQLite in-memory), TestClient, юзеры, правила."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db, Role, User, UnderwritingRule, RiskRule
from app.auth import hash_password, create_access_token
from app.main import app
from app.limiter import limiter

# SQLite in-memory с StaticPool — гарантирует одно соединение для всех сессий
TEST_ENGINE = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=TEST_ENGINE)


@pytest.fixture(autouse=True)
def db_session():
    """Создаёт все таблицы, возвращает сессию, откатывает после теста."""
    Base.metadata.create_all(bind=TEST_ENGINE)
    limiter._storage.reset()
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=TEST_ENGINE)


@pytest.fixture
def client(db_session):
    """TestClient с переопределённой БД."""
    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _seed_roles(db_session) -> tuple[Role, Role]:
    """Создаёт роли Администратор и Инспектор."""
    admin_role = Role(
        name="Администратор", is_system=True,
        anketa_create=True, anketa_edit=True, anketa_view_all=True,
        anketa_conclude=True, anketa_delete=True, user_manage=True,
        analytics_view=True, export_excel=True, rules_manage=True,
    )
    inspector_role = Role(
        name="Инспектор", is_system=True,
        anketa_create=True, anketa_edit=True, anketa_view_all=False,
        anketa_conclude=True, anketa_delete=False, user_manage=False,
        analytics_view=False, export_excel=False, rules_manage=False,
    )
    db_session.add_all([admin_role, inspector_role])
    db_session.commit()
    db_session.refresh(admin_role)
    db_session.refresh(inspector_role)
    return admin_role, inspector_role


def _seed_users(db_session, admin_role, inspector_role) -> tuple[User, User]:
    """Создаёт админа и инспектора."""
    admin = User(
        email="admin@test.com",
        full_name="Тест Админ",
        password_hash=hash_password("Admin123!"),
        role="admin",
        is_active=True,
        is_superadmin=True,
        role_id=admin_role.id,
    )
    inspector = User(
        email="inspector@test.com",
        full_name="Тест Инспектор",
        password_hash=hash_password("Inspector123!"),
        role="inspector",
        is_active=True,
        is_superadmin=False,
        role_id=inspector_role.id,
    )
    db_session.add_all([admin, inspector])
    db_session.commit()
    db_session.refresh(admin)
    db_session.refresh(inspector)
    return admin, inspector


def _seed_rules(db_session):
    """Засеять дефолтные UnderwritingRule и RiskRule."""
    default_rules = [
        {"category": "dti", "rule_key": "max_dti_approve", "value": "50", "label": "DTI: макс. для одобрения (%)", "value_type": "float"},
        {"category": "dti", "rule_key": "max_dti_review", "value": "60", "label": "DTI: макс. для рассмотрения (%)", "value_type": "float"},
        {"category": "pv", "rule_key": "min_pv_percent", "value": "5", "label": "Минимальный ПВ (%)", "value_type": "float"},
        {"category": "pv", "rule_key": "pv_increase_step", "value": "5", "label": "Шаг увеличения ПВ (%)", "value_type": "float"},
        {"category": "overdue", "rule_key": "overdue_30_result", "value": "approved", "label": "До 30 дней: решение", "value_type": "string"},
        {"category": "overdue", "rule_key": "overdue_31_60_lt_near_result", "value": "rejected", "label": "31-60, < ближн.: решение", "value_type": "string"},
        {"category": "overdue", "rule_key": "overdue_31_60_near_to_far_result", "value": "review", "label": "31-60, между порогами: решение", "value_type": "string"},
        {"category": "overdue", "rule_key": "overdue_31_60_near_to_far_pv_add", "value": "5", "label": "31-60, между порогами: ПВ +%", "value_type": "float"},
        {"category": "overdue", "rule_key": "overdue_31_60_gt_far_result", "value": "approved", "label": "31-60, > дальн.: решение", "value_type": "string"},
        {"category": "overdue", "rule_key": "overdue_31_60_gt_far_pv_add", "value": "0", "label": "31-60, > дальн.: ПВ +%", "value_type": "float"},
        {"category": "overdue", "rule_key": "overdue_31_60_threshold_near", "value": "6", "label": "31-60: ближний порог (мес)", "value_type": "int"},
        {"category": "overdue", "rule_key": "overdue_31_60_threshold_far", "value": "12", "label": "31-60: дальний порог (мес)", "value_type": "int"},
        {"category": "overdue", "rule_key": "overdue_61_90_gt_result", "value": "approved", "label": "61-90, > порога: решение", "value_type": "string"},
        {"category": "overdue", "rule_key": "overdue_61_90_gt_pv_add", "value": "10", "label": "61-90, > порога: ПВ +%", "value_type": "float"},
        {"category": "overdue", "rule_key": "overdue_61_90_lte_result", "value": "rejected", "label": "61-90, ≤ порога: решение", "value_type": "string"},
        {"category": "overdue", "rule_key": "overdue_61_90_threshold", "value": "12", "label": "61-90: порог (мес)", "value_type": "int"},
        {"category": "overdue", "rule_key": "overdue_90plus_gt_result", "value": "review", "label": "90+, > порога: решение", "value_type": "string"},
        {"category": "overdue", "rule_key": "overdue_90plus_gt_pv_add", "value": "20", "label": "90+, > порога: ПВ +%", "value_type": "float"},
        {"category": "overdue", "rule_key": "overdue_90plus_lte_result", "value": "rejected", "label": "90+, ≤ порога: решение", "value_type": "string"},
        {"category": "overdue", "rule_key": "overdue_90plus_threshold", "value": "24", "label": "90+: порог (мес)", "value_type": "int"},
        # Credit report
        {"category": "credit_report", "rule_key": "systematic_overdue_result", "value": "rejected", "label": "Систематическая просрочка: решение", "value_type": "string"},
        {"category": "credit_report", "rule_key": "bad_classification_result", "value": "rejected", "label": "Плохой класс качества: решение", "value_type": "string"},
        {"category": "credit_report", "rule_key": "bad_classification_pv_add", "value": "10", "label": "Плохой класс качества: ПВ +%", "value_type": "float"},
        {"category": "credit_report", "rule_key": "warn_classification_result", "value": "review", "label": "Субстандартный класс: решение", "value_type": "string"},
        {"category": "credit_report", "rule_key": "warn_classification_pv_add", "value": "5", "label": "Субстандартный класс: ПВ +%", "value_type": "float"},
        {"category": "credit_report", "rule_key": "lombard_result", "value": "rejected", "label": "Ломбард: решение", "value_type": "string"},
        {"category": "credit_report", "rule_key": "lombard_pv_add", "value": "5", "label": "Ломбард: ПВ +%", "value_type": "float"},
        {"category": "credit_report", "rule_key": "closed_classification_result", "value": "rejected", "label": "Закрытые ниже Субстандартного: решение", "value_type": "string"},
        {"category": "credit_report", "rule_key": "scoring_class_de_result", "value": "rejected", "label": "Скоринговый класс D/E: решение", "value_type": "string"},
        {"category": "credit_report", "rule_key": "current_overdue_result", "value": "rejected", "label": "Текущая просрочка: решение", "value_type": "string"},
        {"category": "client", "rule_key": "min_age", "value": "21", "label": "Мин. возраст заёмщика", "value_type": "int"},
        {"category": "client", "rule_key": "max_age", "value": "65", "label": "Макс. возраст заёмщика", "value_type": "int"},
        {"category": "client", "rule_key": "open_apps_result", "value": "review", "label": "Открытые заявки за 10 дней: решение", "value_type": "string"},
    ]
    for r in default_rules:
        db_session.add(UnderwritingRule(**r))

    default_risk_rules = [
        {"category": "E", "min_pv": 20.0},
        {"category": "E1", "min_pv": 20.0},
        {"category": "E2", "min_pv": 20.0},
        {"category": "E3", "min_pv": 20.0},
        {"category": "E4", "min_pv": 20.0},
        {"category": "F", "min_pv": 20.0},
        {"category": "F1", "min_pv": 20.0},
        {"category": "F2", "min_pv": 20.0},
        {"category": "F3", "min_pv": 20.0},
        {"category": "F4", "min_pv": 20.0},
    ]
    for r in default_risk_rules:
        db_session.add(RiskRule(**r))

    db_session.commit()


@pytest.fixture
def seeded_db(db_session):
    """БД с ролями, юзерами и правилами."""
    admin_role, inspector_role = _seed_roles(db_session)
    admin, inspector = _seed_users(db_session, admin_role, inspector_role)
    _seed_rules(db_session)
    return {
        "session": db_session,
        "admin_role": admin_role,
        "inspector_role": inspector_role,
        "admin": admin,
        "inspector": inspector,
    }


@pytest.fixture
def admin_token(seeded_db):
    """JWT токен для админа."""
    return create_access_token({"sub": seeded_db["admin"].id})


@pytest.fixture
def inspector_token(seeded_db):
    """JWT токен для инспектора."""
    return create_access_token({"sub": seeded_db["inspector"].id})


@pytest.fixture
def admin_headers(admin_token):
    """Заголовки авторизации для админа."""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def inspector_headers(inspector_token):
    """Заголовки авторизации для инспектора."""
    return {"Authorization": f"Bearer {inspector_token}"}


@pytest.fixture
def default_rules():
    """Дефолтные правила андеррайтинга как dict (для unit-тестов вердикта)."""
    return {
        "max_dti_approve": 50.0,
        "max_dti_review": 60.0,
        "min_pv_percent": 5.0,
        "pv_increase_step": 5.0,
        "overdue_30_result": "approved",
        "overdue_31_60_lt_near_result": "rejected",
        "overdue_31_60_near_to_far_result": "review",
        "overdue_31_60_near_to_far_pv_add": 5.0,
        "overdue_31_60_gt_far_result": "approved",
        "overdue_31_60_gt_far_pv_add": 0.0,
        "overdue_31_60_threshold_near": 6,
        "overdue_31_60_threshold_far": 12,
        "overdue_61_90_gt_result": "approved",
        "overdue_61_90_gt_pv_add": 10.0,
        "overdue_61_90_lte_result": "rejected",
        "overdue_61_90_threshold": 12,
        "overdue_90plus_gt_result": "review",
        "overdue_90plus_gt_pv_add": 20.0,
        "overdue_90plus_lte_result": "rejected",
        "overdue_90plus_threshold": 24,
        # Credit report
        "systematic_overdue_result": "rejected",
        "bad_classification_result": "rejected",
        "bad_classification_pv_add": 10.0,
        "warn_classification_result": "review",
        "warn_classification_pv_add": 5.0,
        "lombard_result": "rejected",
        "lombard_pv_add": 5.0,
        "closed_classification_result": "rejected",
        "scoring_class_de_result": "rejected",
        "current_overdue_result": "rejected",
        "min_age": 21,
        "max_age": 65,
        "open_apps_result": "review",
    }


@pytest.fixture
def sample_anketa_data():
    """Валидные данные для создания анкеты (физлицо)."""
    return {
        "full_name": "ТЕСТОВ ТЕСТ ТЕСТОВИЧ",
        "birth_date": "2000-01-15",
        "phone_numbers": "+998901234567",
        "consent_personal_data": True,
        "car_brand": "Chevrolet",
        "car_model": "Malibu",
        "car_year": 2024,
        "purchase_price": 10_000_000,
        "down_payment_percent": 20,
        "lease_term_months": 12,
        "interest_rate": 24,
        "has_official_employment": "да",
        "employer_name": "ООО Тест",
        "salary_period_months": 6,
        "total_salary": 600_000,
        "has_current_obligations": "нет",
        "monthly_obligations_payment": 0,
        "overdue_category": "до 30 дней",
    }
