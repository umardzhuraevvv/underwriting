import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Float, Date, Text, ForeignKey, func, text
from sqlalchemy.orm import sessionmaker, declarative_base, relationship

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./underwriting.db")

# PostgreSQL on Railway may use "postgres://" — SQLAlchemy needs "postgresql://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

_is_sqlite = DATABASE_URL.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _is_sqlite else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class Role(Base):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    is_system = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    # 9 permission columns
    anketa_create = Column(Boolean, default=False, nullable=False)
    anketa_edit = Column(Boolean, default=False, nullable=False)
    anketa_view_all = Column(Boolean, default=False, nullable=False)
    anketa_conclude = Column(Boolean, default=False, nullable=False)
    anketa_delete = Column(Boolean, default=False, nullable=False)
    user_manage = Column(Boolean, default=False, nullable=False)
    analytics_view = Column(Boolean, default=False, nullable=False)
    export_excel = Column(Boolean, default=False, nullable=False)
    rules_manage = Column(Boolean, default=False, nullable=False)


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(150), unique=True, nullable=False, index=True)
    full_name = Column(String(150), nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False)  # admin | inspector (backward compat)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    role_id = Column(Integer, ForeignKey("roles.id"))
    telegram_chat_id = Column(String(50))

    position = relationship("Role", foreign_keys=[role_id])


