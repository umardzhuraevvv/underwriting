import hashlib
import json
import math
import os
import secrets
from datetime import date, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, BeforeValidator
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.database import get_db, Anketa, User, UnderwritingRule, AnketaHistory, RiskRule, EditRequest, Notification, AnketaViewLog
from app.auth import get_current_user, get_user_permissions


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

router = APIRouter(prefix="/api/anketas", tags=["anketas"])
public_router = APIRouter(prefix="/api/public", tags=["public"])


# ---------- Schemas ----------

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


# ---------- Helpers ----------

def calc_annuity(principal: float, annual_rate: float, months: int) -> float:
    """Calculate annuity monthly payment."""
    if not principal or not annual_rate or not months:
        return 0.0
    r = annual_rate / 100 / 12
    if r == 0:
        return principal / months
    return principal * (r * (1 + r) ** months) / ((1 + r) ** months - 1)


def calc_total_monthly_income(anketa: Anketa) -> float:
    """Sum of all income sources averaged per month."""
    # Legal entity income calculation
    if getattr(anketa, 'client_type', None) == "legal_entity":
        total = 0.0
        if anketa.company_revenue_total and anketa.company_revenue_period:
            total += anketa.company_revenue_total / anketa.company_revenue_period
        if anketa.director_income_total and anketa.director_income_period:
            total += anketa.director_income_total / anketa.director_income_period
        return round(total, 2)

    # Individual income calculation (existing logic)
    total = 0.0
    if anketa.total_salary and anketa.salary_period_months:
        total += anketa.total_salary / anketa.salary_period_months
    if anketa.main_activity_income and anketa.main_activity_period:
        total += anketa.main_activity_income / anketa.main_activity_period
    if anketa.additional_income_total and anketa.additional_income_period:
        total += anketa.additional_income_total / anketa.additional_income_period
    if anketa.other_income_total and anketa.other_income_period:
        total += anketa.other_income_total / anketa.other_income_period
    return round(total, 2)


def calc_overdue_check(category: str | None) -> str:
    """Auto check overdue category against matrix."""
    if not category:
        return "Нет данных"
    if category == "до 30 дней":
        return "ОК — допустимая просрочка"
    elif category == "31-60":
        return "Внимание — умеренная просрочка"
    elif category == "61-90":
        return "Риск — значительная просрочка"
    elif category == "90+":
        return "Отказ — критическая просрочка"
    return "Нет данных"


def _worst_overdue_category(*categories: str | None) -> str | None:
    """Return the worst (most severe) overdue category from a list."""
    order = {
        None: -1,
        "до 30 дней": 0,
        "31-60": 1,
        "61-90": 2,
        "90+": 3,
    }
    worst = None
    worst_rank = -1
    for cat in categories:
        rank = order.get(cat, -1)
        if rank > worst_rank:
            worst_rank = rank
            worst = cat
    return worst


def run_calculations(anketa: Anketa):
    """Run all auto-calculations on the anketa."""
    # Down payment
    if anketa.purchase_price and anketa.down_payment_percent:
        anketa.down_payment_amount = round(anketa.purchase_price * anketa.down_payment_percent / 100, 2)
        anketa.remaining_amount = round(anketa.purchase_price - anketa.down_payment_amount, 2)
    else:
        anketa.down_payment_amount = None
        anketa.remaining_amount = None

    # Monthly payment (annuity)
    if anketa.remaining_amount and anketa.interest_rate and anketa.lease_term_months:
        anketa.monthly_payment = round(
            calc_annuity(anketa.remaining_amount, anketa.interest_rate, anketa.lease_term_months), 2
        )
    else:
        anketa.monthly_payment = None

    # Total monthly income
    anketa.total_monthly_income = calc_total_monthly_income(anketa)

    # DTI
    payment = anketa.monthly_payment or 0
    obligations = anketa.monthly_obligations_payment or 0
    income = anketa.total_monthly_income or 0
    if income > 0:
        anketa.dti = round((payment + obligations) / income * 100, 2)
    else:
        anketa.dti = None

    # Overdue check (individual)
    anketa.overdue_check_result = calc_overdue_check(anketa.overdue_category)

    # For legal entities, compute combined worst overdue from company + director + guarantor
    if getattr(anketa, 'client_type', None) == "legal_entity":
        combined_worst = _worst_overdue_category(
            anketa.company_overdue_category,
            anketa.director_overdue_category,
            anketa.guarantor_overdue_category,
        )
        anketa.overdue_check_result = calc_overdue_check(combined_worst)


def load_rules(db: Session) -> dict:
    """Load all underwriting rules as {rule_key: parsed_value}."""
    rules_raw = db.query(UnderwritingRule).all()
    result = {}
    for r in rules_raw:
        if r.value_type == "float":
            result[r.rule_key] = float(r.value)
        elif r.value_type == "int":
            result[r.rule_key] = int(r.value)
        else:
            result[r.rule_key] = r.value
    return result


def _months_since(d: date | None) -> int | None:
    """Calculate months since a given date until today."""
    if not d:
        return None
    today = date.today()
    return (today.year - d.year) * 12 + (today.month - d.month)


def _worst_decision(a: str | None, b: str | None) -> str:
    """Return the worst (most restrictive) of two decisions."""
    order = {"approved": 0, "review": 1, "rejected": 2}
    va = order.get(a, -1)
    vb = order.get(b, -1)
    if va >= vb:
        return a
    return b


