from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator


def _coerce_float(v: Any) -> float | None:
    if v is None or v == '' or v == 'null':
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _coerce_int(v: Any) -> int | None:
    if v is None or v == '' or v == 'null':
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def _coerce_str(v: Any) -> str | None:
    if v is None or v == '' or v == 'null':
        return None
    return str(v)


CoerceFloat = Annotated[float | None, BeforeValidator(_coerce_float)]
CoerceInt = Annotated[int | None, BeforeValidator(_coerce_int)]
CoerceStr = Annotated[str | None, BeforeValidator(_coerce_str)]


class AnketaOut(BaseModel):
    id: int
    status: str
    full_name: str | None = None
    car_brand: str | None = None
    car_model: str | None = None
    car_specs: str | None = None
    car_year: int | None = None
    purchase_price: float | None = None
    down_payment_percent: float | None = None
    dti: float | None = None
    created_at: str | None = None
    creator_name: str | None = None

    class Config:
        from_attributes = True


class ConclusionRequest(BaseModel):
    decision: str          # approved|review|rejected_underwriter|rejected_client
    comment: str | None = None
    final_pv: float | None = None


class DeleteAnketaRequest(BaseModel):
    reason: str


class AnketaDetail(BaseModel):
    id: int
    status: str
    consent_personal_data: bool = False
    client_type: str = "individual"
    # Personal
    full_name: str | None = None
    birth_date: str | None = None
    passport_series: str | None = None
    passport_issue_date: str | None = None
    passport_issued_by: str | None = None
    pinfl: str | None = None
    registration_address: str | None = None
    registration_landmark: str | None = None
    actual_address: str | None = None
    actual_landmark: str | None = None
    phone_numbers: str | None = None
    relative_phones: str | None = None
    # Deal
    partner: str | None = None
    car_brand: str | None = None
    car_model: str | None = None
    car_specs: str | None = None
    car_year: int | None = None
    body_number: str | None = None
    engine_number: str | None = None
    mileage: int | None = None
    purchase_price: float | None = None
    down_payment_percent: float | None = None
    down_payment_amount: float | None = None
    remaining_amount: float | None = None
    lease_term_months: int | None = None
    interest_rate: float | None = None
    monthly_payment: float | None = None
    purchase_purpose: str | None = None
    # Income
    has_official_employment: str | None = None
    employer_name: str | None = None
    salary_period_months: float | None = None
    total_salary: float | None = None
    main_activity: str | None = None
    main_activity_period: float | None = None
    main_activity_income: float | None = None
    additional_income_source: str | None = None
    additional_income_period: float | None = None
    additional_income_total: float | None = None
    other_income_source: str | None = None
    other_income_period: float | None = None
    other_income_total: float | None = None
    total_monthly_income: float | None = None
    property_type: str | None = None
    property_details: str | None = None
    # Credit history
    has_current_obligations: str | None = None
    total_obligations_amount: float | None = None
    obligations_count: int | None = None
    monthly_obligations_payment: float | None = None
    dti: float | None = None
    closed_obligations_count: int | None = None
    max_overdue_principal_days: int | None = None
    max_overdue_principal_amount: float | None = None
    max_continuous_overdue_percent_days: int | None = None
    max_overdue_percent_amount: float | None = None
    overdue_category: str | None = None
    last_overdue_date: str | None = None
    overdue_check_result: str | None = None
    overdue_reason: str | None = None
    # --- Legal entity: Company info ---
    company_name: str | None = None
    company_inn: str | None = None
    company_oked: str | None = None
    company_legal_address: str | None = None
    company_actual_address: str | None = None
    company_phone: str | None = None
    director_full_name: str | None = None
    director_phone: str | None = None
    director_family_phone: str | None = None
    director_family_relation: str | None = None
    contact_person_name: str | None = None
    contact_person_role: str | None = None
    contact_person_phone: str | None = None
    # --- Legal entity: Company income ---
    company_revenue_period: float | None = None
    company_revenue_total: float | None = None
    company_net_profit: float | None = None
    director_income_period: float | None = None
    director_income_total: float | None = None
    # --- Legal entity: Company credit history ---
    company_has_obligations: str | None = None
    company_obligations_amount: float | None = None
    company_obligations_count: int | None = None
    company_monthly_payment: float | None = None
    company_overdue_category: str | None = None
    company_last_overdue_date: str | None = None
    company_overdue_reason: str | None = None
    # --- Legal entity: Director credit history ---
    director_has_obligations: str | None = None
    director_obligations_amount: float | None = None
    director_obligations_count: int | None = None
    director_monthly_payment: float | None = None
    director_overdue_category: str | None = None
    director_last_overdue_date: str | None = None
    director_overdue_reason: str | None = None
    # --- Guarantor ---
    guarantor_full_name: str | None = None
    guarantor_pinfl: str | None = None
    guarantor_passport: str | None = None
    guarantor_phone: str | None = None
    guarantor_monthly_income: float | None = None
    guarantor_overdue_category: str | None = None
    guarantor_last_overdue_date: str | None = None
    # Meta
    created_at: str | None = None
    updated_at: str | None = None
    created_by: int | None = None
    creator_name: str | None = None
    # Conclusion
    decision: str | None = None
    conclusion_comment: str | None = None
    concluded_by: int | None = None
    concluded_at: str | None = None
    concluder_name: str | None = None
    pinfl_hash: str | None = None
    # Auto-verdict
    auto_decision: str | None = None
    auto_decision_reasons: list | None = None
    recommended_pv: float | None = None
    risk_grade: str | None = None
    no_scoring_response: bool | None = None
    final_pv: float | None = None
    conclusion_version: int = 0
    # Soft delete
    deleted_at: str | None = None
    deletion_reason: str | None = None

    class Config:
        from_attributes = True