class Anketa(Base):
    __tablename__ = "anketas"

    # Meta
    id = Column(Integer, primary_key=True, index=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    status = Column(String(30), default="draft", nullable=False)
    consent_personal_data = Column(Boolean, default=False)
    client_type = Column(String(20), default="individual")  # individual | legal_entity

    # Block 1: Personal info
    full_name = Column(String(300))
    birth_date = Column(Date)
    passport_series = Column(String(20))
    passport_issue_date = Column(Date)
    passport_issued_by = Column(String(200))
    pinfl = Column(String(14))
    registration_address = Column(Text)
    registration_landmark = Column(String(300))
    actual_address = Column(Text)
    actual_landmark = Column(String(300))
    phone_numbers = Column(Text)
    relative_phones = Column(Text)

    # Block 2: Deal conditions
    partner = Column(String(200))
    car_brand = Column(String(100))
    car_model = Column(String(100))
    car_specs = Column(String(200))
    car_year = Column(Integer)
    body_number = Column(String(100))       # legacy, removed from UI
    engine_number = Column(String(100))     # legacy, removed from UI
    mileage = Column(Integer)               # пробег (км)
    purchase_price = Column(Float)
    down_payment_percent = Column(Float)
    down_payment_amount = Column(Float)       # auto-calc
    remaining_amount = Column(Float)           # auto-calc
    lease_term_months = Column(Integer)
    interest_rate = Column(Float)
    monthly_payment = Column(Float)            # auto-calc
    purchase_purpose = Column(String(200))

    # Block 3: Income
    has_official_employment = Column(String(10))  # да/нет
    employer_name = Column(String(300))
    salary_period_months = Column(Float)
    total_salary = Column(Float)
    main_activity = Column(String(300))
    main_activity_period = Column(Float)
    main_activity_income = Column(Float)
    additional_income_source = Column(String(300))
    additional_income_period = Column(Float)
    additional_income_total = Column(Float)
    other_income_source = Column(String(300))
    other_income_period = Column(Float)
    other_income_total = Column(Float)
    total_monthly_income = Column(Float)       # auto-calc
    property_type = Column(String(200))
    property_details = Column(Text)

    # Block 4: Credit history
    has_current_obligations = Column(String(10))  # есть/нет
    total_obligations_amount = Column(Float)
    obligations_count = Column(Integer)
    monthly_obligations_payment = Column(Float)
    dti = Column(Float)                        # auto-calc
    closed_obligations_count = Column(Integer)
    max_overdue_principal_days = Column(Integer)
    max_overdue_principal_amount = Column(Float)
    max_continuous_overdue_percent_days = Column(Integer)
    max_overdue_percent_amount = Column(Float)
    overdue_category = Column(String(20))      # до 30 дней/31-60/61-90/90+
    last_overdue_date = Column(Date)
    overdue_check_result = Column(String(100)) # auto-calc
    overdue_reason = Column(Text)

    # ===== LEGAL ENTITY FIELDS =====
    # Company info
    company_name = Column(String(300))
    company_inn = Column(String(14))
    company_oked = Column(String(200))
    company_legal_address = Column(Text)
    company_actual_address = Column(Text)
    company_phone = Column(String(50))
    director_full_name = Column(String(300))       # Latin only
    director_phone = Column(String(50))
    director_family_phone = Column(String(50))     # family member phone
    director_family_relation = Column(String(50))  # кем приходится
    contact_person_name = Column(String(300))
    contact_person_role = Column(String(100))      # бухгалтер / зам. директора
    contact_person_phone = Column(String(50))

    # Company income
    company_revenue_period = Column(Float)         # period in months
    company_revenue_total = Column(Float)          # revenue for period
    company_net_profit = Column(Float)             # net profit for period
    director_income_period = Column(Float)         # period in months
    director_income_total = Column(Float)          # director income for period

    # Company credit history
    company_has_obligations = Column(String(10))
    company_obligations_amount = Column(Float)
    company_obligations_count = Column(Integer)
    company_monthly_payment = Column(Float)
    company_overdue_category = Column(String(20))
    company_last_overdue_date = Column(Date)
    company_overdue_reason = Column(Text)

    # Director credit history
    director_has_obligations = Column(String(10))
    director_obligations_amount = Column(Float)
    director_obligations_count = Column(Integer)
    director_monthly_payment = Column(Float)
    director_overdue_category = Column(String(20))
    director_last_overdue_date = Column(Date)
    director_overdue_reason = Column(Text)

    # Guarantor (legal entity only)
    guarantor_full_name = Column(String(300))      # Latin only
    guarantor_pinfl = Column(String(14))
    guarantor_passport = Column(String(20))
    guarantor_phone = Column(String(50))
    guarantor_monthly_income = Column(Float)
    guarantor_overdue_category = Column(String(20))
    guarantor_last_overdue_date = Column(Date)

    # Conclusion
    decision = Column(String(30))          # approved|review|rejected_underwriter|rejected_client
    conclusion_comment = Column(Text)
    concluded_by = Column(Integer, ForeignKey("users.id"))
    concluded_at = Column(DateTime)
    pinfl_hash = Column(String(64))        # SHA-256

    # Auto-verdict
    auto_decision = Column(String(30))           # approved | review | rejected
    auto_decision_reasons = Column(Text)         # JSON array of reasons
    recommended_pv = Column(Float)               # recommended down payment %
    risk_grade = Column(String(50))              # risk grade (E, E1, F2...)
    no_scoring_response = Column(Boolean, default=False)  # "Нет ответа от скоринга"
    final_pv = Column(Float)                     # final PV% from conclusion
    conclusion_version = Column(Integer, default=0)  # 1, 2, 3... incremented on each conclusion

    # Soft delete
    deleted_at = Column(DateTime)
    deleted_by = Column(Integer, ForeignKey("users.id"))
    deletion_reason = Column(Text)

    # Relationships
    creator = relationship("User", foreign_keys=[created_by], backref="anketas")
    concluder = relationship("User", foreign_keys=[concluded_by])
    deleter = relationship("User", foreign_keys=[deleted_by])


class AnketaHistory(Base):
    __tablename__ = "anketa_history"
    id = Column(Integer, primary_key=True, index=True)
    anketa_id = Column(Integer, ForeignKey("anketas.id"), nullable=False)
    field_name = Column(String(100), nullable=False)
    old_value = Column(Text)
    new_value = Column(Text)
    changed_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    changed_at = Column(DateTime, server_default=func.now())

    anketa = relationship("Anketa", backref="history")
    changer = relationship("User", foreign_keys=[changed_by])


class EditRequest(Base):
    __tablename__ = "edit_requests"
    id = Column(Integer, primary_key=True, index=True)
    anketa_id = Column(Integer, ForeignKey("anketas.id"), nullable=False)
    requested_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(String(20), default="pending", nullable=False)  # pending|approved|rejected
    reviewed_by = Column(Integer, ForeignKey("users.id"))
    review_comment = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    reviewed_at = Column(DateTime)

    anketa = relationship("Anketa", backref="edit_requests")
    requester = relationship("User", foreign_keys=[requested_by])
    reviewer = relationship("User", foreign_keys=[reviewed_by])


class Notification(Base):
    __tablename__ = "notifications"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    type = Column(String(50), nullable=False)
    title = Column(String(300), nullable=False)
    message = Column(Text)
    anketa_id = Column(Integer, ForeignKey("anketas.id"))
    is_read = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    user = relationship("User", foreign_keys=[user_id])
    anketa = relationship("Anketa", foreign_keys=[anketa_id])


class AnketaViewLog(Base):
    __tablename__ = "anketa_view_log"
    id = Column(Integer, primary_key=True, index=True)
    anketa_id = Column(Integer, ForeignKey("anketas.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    viewed_at = Column(DateTime, server_default=func.now())
    anketa = relationship("Anketa", foreign_keys=[anketa_id])
    viewer = relationship("User", foreign_keys=[user_id])


class RiskRule(Base):
    __tablename__ = "risk_rules"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), unique=True, nullable=False)  # E, E1, F, ...
    min_pv = Column(Float, nullable=False, default=20.0)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class UnderwritingRule(Base):
    __tablename__ = "underwriting_rules"
    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), nullable=False)    # dti | overdue | pv
    rule_key = Column(String(100), unique=True, nullable=False)
    value = Column(String(200), nullable=False)
    label = Column(String(200), nullable=False)
    value_type = Column(String(20), default="float") # float | int | string
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    from app.auth import hash_password

    Base.metadata.create_all(bind=engine)

    # Migration: add new columns if missing (idempotent)
    new_columns = [
        ("decision", "VARCHAR(30)"),
        ("conclusion_comment", "TEXT"),
        ("concluded_by", "INTEGER REFERENCES users(id)"),
        ("concluded_at", "TIMESTAMP"),
        ("pinfl_hash", "VARCHAR(64)"),
        ("deleted_at", "TIMESTAMP"),
        ("deleted_by", "INTEGER REFERENCES users(id)"),
        ("deletion_reason", "TEXT"),
        ("auto_decision", "VARCHAR(30)"),
        ("auto_decision_reasons", "TEXT"),
        ("recommended_pv", "FLOAT"),
        ("mileage", "INTEGER"),
        ("conclusion_version", "INTEGER DEFAULT 0"),
        ("client_type", "VARCHAR(20) DEFAULT 'individual'"),
        # Legal entity: company
        ("company_name", "VARCHAR(300)"),
        ("company_inn", "VARCHAR(14)"),
        ("company_oked", "VARCHAR(200)"),
        ("company_legal_address", "TEXT"),
        ("company_actual_address", "TEXT"),
        ("company_phone", "VARCHAR(50)"),
        ("director_full_name", "VARCHAR(300)"),
        ("director_phone", "VARCHAR(50)"),
        ("director_family_phone", "VARCHAR(50)"),
        ("director_family_relation", "VARCHAR(50)"),
        ("contact_person_name", "VARCHAR(300)"),
        ("contact_person_role", "VARCHAR(100)"),
        ("contact_person_phone", "VARCHAR(50)"),
        # Legal entity: company income
        ("company_revenue_period", "FLOAT"),
        ("company_revenue_total", "FLOAT"),
        ("company_net_profit", "FLOAT"),
        ("director_income_period", "FLOAT"),
        ("director_income_total", "FLOAT"),
        # Legal entity: company credit history
        ("company_has_obligations", "VARCHAR(10)"),
        ("company_obligations_amount", "FLOAT"),
        ("company_obligations_count", "INTEGER"),
        ("company_monthly_payment", "FLOAT"),
        ("company_overdue_category", "VARCHAR(20)"),
        ("company_last_overdue_date", "DATE"),
        ("company_overdue_reason", "TEXT"),
        # Legal entity: director credit history
        ("director_has_obligations", "VARCHAR(10)"),
        ("director_obligations_amount", "FLOAT"),
        ("director_obligations_count", "INTEGER"),
        ("director_monthly_payment", "FLOAT"),
        ("director_overdue_category", "VARCHAR(20)"),
        ("director_last_overdue_date", "DATE"),
        ("director_overdue_reason", "TEXT"),
        # Legal entity: guarantor
        ("guarantor_full_name", "VARCHAR(300)"),
        ("guarantor_pinfl", "VARCHAR(14)"),
        ("guarantor_passport", "VARCHAR(20)"),
        ("guarantor_phone", "VARCHAR(50)"),
        ("guarantor_monthly_income", "FLOAT"),
        ("guarantor_overdue_category", "VARCHAR(20)"),
        ("guarantor_last_overdue_date", "DATE"),
        # Risk grade & final PV
        ("risk_grade", "VARCHAR(50)"),
        ("no_scoring_response", "BOOLEAN DEFAULT FALSE"),
        ("final_pv", "FLOAT"),
    ]
    def _add_columns(table, columns):
        with engine.connect() as conn:
            for col_name, col_type in columns:
                try:
                    if _is_sqlite:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}"))
                    else:
                        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col_name} {col_type}"))
                    conn.commit()
                except Exception:
                    conn.rollback()

    _add_columns("anketas", new_columns)

    # Migration: users table new columns
    user_new_columns = [
        ("role_id", "INTEGER REFERENCES roles(id)"),
        ("telegram_chat_id", "VARCHAR(50)"),
    ]
    _add_columns("users", user_new_columns)

    db = SessionLocal()
    try:
        # Seed system roles
        admin_role = db.query(Role).filter(Role.name == "Администратор").first()
        if not admin_role:
            admin_role = Role(
                name="Администратор", is_system=True,
                anketa_create=True, anketa_edit=True, anketa_view_all=True,
                anketa_conclude=True, anketa_delete=True, user_manage=True,
                analytics_view=True, export_excel=True, rules_manage=True,
            )
            db.add(admin_role)
            db.flush()

        inspector_role = db.query(Role).filter(Role.name == "Инспектор").first()
        if not inspector_role:
            inspector_role = Role(
                name="Инспектор", is_system=True,
                anketa_create=True, anketa_edit=True, anketa_view_all=False,
                anketa_conclude=True, anketa_delete=False, user_manage=False,
                analytics_view=False, export_excel=False, rules_manage=False,
            )
            db.add(inspector_role)
            db.flush()

        db.commit()

        # Re-fetch after commit
        admin_role = db.query(Role).filter(Role.name == "Администратор").first()
        inspector_role = db.query(Role).filter(Role.name == "Инспектор").first()

        # Assign existing users to roles if not yet assigned
        users_no_role = db.query(User).filter(User.role_id.is_(None)).all()
        for u in users_no_role:
            if u.role == "admin":
                u.role_id = admin_role.id
            else:
                u.role_id = inspector_role.id
        if users_no_role:
            db.commit()

        existing = db.query(User).filter(User.email == "admin@fintechdrive.uz").first()
        if not existing:
            admin = User(
                email="admin@fintechdrive.uz",
                full_name="Администратор",
                password_hash=hash_password("Forever0109!"),
                role="admin",
                is_active=True,
                role_id=admin_role.id,
            )
            db.add(admin)
            db.commit()

        # Seed risk rules if table is empty
        if db.query(RiskRule).count() == 0:
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
                db.add(RiskRule(**r))
            db.commit()

        # Seed underwriting rules if table is empty
        if db.query(UnderwritingRule).count() == 0:
            default_rules = [
                # DTI
                {"category": "dti", "rule_key": "max_dti_approve", "value": "50", "label": "DTI: макс. для одобрения (%)", "value_type": "float"},
                {"category": "dti", "rule_key": "max_dti_review", "value": "60", "label": "DTI: макс. для рассмотрения (%)", "value_type": "float"},
                # PV
                {"category": "pv", "rule_key": "min_pv_percent", "value": "5", "label": "Минимальный ПВ (%)", "value_type": "float"},
                {"category": "pv", "rule_key": "pv_increase_step", "value": "5", "label": "Шаг увеличения ПВ при условиях (%)", "value_type": "float"},
                # Overdue
                {"category": "overdue", "rule_key": "overdue_30_result", "value": "approved", "label": "До 30 дней: решение", "value_type": "string"},
                {"category": "overdue", "rule_key": "overdue_31_60_lt_near_result", "value": "rejected", "label": "31-60, менее порога (ближн.): решение", "value_type": "string"},
                {"category": "overdue", "rule_key": "overdue_31_60_near_to_far_result", "value": "review", "label": "31-60, между порогами: решение", "value_type": "string"},
                {"category": "overdue", "rule_key": "overdue_31_60_near_to_far_pv_add", "value": "5", "label": "31-60, между порогами: ПВ +%", "value_type": "float"},
                {"category": "overdue", "rule_key": "overdue_31_60_gt_far_result", "value": "approved", "label": "31-60, более порога (дальн.): решение", "value_type": "string"},
                {"category": "overdue", "rule_key": "overdue_31_60_gt_far_pv_add", "value": "5", "label": "31-60, более порога (дальн.): ПВ +%", "value_type": "float"},
                {"category": "overdue", "rule_key": "overdue_31_60_threshold_near", "value": "6", "label": "31-60: ближний порог (мес)", "value_type": "int"},
                {"category": "overdue", "rule_key": "overdue_31_60_threshold_far", "value": "12", "label": "31-60: дальний порог (мес)", "value_type": "int"},
                {"category": "overdue", "rule_key": "overdue_61_90_gt_result", "value": "review", "label": "61-90, более порога: решение", "value_type": "string"},
                {"category": "overdue", "rule_key": "overdue_61_90_lte_result", "value": "rejected", "label": "61-90, до порога: решение", "value_type": "string"},
                {"category": "overdue", "rule_key": "overdue_61_90_threshold", "value": "12", "label": "61-90: порог (мес)", "value_type": "int"},
                {"category": "overdue", "rule_key": "overdue_90plus_gt_result", "value": "review", "label": "90+, более порога: решение", "value_type": "string"},
                {"category": "overdue", "rule_key": "overdue_90plus_lte_result", "value": "rejected", "label": "90+, до порога: решение", "value_type": "string"},
                {"category": "overdue", "rule_key": "overdue_90plus_threshold", "value": "24", "label": "90+: порог (мес)", "value_type": "int"},
            ]
            for r in default_rules:
                db.add(UnderwritingRule(**r))
            db.commit()
    finally:
        db.close()