def _calc_overdue_decision_for_category(cat: str | None, overdue_date: date | None,
                                         rules: dict, reasons: list, prefix: str) -> tuple[str, float]:
    """Calculate overdue decision for a single overdue category. Returns (decision, pv_add)."""
    decision = "approved"
    pv_add = 0.0
    months = _months_since(overdue_date)

    if cat and cat != "до 30 дней":
        if cat == "31-60":
            near = rules.get("overdue_31_60_threshold_near", 6)
            far = rules.get("overdue_31_60_threshold_far", 12)
            if months is not None and months < near:
                decision = rules.get("overdue_31_60_lt_near_result", "rejected")
                reasons.append(f"{prefix}Просрочка 31-60, давность {months} мес < {near} мес — {decision}")
            elif months is not None and months <= far:
                decision = rules.get("overdue_31_60_near_to_far_result", "review")
                pv_add += rules.get("overdue_31_60_near_to_far_pv_add", 5)
                reasons.append(f"{prefix}Просрочка 31-60, давность {months} мес ({near}–{far}) — {decision}, ПВ +{rules.get('overdue_31_60_near_to_far_pv_add', 5)}%")
            else:
                decision = rules.get("overdue_31_60_gt_far_result", "approved")
                pv_add += rules.get("overdue_31_60_gt_far_pv_add", 5)
                m_str = f"{months} мес" if months is not None else "нет даты"
                reasons.append(f"{prefix}Просрочка 31-60, давность {m_str} > {far} мес — {decision}, ПВ +{rules.get('overdue_31_60_gt_far_pv_add', 5)}%")
        elif cat == "61-90":
            threshold = rules.get("overdue_61_90_threshold", 12)
            if months is not None and months > threshold:
                decision = rules.get("overdue_61_90_gt_result", "review")
                reasons.append(f"{prefix}Просрочка 61-90, давность {months} мес > {threshold} мес — {decision}")
            else:
                decision = rules.get("overdue_61_90_lte_result", "rejected")
                m_str = f"{months} мес" if months is not None else "нет даты"
                reasons.append(f"{prefix}Просрочка 61-90, давность {m_str} ≤ {threshold} мес — {decision}")
        elif cat == "90+":
            threshold = rules.get("overdue_90plus_threshold", 24)
            if months is not None and months > threshold:
                decision = rules.get("overdue_90plus_gt_result", "review")
                reasons.append(f"{prefix}Просрочка 90+, давность {months} мес > {threshold} мес — {decision}")
            else:
                decision = rules.get("overdue_90plus_lte_result", "rejected")
                m_str = f"{months} мес" if months is not None else "нет даты"
                reasons.append(f"{prefix}Просрочка 90+, давность {m_str} ≤ {threshold} мес — {decision}")
    elif cat == "до 30 дней":
        decision = rules.get("overdue_30_result", "approved")
        reasons.append(f"{prefix}Просрочка до 30 дней — {decision}")

    return decision, pv_add


def calc_auto_verdict(anketa: Anketa, rules: dict) -> dict:
    """Calculate automatic underwriting verdict based on rules."""
    reasons = []
    pv_add = 0.0

    # --- DTI check ---
    dti_decision = "approved"
    dti = anketa.dti
    max_approve = rules.get("max_dti_approve", 50)
    max_review = rules.get("max_dti_review", 60)

    if dti is not None:
        if dti <= max_approve:
            dti_decision = "approved"
            reasons.append(f"DTI {dti:.1f}% ≤ {max_approve}% — одобрено")
        elif dti <= max_review:
            dti_decision = "review"
            reasons.append(f"DTI {dti:.1f}% > {max_approve}%, ≤ {max_review}% — на рассмотрение")
        else:
            dti_decision = "rejected"
            reasons.append(f"DTI {dti:.1f}% > {max_review}% — отказ")
    else:
        reasons.append("DTI не рассчитан")

    # --- Overdue check ---
    is_legal = getattr(anketa, 'client_type', None) == "legal_entity"

    if is_legal:
        # For legal entities: check company, director, guarantor overdue separately
        # then take worst decision of all three
        overdue_decision = "approved"

        # Company overdue
        comp_decision, comp_pv = _calc_overdue_decision_for_category(
            anketa.company_overdue_category, anketa.company_last_overdue_date,
            rules, reasons, "[Компания] "
        )
        pv_add += comp_pv
        overdue_decision = _worst_decision(overdue_decision, comp_decision)

        # Director overdue
        dir_decision, dir_pv = _calc_overdue_decision_for_category(
            anketa.director_overdue_category, anketa.director_last_overdue_date,
            rules, reasons, "[Директор] "
        )
        pv_add += dir_pv
        overdue_decision = _worst_decision(overdue_decision, dir_decision)

        # Guarantor overdue
        guar_decision, guar_pv = _calc_overdue_decision_for_category(
            anketa.guarantor_overdue_category, anketa.guarantor_last_overdue_date,
            rules, reasons, "[Поручитель] "
        )
        pv_add += guar_pv
        overdue_decision = _worst_decision(overdue_decision, guar_decision)

    else:
        # Individual: existing logic
        overdue_decision = "approved"
        cat = anketa.overdue_category
        months = _months_since(anketa.last_overdue_date)

        if cat and cat != "до 30 дней":
            if cat == "31-60":
                near = rules.get("overdue_31_60_threshold_near", 6)
                far = rules.get("overdue_31_60_threshold_far", 12)
                if months is not None and months < near:
                    overdue_decision = rules.get("overdue_31_60_lt_near_result", "rejected")
                    reasons.append(f"Просрочка 31-60, давность {months} мес < {near} мес — {overdue_decision}")
                elif months is not None and months <= far:
                    overdue_decision = rules.get("overdue_31_60_near_to_far_result", "review")
                    pv_add += rules.get("overdue_31_60_near_to_far_pv_add", 5)
                    reasons.append(f"Просрочка 31-60, давность {months} мес ({near}–{far}) — {overdue_decision}, ПВ +{rules.get('overdue_31_60_near_to_far_pv_add', 5)}%")
                else:
                    overdue_decision = rules.get("overdue_31_60_gt_far_result", "approved")
                    pv_add += rules.get("overdue_31_60_gt_far_pv_add", 5)
                    m_str = f"{months} мес" if months is not None else "нет даты"
                    reasons.append(f"Просрочка 31-60, давность {m_str} > {far} мес — {overdue_decision}, ПВ +{rules.get('overdue_31_60_gt_far_pv_add', 5)}%")
            elif cat == "61-90":
                threshold = rules.get("overdue_61_90_threshold", 12)
                if months is not None and months > threshold:
                    overdue_decision = rules.get("overdue_61_90_gt_result", "review")
                    reasons.append(f"Просрочка 61-90, давность {months} мес > {threshold} мес — {overdue_decision}")
                else:
                    overdue_decision = rules.get("overdue_61_90_lte_result", "rejected")
                    m_str = f"{months} мес" if months is not None else "нет даты"
                    reasons.append(f"Просрочка 61-90, давность {m_str} ≤ {threshold} мес — {overdue_decision}")
            elif cat == "90+":
                threshold = rules.get("overdue_90plus_threshold", 24)
                if months is not None and months > threshold:
                    overdue_decision = rules.get("overdue_90plus_gt_result", "review")
                    reasons.append(f"Просрочка 90+, давность {months} мес > {threshold} мес — {overdue_decision}")
                else:
                    overdue_decision = rules.get("overdue_90plus_lte_result", "rejected")
                    m_str = f"{months} мес" if months is not None else "нет даты"
                    reasons.append(f"Просрочка 90+, давность {m_str} ≤ {threshold} мес — {overdue_decision}")
        elif cat == "до 30 дней":
            overdue_decision = rules.get("overdue_30_result", "approved")
            reasons.append(f"Просрочка до 30 дней — {overdue_decision}")

    # --- Final decision = worst of DTI and overdue ---
    final = _worst_decision(dti_decision, overdue_decision)

    # --- Recommended PV ---
    min_pv = rules.get("min_pv_percent", 5)
    current_pv = anketa.down_payment_percent or 0
    # Рекомендуемый ПВ = базовый минимум + добавки из правил (независимо от выбора клиента)
    recommended_pv = min_pv + pv_add
    if current_pv < recommended_pv:
        reasons.append(f"Текущий ПВ {current_pv:.0f}% ниже рекомендуемого {recommended_pv:.0f}%")

    return {
        "auto_decision": final,
        "auto_decision_reasons": reasons,
        "recommended_pv": round(recommended_pv, 1),
    }