class AnketaUpdate(BaseModel):
    consent_personal_data: bool | None = None
    client_type: CoerceStr = None
    full_name: CoerceStr = None
    birth_date: CoerceStr = None
    passport_series: CoerceStr = None
    passport_issue_date: CoerceStr = None
    passport_issued_by: CoerceStr = None
    pinfl: CoerceStr = None
    registration_address: CoerceStr = None
    registration_landmark: CoerceStr = None
    actual_address: CoerceStr = None
    actual_landmark: CoerceStr = None
    phone_numbers: CoerceStr = None
    relative_phones: CoerceStr = None
    partner: CoerceStr = None
    car_brand: CoerceStr = None
    car_model: CoerceStr = None
    car_specs: CoerceStr = None
    car_year: CoerceInt = None
    body_number: CoerceStr = None
    engine_number: CoerceStr = None
    mileage: CoerceInt = None
    purchase_price: CoerceFloat = None
    down_payment_percent: CoerceFloat = None
    lease_term_months: CoerceInt = None
    interest_rate: CoerceFloat = None
    purchase_purpose: CoerceStr = None
    has_official_employment: CoerceStr = None
    employer_name: CoerceStr = None
    salary_period_months: CoerceFloat = None
    total_salary: CoerceFloat = None
    main_activity: CoerceStr = None
    main_activity_period: CoerceFloat = None
    main_activity_income: CoerceFloat = None
    additional_income_source: CoerceStr = None
    additional_income_period: CoerceFloat = None
    additional_income_total: CoerceFloat = None
    other_income_source: CoerceStr = None
    other_income_period: CoerceFloat = None
    other_income_total: CoerceFloat = None
    property_type: CoerceStr = None
    property_details: CoerceStr = None
    has_current_obligations: CoerceStr = None
    total_obligations_amount: CoerceFloat = None
    obligations_count: CoerceInt = None
    monthly_obligations_payment: CoerceFloat = None
    closed_obligations_count: CoerceInt = None
    max_overdue_principal_days: CoerceInt = None
    max_overdue_principal_amount: CoerceFloat = None
    max_continuous_overdue_percent_days: CoerceInt = None
    max_overdue_percent_amount: CoerceFloat = None
    overdue_category: CoerceStr = None
    last_overdue_date: CoerceStr = None
    overdue_reason: CoerceStr = None
    # --- Legal entity: Company info ---
    company_name: CoerceStr = None
    company_inn: CoerceStr = None
    company_oked: CoerceStr = None
    company_legal_address: CoerceStr = None
    company_actual_address: CoerceStr = None
    company_phone: CoerceStr = None
    director_full_name: CoerceStr = None
    director_phone: CoerceStr = None
    director_family_phone: CoerceStr = None
    director_family_relation: CoerceStr = None
    contact_person_name: CoerceStr = None
    contact_person_role: CoerceStr = None
    contact_person_phone: CoerceStr = None
    # --- Legal entity: Company income ---
    company_revenue_period: CoerceFloat = None
    company_revenue_total: CoerceFloat = None
    company_net_profit: CoerceFloat = None
    director_income_period: CoerceFloat = None
    director_income_total: CoerceFloat = None
    # --- Legal entity: Company credit history ---
    company_has_obligations: CoerceStr = None
    company_obligations_amount: CoerceFloat = None
    company_obligations_count: CoerceInt = None
    company_monthly_payment: CoerceFloat = None
    company_overdue_category: CoerceStr = None
    company_last_overdue_date: CoerceStr = None
    company_overdue_reason: CoerceStr = None
    # --- Legal entity: Director credit history ---
    director_has_obligations: CoerceStr = None
    director_obligations_amount: CoerceFloat = None
    director_obligations_count: CoerceInt = None
    director_monthly_payment: CoerceFloat = None
    director_overdue_category: CoerceStr = None
    director_last_overdue_date: CoerceStr = None
    director_overdue_reason: CoerceStr = None
    # --- Guarantor ---
    guarantor_full_name: CoerceStr = None
    guarantor_pinfl: CoerceStr = None
    guarantor_passport: CoerceStr = None
    guarantor_phone: CoerceStr = None
    guarantor_monthly_income: CoerceFloat = None
    guarantor_overdue_category: CoerceStr = None
    guarantor_last_overdue_date: CoerceStr = None
    # Risk grade
    risk_grade: CoerceStr = None
    no_scoring_response: bool | None = None


class EditRequestCreate(BaseModel):
    reason: str


class EditRequestOut(BaseModel):
    id: int
    anketa_id: int
    requester_name: str
    reason: str
    status: str
    reviewer_name: str | None = None
    review_comment: str | None = None
    created_at: str | None = None
    reviewed_at: str | None = None
    anketa_client_name: str | None = None
    anketa_status: str | None = None