def anketa_to_detail(a: Anketa, db: Session = None) -> dict:
    """Convert Anketa ORM object to detail dict."""
    result = {
        "id": a.id,
        "status": a.status,
        "consent_personal_data": a.consent_personal_data or False,
        "client_type": getattr(a, 'client_type', None) or "individual",
        "full_name": a.full_name,
        "birth_date": str(a.birth_date) if a.birth_date else None,
        "passport_series": a.passport_series,
        "passport_issue_date": str(a.passport_issue_date) if a.passport_issue_date else None,
        "passport_issued_by": a.passport_issued_by,
        "pinfl": a.pinfl,
        "registration_address": a.registration_address,
        "registration_landmark": a.registration_landmark,
        "actual_address": a.actual_address,
        "actual_landmark": a.actual_landmark,
        "phone_numbers": a.phone_numbers,
        "relative_phones": a.relative_phones,
        "partner": a.partner,
        "car_brand": a.car_brand,
        "car_model": a.car_model,
        "car_specs": a.car_specs,
        "car_year": a.car_year,
        "body_number": a.body_number,
        "engine_number": a.engine_number,
        "mileage": a.mileage,
        "purchase_price": a.purchase_price,
        "down_payment_percent": a.down_payment_percent,
        "down_payment_amount": a.down_payment_amount,
        "remaining_amount": a.remaining_amount,
        "lease_term_months": a.lease_term_months,
        "interest_rate": a.interest_rate,
        "monthly_payment": a.monthly_payment,
        "purchase_purpose": a.purchase_purpose,
        "has_official_employment": a.has_official_employment,
        "employer_name": a.employer_name,
        "salary_period_months": a.salary_period_months,
        "total_salary": a.total_salary,
        "main_activity": a.main_activity,
        "main_activity_period": a.main_activity_period,
        "main_activity_income": a.main_activity_income,
        "additional_income_source": a.additional_income_source,
        "additional_income_period": a.additional_income_period,
        "additional_income_total": a.additional_income_total,
        "other_income_source": a.other_income_source,
        "other_income_period": a.other_income_period,
        "other_income_total": a.other_income_total,
        "total_monthly_income": a.total_monthly_income,
        "property_type": a.property_type,
        "property_details": a.property_details,
        "has_current_obligations": a.has_current_obligations,
        "total_obligations_amount": a.total_obligations_amount,
        "obligations_count": a.obligations_count,
        "monthly_obligations_payment": a.monthly_obligations_payment,
        "dti": a.dti,
        "closed_obligations_count": a.closed_obligations_count,
        "max_overdue_principal_days": a.max_overdue_principal_days,
        "max_overdue_principal_amount": a.max_overdue_principal_amount,
        "max_continuous_overdue_percent_days": a.max_continuous_overdue_percent_days,
        "max_overdue_percent_amount": a.max_overdue_percent_amount,
        "overdue_category": a.overdue_category,
        "last_overdue_date": str(a.last_overdue_date) if a.last_overdue_date else None,
        "overdue_check_result": a.overdue_check_result,
        "overdue_reason": a.overdue_reason,
        # --- Legal entity: Company info ---
        "company_name": a.company_name,
        "company_inn": a.company_inn,
        "company_oked": a.company_oked,
        "company_legal_address": a.company_legal_address,
        "company_actual_address": a.company_actual_address,
        "company_phone": a.company_phone,
        "director_full_name": a.director_full_name,
        "director_phone": a.director_phone,
        "director_family_phone": a.director_family_phone,
        "director_family_relation": a.director_family_relation,
        "contact_person_name": a.contact_person_name,
        "contact_person_role": a.contact_person_role,
        "contact_person_phone": a.contact_person_phone,
        # --- Legal entity: Company income ---
        "company_revenue_period": a.company_revenue_period,
        "company_revenue_total": a.company_revenue_total,
        "company_net_profit": a.company_net_profit,
        "director_income_period": a.director_income_period,
        "director_income_total": a.director_income_total,
        # --- Legal entity: Company credit history ---
        "company_has_obligations": a.company_has_obligations,
        "company_obligations_amount": a.company_obligations_amount,
        "company_obligations_count": a.company_obligations_count,
        "company_monthly_payment": a.company_monthly_payment,
        "company_overdue_category": a.company_overdue_category,
        "company_last_overdue_date": str(a.company_last_overdue_date) if a.company_last_overdue_date else None,
        "company_overdue_reason": a.company_overdue_reason,
        # --- Legal entity: Director credit history ---
        "director_has_obligations": a.director_has_obligations,
        "director_obligations_amount": a.director_obligations_amount,
        "director_obligations_count": a.director_obligations_count,
        "director_monthly_payment": a.director_monthly_payment,
        "director_overdue_category": a.director_overdue_category,
        "director_last_overdue_date": str(a.director_last_overdue_date) if a.director_last_overdue_date else None,
        "director_overdue_reason": a.director_overdue_reason,
        # --- Guarantor ---
        "guarantor_full_name": a.guarantor_full_name,
        "guarantor_pinfl": a.guarantor_pinfl,
        "guarantor_passport": a.guarantor_passport,
        "guarantor_phone": a.guarantor_phone,
        "guarantor_monthly_income": a.guarantor_monthly_income,
        "guarantor_overdue_category": a.guarantor_overdue_category,
        "guarantor_last_overdue_date": str(a.guarantor_last_overdue_date) if a.guarantor_last_overdue_date else None,
        # Meta
        "created_at": str(a.created_at) if a.created_at else None,
        "updated_at": str(a.updated_at) if a.updated_at else None,
        "created_by": a.created_by,
        "creator_name": a.creator.full_name if a.creator else None,
        "decision": a.decision,
        "conclusion_comment": a.conclusion_comment,
        "concluded_by": a.concluded_by,
        "concluded_at": str(a.concluded_at) if a.concluded_at else None,
        "concluder_name": a.concluder.full_name if a.concluder else None,
        "pinfl_hash": a.pinfl_hash,
        "auto_decision": a.auto_decision,
        "auto_decision_reasons": json.loads(a.auto_decision_reasons) if a.auto_decision_reasons else [],
        "recommended_pv": a.recommended_pv,
        "risk_grade": a.risk_grade,
        "no_scoring_response": a.no_scoring_response or False,
        "final_pv": a.final_pv,
        "conclusion_version": a.conclusion_version or 0,
        "deleted_at": str(a.deleted_at) if a.deleted_at else None,
        "deletion_reason": a.deletion_reason,
        "share_token": a.share_token,
    }
    result["has_pending_edit_request"] = False
    if db:
        result["has_pending_edit_request"] = db.query(EditRequest).filter(
            EditRequest.anketa_id == a.id, EditRequest.status == "pending"
        ).first() is not None
    result["duplicates"] = find_duplicates(db, a) if db else []
    return result


def record_history(db: Session, anketa_id: int, user_id: int,
                   field_name: str, old_value, new_value):
    """Record a change in anketa_history."""
    entry = AnketaHistory(
        anketa_id=anketa_id,
        field_name=field_name,
        old_value=str(old_value) if old_value is not None else None,
        new_value=str(new_value) if new_value is not None else None,
        changed_by=user_id,
    )
    db.add(entry)


def create_notification(db: Session, user_id: int, ntype: str, title: str, message: str, anketa_id: int | None = None):
    db.add(Notification(user_id=user_id, type=ntype, title=title, message=message, anketa_id=anketa_id))


def _normalize_phone(raw: str) -> str:
    """Strip everything except digits from a phone string."""
    return "".join(c for c in raw if c.isdigit())


def find_duplicates(db: Session, anketa: Anketa) -> list[dict]:
    # Collect match fields per anketa id
    matches: dict[int, dict] = {}  # anketa_id -> {"obj": Anketa, "fields": [str]}

    def _add(m, match_field):
        if m.id == anketa.id:
            return
        if m.id in matches:
            matches[m.id]["fields"].append(match_field)
        else:
            matches[m.id] = {"obj": m, "fields": [match_field]}

    # По ПИНФЛ
    if anketa.pinfl and len(anketa.pinfl) == 14:
        for m in db.query(Anketa).filter(Anketa.pinfl == anketa.pinfl, Anketa.id != anketa.id, Anketa.status != "deleted").all():
            _add(m, "ПИНФЛ")

    # По паспорту
    if anketa.passport_series and anketa.passport_series.strip():
        for m in db.query(Anketa).filter(Anketa.passport_series == anketa.passport_series.strip(), Anketa.id != anketa.id, Anketa.status != "deleted").all():
            _add(m, "Паспорт")

    # По номеру телефона
    if anketa.phone_numbers and anketa.phone_numbers.strip():
        phone_norm = _normalize_phone(anketa.phone_numbers)
        if len(phone_norm) >= 9:
            for m in db.query(Anketa).filter(Anketa.phone_numbers.isnot(None), Anketa.id != anketa.id, Anketa.status != "deleted").all():
                if m.phone_numbers and _normalize_phone(m.phone_numbers) == phone_norm:
                    _add(m, "Телефон")

    # По ИНН (юр. лица)
    if anketa.client_type == "legal_entity" and anketa.company_inn and anketa.company_inn.strip():
        for m in db.query(Anketa).filter(Anketa.company_inn == anketa.company_inn.strip(), Anketa.id != anketa.id, Anketa.status != "deleted").all():
            _add(m, "ИНН")

    return [
        {
            "id": info["obj"].id,
            "full_name": info["obj"].full_name or info["obj"].company_name or f"#{info['obj'].id}",
            "status": info["obj"].status,
            "match_field": ", ".join(info["fields"]),
            "created_at": str(info["obj"].created_at) if info["obj"].created_at else None,
        }
        for info in matches.values()
    ]


def check_anketa_access(anketa: Anketa, user: User, db: Session = None):
    """Проверяет, что пользователь — создатель или имеет право anketa_view_all."""
    if anketa.created_by == user.id:
        return
    if db:
        perms = get_user_permissions(user, db)
        if perms.get("anketa_view_all"):
            return
    elif user.role == "admin":
        return
    raise HTTPException(status_code=403, detail="Нет доступа к этой анкете")


# ---------- Edit Request Schemas ----------

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


# ---------- Endpoints ----------

@router.post("")
def create_anketa(
    client_type: str = Query("individual"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new draft anketa."""
    perms = get_user_permissions(user, db)
    if not perms.get("anketa_create"):
        raise HTTPException(status_code=403, detail="Нет права на создание анкет")
    anketa = Anketa(created_by=user.id, status="draft", client_type=client_type)
    db.add(anketa)
    db.commit()
    db.refresh(anketa)
    return {"id": anketa.id, "status": anketa.status}


@router.get("/verdict-rules")
def get_verdict_rules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return underwriting rules as {rule_key: value} for client-side preview."""
    return load_rules(db)


@router.get("/risk-rules")
def get_risk_rules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return active risk rules for client-side PV validation."""
    rules = db.query(RiskRule).filter(RiskRule.is_active == True).order_by(RiskRule.category).all()
    return [{"category": r.category, "min_pv": r.min_pv} for r in rules]


@router.get("/stats")
def get_stats(
    period: str = Query("month"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    client_type: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get anketa statistics for the dashboard funnel."""
    now = datetime.utcnow()
    if period == "week":
        start = now - timedelta(days=7)
        end = now
    elif period == "custom" and date_from and date_to:
        try:
            start = datetime.fromisoformat(date_from)
            end = datetime.fromisoformat(date_to) + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат даты")
    else:  # month
        start = now - timedelta(days=30)
        end = now

    perms = get_user_permissions(user, db)
    base = db.query(Anketa).filter(Anketa.created_at >= start, Anketa.created_at <= end)

    # Filter by permissions: users without anketa_view_all see only their own
    if not perms.get("anketa_view_all"):
        base = base.filter(Anketa.created_by == user.id)

    # Filter by client_type if provided
    if client_type:
        base = base.filter(Anketa.client_type == client_type)

    total = base.count()
    draft = base.filter(Anketa.status == "draft").count()
    saved = base.filter(Anketa.status == "saved").count()
    approved = base.filter(Anketa.status == "approved").count()
    review = base.filter(Anketa.status == "review").count()
    rejected_underwriter = base.filter(Anketa.status == "rejected_underwriter").count()
    rejected_client = base.filter(Anketa.status == "rejected_client").count()
    deleted = base.filter(Anketa.status == "deleted").count()

    return {
        "total": total,
        "draft": draft,
        "saved": saved,
        "approved": approved,
        "review": review,
        "rejected_underwriter": rejected_underwriter,
        "rejected_client": rejected_client,
        "deleted": deleted,
    }


@router.get("")
def list_anketas(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all anketas with summary info (excluding deleted)."""
    perms = get_user_permissions(user, db)
    query = db.query(Anketa).filter(Anketa.status != "deleted")
    if not perms.get("anketa_view_all"):
        query = query.filter(Anketa.created_by == user.id)
    anketas = query.order_by(Anketa.id.desc()).all()
    result = []
    for a in anketas:
        result.append({
            "id": a.id,
            "status": a.status,
            "client_type": getattr(a, 'client_type', None) or "individual",
            "full_name": a.full_name,
            "company_name": a.company_name,
            "car_brand": a.car_brand,
            "car_model": a.car_model,
            "car_specs": a.car_specs,
            "car_year": a.car_year,
            "purchase_price": a.purchase_price,
            "down_payment_percent": a.down_payment_percent,
            "dti": a.dti,
            "decision": a.decision,
            "created_by": a.created_by,
            "created_at": str(a.created_at) if a.created_at else None,
            "creator_name": a.creator.full_name if a.creator else None,
        })
    return result


# ---------- Notifications ----------

@router.get("/notifications/list")
def list_notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get latest notifications for the current user."""
    notifs = db.query(Notification).filter(
        Notification.user_id == user.id
    ).order_by(Notification.id.desc()).limit(50).all()
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "message": n.message,
            "anketa_id": n.anketa_id,
            "is_read": n.is_read,
            "created_at": str(n.created_at) if n.created_at else None,
        }
        for n in notifs
    ]


@router.get("/notifications/unread-count")
def unread_notification_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read == False
    ).count()
    return {"count": count}


@router.patch("/notifications/{notif_id}/read")
def mark_notification_read(
    notif_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.query(Notification).filter(Notification.id == notif_id, Notification.user_id == user.id).first()
    if not n:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    n.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/notifications/read-all")
def mark_all_notifications_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}


# ---------- Analytics ----------

@router.get("/analytics")
def get_analytics(
    period: str = Query("month"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    client_type: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Extended analytics: approval rate, avg DTI, trend, risk distribution."""
    now = datetime.utcnow()

    if period == "week":
        current_start = now - timedelta(days=7)
        current_end = now
        prev_start = current_start - timedelta(days=7)
        prev_end = current_start
        # Trend: 7 daily points
        trend_points = 7
        trend_delta = timedelta(days=1)
        trend_fmt = lambda d: d.strftime("%d.%m")
    elif period == "custom" and date_from and date_to:
        try:
            current_start = datetime.fromisoformat(date_from)
            current_end = datetime.fromisoformat(date_to) + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат даты")
        delta = current_end - current_start
        prev_start = current_start - delta
        prev_end = current_start
        trend_points = min(7, max(1, delta.days))
        trend_delta = timedelta(days=max(1, delta.days // trend_points))
        trend_fmt = lambda d: d.strftime("%d.%m")
    else:  # month
        current_start = now - timedelta(days=30)
        current_end = now
        prev_start = current_start - timedelta(days=30)
        prev_end = current_start
        # Trend: 4 weekly points
        trend_points = 4
        trend_delta = timedelta(days=7)
        trend_fmt = lambda d: d.strftime("%d.%m")

    perms_analytics = get_user_permissions(user, db)

    def build_base(start, end):
        q = db.query(Anketa).filter(Anketa.created_at >= start, Anketa.created_at <= end)
        if not perms_analytics.get("anketa_view_all"):
            q = q.filter(Anketa.created_by == user.id)
        if client_type:
            q = q.filter(Anketa.client_type == client_type)
        return q

    # Current period
    cur_base = build_base(current_start, current_end)
    current_total = cur_base.count()
    cur_approved = cur_base.filter(Anketa.status == "approved").count()
    cur_rejected = cur_base.filter(Anketa.status.in_(["rejected_underwriter", "rejected_client"])).count()
    cur_decided = cur_approved + cur_rejected
    approval_rate = round(cur_approved / cur_decided * 100, 1) if cur_decided > 0 else 0

    avg_dti_row = cur_base.filter(Anketa.status != "draft", Anketa.dti.isnot(None)).with_entities(
        sa_func.avg(Anketa.dti)
    ).scalar()
    avg_dti = round(float(avg_dti_row), 1) if avg_dti_row else 0

    # Previous period
    prev_base = build_base(prev_start, prev_end)
    prev_total = prev_base.count()
    prev_approved = prev_base.filter(Anketa.status == "approved").count()
    prev_rejected = prev_base.filter(Anketa.status.in_(["rejected_underwriter", "rejected_client"])).count()
    prev_decided = prev_approved + prev_rejected
    prev_approval_rate = round(prev_approved / prev_decided * 100, 1) if prev_decided > 0 else 0

    prev_avg_dti_row = prev_base.filter(Anketa.status != "draft", Anketa.dti.isnot(None)).with_entities(
        sa_func.avg(Anketa.dti)
    ).scalar()
    prev_avg_dti = round(float(prev_avg_dti_row), 1) if prev_avg_dti_row else 0

    # Risk distribution
    risk_rows = cur_base.filter(Anketa.risk_grade.isnot(None)).with_entities(
        Anketa.risk_grade, sa_func.count()
    ).group_by(Anketa.risk_grade).all()
    risk_distribution = {row[0]: row[1] for row in risk_rows}

    # Trend
    trend = []
    for i in range(trend_points):
        t_start = current_start + trend_delta * i
        t_end = t_start + trend_delta
        t_base = build_base(t_start, t_end)
        t_total = t_base.count()
        t_approved = t_base.filter(Anketa.status == "approved").count()
        trend.append({
            "label": trend_fmt(t_start),
            "total": t_total,
            "approved": t_approved,
        })

    return {
        "current_total": current_total,
        "prev_total": prev_total,
        "approval_rate": approval_rate,
        "prev_approval_rate": prev_approval_rate,
        "avg_dti": avg_dti,
        "prev_avg_dti": prev_avg_dti,
        "risk_distribution": risk_distribution,
        "trend": trend,
    }


@router.get("/edit-requests")
def list_edit_requests(
    status: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List edit requests. Users with anketa_view_all see all; others see their own."""
    er_perms = get_user_permissions(user, db)
    query = db.query(EditRequest)
    if not er_perms.get("anketa_view_all"):
        query = query.filter(EditRequest.requested_by == user.id)
    if status:
        query = query.filter(EditRequest.status == status)
    requests = query.order_by(EditRequest.id.desc()).all()

    result = []
    for r in requests:
        anketa = db.query(Anketa).filter(Anketa.id == r.anketa_id).first()
        is_legal = anketa and (getattr(anketa, 'client_type', None) == 'legal_entity')
        client_name = None
        if anketa:
            client_name = anketa.company_name if is_legal else anketa.full_name
        result.append(EditRequestOut(
            id=r.id,
            anketa_id=r.anketa_id,
            requester_name=r.requester.full_name if r.requester else "—",
            reason=r.reason,
            status=r.status,
            reviewer_name=r.reviewer.full_name if r.reviewer else None,
            review_comment=r.review_comment,
            created_at=str(r.created_at) if r.created_at else None,
            reviewed_at=str(r.reviewed_at) if r.reviewed_at else None,
            anketa_client_name=client_name,
            anketa_status=anketa.status if anketa else None,
        ))
    return result


@router.get("/{anketa_id}")
def get_anketa(
    anketa_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full anketa details."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    check_anketa_access(anketa, user, db)
    # Record view
    db.add(AnketaViewLog(anketa_id=anketa.id, user_id=user.id))
    db.commit()
    return anketa_to_detail(anketa, db)


@router.patch("/{anketa_id}")
def update_anketa(
    anketa_id: int,
    data: AnketaUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update anketa fields (only if draft)."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    check_anketa_access(anketa, user, db)
    # Permission check: only creator or users with anketa_edit can edit
    if anketa.created_by != user.id:
        perms = get_user_permissions(user, db)
        if not perms.get("anketa_edit"):
            raise HTTPException(status_code=403, detail="Нет права на редактирование анкет")
    if anketa.status != "draft":
        raise HTTPException(status_code=400, detail="Редактировать можно только черновики")

    update_data = data.model_dump(exclude_unset=True)

    # Convert date strings to date objects
    date_fields = [
        "birth_date", "passport_issue_date", "last_overdue_date",
        "company_last_overdue_date", "director_last_overdue_date", "guarantor_last_overdue_date",
    ]
    for field in date_fields:
        if field in update_data and update_data[field]:
            try:
                update_data[field] = date.fromisoformat(update_data[field])
            except (ValueError, TypeError):
                update_data[field] = None

    # Normalize passport fields (strip spaces from formatted input like "AC 1234567")
    for pf in ("passport_series", "guarantor_passport"):
        if pf in update_data and update_data[pf]:
            update_data[pf] = update_data[pf].replace(" ", "")

    for key, value in update_data.items():
        old_value = getattr(anketa, key, None)
        old_str = str(old_value) if old_value is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            record_history(db, anketa.id, user.id, key, old_value, value)
        setattr(anketa, key, value)

    # Run auto-calculations
    run_calculations(anketa)

    db.commit()
    db.refresh(anketa)
    return anketa_to_detail(anketa, db)


@router.post("/{anketa_id}/save")
def save_anketa(
    anketa_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Finalize anketa: validate, recalculate, set status to saved."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    check_anketa_access(anketa, user, db)
    if anketa.status != "draft":
        raise HTTPException(status_code=400, detail="Сохранить можно только черновики")

    is_legal = getattr(anketa, 'client_type', None) == "legal_entity"

    # Validate required fields
    errors = []
    if not anketa.consent_personal_data:
        errors.append("Необходимо согласие на обработку персональных данных")

    if is_legal:
        # Legal entity required fields
        if not anketa.company_name:
            errors.append("Наименование компании обязательно")
        if not anketa.company_inn:
            errors.append("ИНН компании обязателен")
        if not anketa.director_full_name:
            errors.append("ФИО директора обязательно")
        if not anketa.purchase_price:
            errors.append("Стоимость обязательна")
        if not anketa.down_payment_percent:
            errors.append("Процент ПВ обязателен")
        if not anketa.lease_term_months:
            errors.append("Срок аренды обязателен")

        # Validate company INN (14 digits)
        if anketa.company_inn and (len(anketa.company_inn) != 14 or not anketa.company_inn.isdigit()):
            errors.append("ИНН компании должен содержать ровно 14 цифр")

    else:
        # Individual required fields (existing logic)
        if not anketa.full_name:
            errors.append("ФИО обязательно")
        if not anketa.birth_date:
            errors.append("Дата рождения обязательна")
        if not anketa.passport_series:
            errors.append("Серия паспорта обязательна")
        if not anketa.purchase_price:
            errors.append("Стоимость обязательна")
        if not anketa.down_payment_percent:
            errors.append("Процент ПВ обязателен")
        if not anketa.lease_term_months:
            errors.append("Срок аренды обязателен")

        # Credit history — required section, but last_overdue_date is optional (clean history)
        if not anketa.has_current_obligations:
            errors.append("Укажите наличие обязательств (Кредитная история)")
        if not anketa.overdue_category:
            errors.append("Укажите категорию просрочки (Кредитная история)")

        # Validate relative phones (min 2 contacts)
        if anketa.relative_phones:
            try:
                rp = json.loads(anketa.relative_phones)
                filled = [p for p in rp if isinstance(p, dict) and p.get("phone", "").strip()]
                if len(filled) < 2:
                    errors.append("Укажите минимум 2 дополнительных контакта")
            except (json.JSONDecodeError, TypeError):
                # Legacy plain text — count comma-separated
                parts = [p.strip() for p in anketa.relative_phones.split(",") if p.strip()]
                if len(parts) < 2:
                    errors.append("Укажите минимум 2 дополнительных контакта")
        else:
            errors.append("Укажите минимум 2 дополнительных контакта")

        # Validate PINFL (14 digits)
        if anketa.pinfl and (len(anketa.pinfl) != 14 or not anketa.pinfl.isdigit()):
            errors.append("ПИНФЛ должен содержать ровно 14 цифр")

    # Validate PV against risk grade
    if anketa.risk_grade and not anketa.no_scoring_response:
        risk_rule = db.query(RiskRule).filter(
            sa_func.lower(RiskRule.category) == anketa.risk_grade.lower(),
            RiskRule.is_active == True
        ).first()
        if risk_rule and anketa.down_payment_percent is not None:
            if anketa.down_payment_percent < risk_rule.min_pv:
                errors.append(f"ПВ ({anketa.down_payment_percent}%) ниже минимума для грейда {anketa.risk_grade} ({risk_rule.min_pv}%)")

    if errors:
        raise HTTPException(status_code=422, detail=errors)

    # Run calculations
    run_calculations(anketa)

    # Auto-verdict
    rules = load_rules(db)
    verdict = calc_auto_verdict(anketa, rules)
    anketa.auto_decision = verdict["auto_decision"]
    anketa.auto_decision_reasons = json.dumps(verdict["auto_decision_reasons"], ensure_ascii=False)
    anketa.recommended_pv = verdict["recommended_pv"]

    # If anketa was edited via approved edit request → set status to "review"
    has_approved_edit = db.query(EditRequest).filter(
        EditRequest.anketa_id == anketa.id,
        EditRequest.status == "approved",
    ).first()
    if has_approved_edit:
        anketa.status = "review"
        anketa.decision = None
        anketa.concluded_by = None
        anketa.concluded_at = None
        anketa.conclusion_comment = None
    else:
        anketa.status = "saved"

    # Check for duplicates and notify
    dupes = find_duplicates(db, anketa)
    if dupes:
        dupe_ids = ", ".join([f"#{d['id']}" for d in dupes])
        msg = f"Анкета #{anketa.id} имеет совпадения с: {dupe_ids}"
        create_notification(db, anketa.created_by, "duplicate_detected", "Обнаружены дубликаты", msg, anketa.id)
        # Notify all active admins
        admins = db.query(User).filter(User.role == "admin", User.is_active == True).all()
        for adm in admins:
            if adm.id != anketa.created_by:
                create_notification(db, adm.id, "duplicate_detected", "Обнаружены дубликаты", msg, anketa.id)

    # Telegram: notify admins about new saved anketa
    from app.telegram_service import notify_telegram_many
    admin_users = db.query(User).filter(User.role == "admin", User.is_active == True).all()
    admin_ids = [a.id for a in admin_users if a.id != user.id]
    client_name = anketa.full_name or anketa.company_name or f"#{anketa.id}"
    if admin_ids:
        notify_telegram_many(db, admin_ids, f"Новая анкета #{anketa.id} от {user.full_name}\nКлиент: {client_name}")

    db.commit()
    db.refresh(anketa)
    return anketa_to_detail(anketa, db)


@router.post("/{anketa_id}/conclude")
def conclude_anketa(
    anketa_id: int,
    data: ConclusionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set underwriter conclusion on a saved anketa. Supports re-conclusion."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    check_anketa_access(anketa, user, db)
    # Permission check: anketa_conclude required
    perms = get_user_permissions(user, db)
    if not perms.get("anketa_conclude"):
        raise HTTPException(status_code=403, detail="Нет права на вынесение заключения")

    # Allow conclusion for saved anketas and re-conclusion for already concluded
    allowed_statuses = {"saved", "approved", "review", "rejected_underwriter", "rejected_client"}
    if anketa.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Заключение можно дать только для сохранённой анкеты")

    valid_decisions = {"approved", "review", "rejected_underwriter", "rejected_client"}
    if data.decision not in valid_decisions:
        raise HTTPException(status_code=400, detail=f"Недопустимое решение. Допустимые: {', '.join(valid_decisions)}")

    # Validate final_pv (required)
    if data.final_pv is None:
        raise HTTPException(status_code=400, detail="Укажите итоговый ПВ%")

    anketa.final_pv = data.final_pv
    if anketa.risk_grade and not anketa.no_scoring_response:
        risk_rule = db.query(RiskRule).filter(
            sa_func.lower(RiskRule.category) == anketa.risk_grade.lower(),
            RiskRule.is_active == True
        ).first()
        if risk_rule and data.final_pv < risk_rule.min_pv:
            raise HTTPException(
                status_code=400,
                detail=f"Итоговый ПВ ({data.final_pv}%) ниже минимума для грейда {anketa.risk_grade} ({risk_rule.min_pv}%)"
            )

    is_reconclusion = anketa.decision is not None

    # Record history for re-conclusion
    if is_reconclusion:
        if anketa.decision != data.decision:
            record_history(db, anketa.id, user.id, "decision", anketa.decision, data.decision)
        if anketa.conclusion_comment != data.comment:
            record_history(db, anketa.id, user.id, "conclusion_comment",
                           anketa.conclusion_comment, data.comment)

    # Hash PINFL for dedup (keep raw PINFL in DB encrypted)
    if anketa.pinfl:
        salt = os.environ.get("PINFL_SALT", "fintechdrive_salt_2024")
        anketa.pinfl_hash = hashlib.sha256((salt + anketa.pinfl).encode()).hexdigest()

    # Increment conclusion version
    anketa.conclusion_version = (anketa.conclusion_version or 0) + 1

    # Set conclusion
    anketa.decision = data.decision
    anketa.conclusion_comment = data.comment
    anketa.concluded_by = user.id
    anketa.concluded_at = datetime.utcnow()
    anketa.status = data.decision

    # Notify creator about conclusion
    decision_labels = {
        "approved": "Одобрена",
        "review": "На рассмотрении",
        "rejected_underwriter": "Отказ андеррайтера",
        "rejected_client": "Отказ клиента",
    }
    label = decision_labels.get(data.decision, data.decision)
    if user.id != anketa.created_by:
        create_notification(
            db, anketa.created_by, "anketa_concluded",
            f"Анкета #{anketa.id}: {label}",
            f"По анкете #{anketa.id} вынесено решение: {label}." +
            (f" Комментарий: {data.comment}" if data.comment else ""),
            anketa.id,
        )

    # Generate share token for public access (QR code)
    if not anketa.share_token:
        anketa.share_token = secrets.token_urlsafe(32)

    # Telegram: notify creator about conclusion
    from app.telegram_service import notify_telegram
    notify_telegram(db, anketa.created_by,
        f"Анкета #{anketa.id}: {label}" +
        (f"\nКомментарий: {data.comment}" if data.comment else ""))

    db.commit()
    db.refresh(anketa)
    return anketa_to_detail(anketa, db)


@router.delete("/{anketa_id}")
def delete_anketa(
    anketa_id: int,
    data: DeleteAnketaRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete an anketa (only by creator or users with anketa_delete permission)."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    if anketa.created_by != user.id:
        perms = get_user_permissions(user, db)
        if not perms.get("anketa_delete"):
            raise HTTPException(status_code=403, detail="Нет права на удаление анкет")
    if anketa.status == "deleted":
        raise HTTPException(status_code=400, detail="Анкета уже удалена")
    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="Укажите причину удаления")

    old_status = anketa.status
    reason = data.reason.strip()

    # Record history
    record_history(db, anketa.id, user.id, "status", old_status, "deleted")
    record_history(db, anketa.id, user.id, "deletion_reason", None, reason)

    # Hash PINFL for dedup (keep data in DB)
    if anketa.pinfl:
        salt = os.environ.get("PINFL_SALT", "fintechdrive_salt_2024")
        anketa.pinfl_hash = hashlib.sha256((salt + anketa.pinfl).encode()).hexdigest()

    anketa.status = "deleted"
    anketa.deleted_at = datetime.utcnow()
    anketa.deleted_by = user.id
    anketa.deletion_reason = reason

    db.commit()
    return {"ok": True, "id": anketa.id}


# ---------- Edit Requests ----------

@router.post("/{anketa_id}/edit-request")
def create_edit_request(
    anketa_id: int,
    data: EditRequestCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a request to edit a saved/concluded anketa."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    check_anketa_access(anketa, user, db)

    if anketa.status in ("draft", "deleted"):
        raise HTTPException(status_code=400, detail="Запрос на правку не нужен для черновика или удалённой анкеты")

    # Check for existing pending request
    existing = db.query(EditRequest).filter(
        EditRequest.anketa_id == anketa_id,
        EditRequest.status == "pending",
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Уже есть ожидающий запрос на правку для этой анкеты")

    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="Укажите причину")

    req = EditRequest(
        anketa_id=anketa_id,
        requested_by=user.id,
        reason=data.reason.strip(),
    )
    db.add(req)

    # Notify all active admins
    admins = db.query(User).filter(User.role == "admin", User.is_active == True).all()
    for adm in admins:
        create_notification(
            db, adm.id, "edit_request_created",
            "Новый запрос на правку",
            f"{user.full_name} запросил правку анкеты #{anketa_id}. Причина: {data.reason.strip()}",
            anketa_id,
        )

    # Telegram: notify admins about edit request
    from app.telegram_service import notify_telegram_many
    admin_ids = [a.id for a in admins]
    if admin_ids:
        notify_telegram_many(db, admin_ids,
            f"Запрос на правку анкеты #{anketa_id}\nОт: {user.full_name}\nПричина: {data.reason.strip()}")

    db.commit()
    db.refresh(req)
    return {"ok": True, "id": req.id}


@router.get("/{anketa_id}/history")
def get_anketa_history(
    anketa_id: int,
    field: str | None = None,
    user_filter: int | None = Query(None, alias="user"),
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get change history for an anketa with optional filters."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    check_anketa_access(anketa, user, db)

    q = db.query(AnketaHistory).filter(AnketaHistory.anketa_id == anketa_id)

    if field:
        q = q.filter(AnketaHistory.field_name == field)
    if user_filter:
        q = q.filter(AnketaHistory.changed_by == user_filter)
    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            q = q.filter(AnketaHistory.changed_at >= dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to + "T23:59:59")
            q = q.filter(AnketaHistory.changed_at <= dt_to)
        except ValueError:
            pass
    if search:
        pattern = f"%{search}%"
        q = q.filter(
            (AnketaHistory.old_value.ilike(pattern)) | (AnketaHistory.new_value.ilike(pattern))
        )

    entries = q.order_by(AnketaHistory.id.desc()).all()

    return [
        {
            "id": e.id,
            "field_name": e.field_name,
            "old_value": e.old_value,
            "new_value": e.new_value,
            "changed_by_name": e.changer.full_name if e.changer else "—",
            "changed_by_id": e.changed_by,
            "changed_at": str(e.changed_at) if e.changed_at else None,
        }
        for e in entries
    ]


@router.get("/{anketa_id}/view-log")
def get_view_log(
    anketa_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get view log for an anketa."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    check_anketa_access(anketa, user, db)

    entries = db.query(AnketaViewLog).filter(
        AnketaViewLog.anketa_id == anketa_id
    ).order_by(AnketaViewLog.id.desc()).all()

    return [
        {
            "id": e.id,
            "user_name": e.viewer.full_name if e.viewer else "—",
            "viewed_at": str(e.viewed_at) if e.viewed_at else None,
        }
        for e in entries
    ]


# ---------- Employee Stats ----------

@router.get("/employee-stats/data")
def get_employee_stats(
    period: str = Query("month"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get per-employee stats: total, approved, rejected, review, approval_rate, avg_dti, avg_processing_hours."""
    perms = get_user_permissions(user, db)

    # Only users with analytics_view can access
    if not perms.get("analytics_view"):
        raise HTTPException(status_code=403, detail="Нет права: analytics_view")

    now = datetime.utcnow()
    if period == "week":
        start = now - timedelta(days=7)
        end = now
    elif period == "custom" and date_from and date_to:
        try:
            start = datetime.fromisoformat(date_from)
            end = datetime.fromisoformat(date_to) + timedelta(days=1)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат даты")
    else:
        start = now - timedelta(days=30)
        end = now

    base = db.query(Anketa).filter(
        Anketa.created_at >= start,
        Anketa.created_at <= end,
        Anketa.status != "deleted",
    )

    # If no anketa_view_all, only show own stats
    if not perms.get("anketa_view_all"):
        base = base.filter(Anketa.created_by == user.id)

    anketas = base.all()

    # Group by created_by
    by_user: dict[int, list] = {}
    for a in anketas:
        by_user.setdefault(a.created_by, []).append(a)

    # Load user names
    user_ids = list(by_user.keys())
    users_map = {}
    if user_ids:
        users_list = db.query(User).filter(User.id.in_(user_ids)).all()
        users_map = {u.id: u.full_name for u in users_list}

    result = []
    for uid, user_anketas in by_user.items():
        total = len(user_anketas)
        approved = sum(1 for a in user_anketas if a.status == "approved")
        rejected = sum(1 for a in user_anketas if a.status in ("rejected_underwriter", "rejected_client"))
        review = sum(1 for a in user_anketas if a.status == "review")
        decided = approved + rejected
        approval_rate = round(approved / decided * 100, 1) if decided > 0 else 0

        dtis = [a.dti for a in user_anketas if a.dti is not None and a.status != "draft"]
        avg_dti = round(sum(dtis) / len(dtis), 1) if dtis else 0

        # Avg processing hours: time from created_at to concluded_at
        processing_hours = []
        for a in user_anketas:
            if a.concluded_at and a.created_at:
                diff = (a.concluded_at - a.created_at).total_seconds() / 3600
                processing_hours.append(diff)
        avg_hours = round(sum(processing_hours) / len(processing_hours), 1) if processing_hours else 0

        result.append({
            "user_id": uid,
            "user_name": users_map.get(uid, f"User #{uid}"),
            "total": total,
            "approved": approved,
            "rejected": rejected,
            "review": review,
            "approval_rate": approval_rate,
            "avg_dti": avg_dti,
            "avg_processing_hours": avg_hours,
        })

    # Sort by total desc
    result.sort(key=lambda x: x["total"], reverse=True)
    return result


# ---------- Public API (no auth) ----------

@public_router.get("/anketa/{token}")
def get_public_anketa(token: str, db: Session = Depends(get_db)):
    """Return anketa data by share_token (no authentication required)."""
    anketa = db.query(Anketa).filter(
        Anketa.share_token == token,
        Anketa.status != "deleted",
    ).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    return anketa_to_detail(anketa, db)
