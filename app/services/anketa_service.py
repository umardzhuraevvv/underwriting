import hashlib
import json
import os
import secrets
from datetime import date, datetime

from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.database import Anketa, AnketaHistory, EditRequest, Notification, User, Role, RiskRule
from app.auth import get_user_permissions


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
    elif user.is_superadmin:
        return
    raise HTTPException(status_code=403, detail="Нет доступа к этой анкете")


def check_duplicate_field(db: Session, field: str, value: str, exclude_id: int | None) -> list[dict]:
    """Check for duplicates by a single field. Returns list of duplicate dicts."""
    allowed = {"phone_numbers", "company_inn"}
    if field not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid field: {field}")

    value = value.strip()
    if not value:
        return []

    base_q = db.query(Anketa).filter(Anketa.status != "deleted")
    if exclude_id:
        base_q = base_q.filter(Anketa.id != exclude_id)

    if field == "pinfl" and len(value) == 14:
        matches = base_q.filter(Anketa.pinfl == value).all()
    elif field == "passport_series":
        passport_norm = value.replace(" ", "")
        matches = []
        for m in base_q.filter(Anketa.passport_series.isnot(None)).all():
            if m.passport_series and m.passport_series.replace(" ", "") == passport_norm:
                matches.append(m)
    elif field == "phone_numbers":
        phone_norm = _normalize_phone(value)
        if len(phone_norm) < 9:
            return []
        matches = []
        for m in base_q.filter(Anketa.phone_numbers.isnot(None)).all():
            if m.phone_numbers and _normalize_phone(m.phone_numbers) == phone_norm:
                matches.append(m)
    elif field == "company_inn":
        matches = base_q.filter(Anketa.company_inn == value).all()
    else:
        matches = []

    field_labels = {
        "pinfl": "ПИНФЛ",
        "passport_series": "Паспорт",
        "phone_numbers": "Телефон",
        "company_inn": "ИНН",
    }

    return [
        {
            "id": m.id,
            "full_name": m.full_name or m.company_name or f"#{m.id}",
            "status": m.status,
            "decision": m.decision if hasattr(m, "decision") else None,
            "match_field": field_labels.get(field, field),
            "created_at": str(m.created_at) if m.created_at else None,
        }
        for m in matches
    ]


def validate_anketa_for_save(anketa: Anketa, db: Session) -> list[str]:
    """Validate required fields before saving. Returns list of error strings."""
    is_legal = getattr(anketa, 'client_type', None) == "legal_entity"
    errors = []

    if not anketa.consent_personal_data:
        errors.append("Необходимо согласие на обработку персональных данных")

    if is_legal:
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
        if anketa.company_inn and (len(anketa.company_inn) != 14 or not anketa.company_inn.isdigit()):
            errors.append("ИНН компании должен содержать ровно 14 цифр")
    else:
        if not anketa.full_name:
            errors.append("ФИО обязательно")
        if not anketa.birth_date:
            errors.append("Дата рождения обязательна")
        if not anketa.purchase_price:
            errors.append("Стоимость обязательна")
        if not anketa.down_payment_percent:
            errors.append("Процент ПВ обязателен")
        if not anketa.lease_term_months:
            errors.append("Срок аренды обязателен")
        if not anketa.has_current_obligations:
            errors.append("Укажите наличие обязательств (Кредитная история)")
        if not anketa.overdue_category:
            errors.append("Укажите категорию просрочки (Кредитная история)")

    # Validate PV against risk grade
    if anketa.risk_grade and not anketa.no_scoring_response:
        risk_rule = db.query(RiskRule).filter(
            sa_func.lower(RiskRule.category) == anketa.risk_grade.lower(),
            RiskRule.is_active == True
        ).first()
        if risk_rule and anketa.down_payment_percent is not None:
            if anketa.down_payment_percent < risk_rule.min_pv:
                errors.append(f"ПВ ({anketa.down_payment_percent}%) ниже минимума для грейда {anketa.risk_grade} ({risk_rule.min_pv}%)")

    return errors


def notify_admins_on_save(db: Session, anketa: Anketa, user: User):
    """Notify about duplicates and send Telegram notifications on save."""
    dupes = find_duplicates(db, anketa)
    if dupes:
        dupe_ids = ", ".join([f"#{d['id']}" for d in dupes])
        msg = f"Анкета #{anketa.id} имеет совпадения с: {dupe_ids}"
        create_notification(db, anketa.created_by, "duplicate_detected", "Обнаружены дубликаты", msg, anketa.id)
        admin_role_ids = [r.id for r in db.query(Role).filter(Role.user_manage == True).all()]
        admins = db.query(User).filter(
            User.is_active == True,
            (User.role_id.in_(admin_role_ids)) | (User.is_superadmin == True)
        ).all()
        for adm in admins:
            if adm.id != anketa.created_by:
                create_notification(db, adm.id, "duplicate_detected", "Обнаружены дубликаты", msg, anketa.id)

    # Telegram: notify admins about new saved anketa
    from app.telegram_service import notify_telegram_many
    admin_role_ids_tg = [r.id for r in db.query(Role).filter(Role.user_manage == True).all()]
    admin_users = db.query(User).filter(
        User.is_active == True,
        (User.role_id.in_(admin_role_ids_tg)) | (User.is_superadmin == True)
    ).all()
    admin_ids = [a.id for a in admin_users if a.id != user.id]
    client_name = anketa.full_name or anketa.company_name or f"#{anketa.id}"
    if admin_ids:
        notify_telegram_many(db, admin_ids, f"Новая анкета #{anketa.id} от {user.full_name}\nКлиент: {client_name}")


def notify_admins_on_edit_request(db: Session, anketa_id: int, user: User, reason: str):
    """Notify admins about a new edit request."""
    admin_role_ids = [r.id for r in db.query(Role).filter(Role.user_manage == True).all()]
    admins = db.query(User).filter(
        User.is_active == True,
        (User.role_id.in_(admin_role_ids)) | (User.is_superadmin == True)
    ).all()
    for adm in admins:
        create_notification(
            db, adm.id, "edit_request_created",
            "Новый запрос на правку",
            f"{user.full_name} запросил правку анкеты #{anketa_id}. Причина: {reason}",
            anketa_id,
        )

    from app.telegram_service import notify_telegram_many
    admin_ids = [a.id for a in admins]
    if admin_ids:
        notify_telegram_many(db, admin_ids,
            f"Запрос на правку анкеты #{anketa_id}\nОт: {user.full_name}\nПричина: {reason}")


DATE_FIELDS = [
    "birth_date", "passport_issue_date", "last_overdue_date",
    "company_last_overdue_date", "director_last_overdue_date", "guarantor_last_overdue_date",
]


def apply_anketa_updates(db: Session, anketa: Anketa, update_data: dict, user_id: int):
    """Convert dates, normalize passports, record history, and apply field updates."""
    for field in DATE_FIELDS:
        if field in update_data and update_data[field]:
            try:
                update_data[field] = date.fromisoformat(update_data[field])
            except (ValueError, TypeError):
                update_data[field] = None

    for pf in ("guarantor_passport",):
        if pf in update_data and update_data[pf]:
            update_data[pf] = update_data[pf].replace(" ", "")

    for key, value in update_data.items():
        old_value = getattr(anketa, key, None)
        old_str = str(old_value) if old_value is not None else None
        new_str = str(value) if value is not None else None
        if old_str != new_str:
            record_history(db, anketa.id, user_id, key, old_value, value)
        setattr(anketa, key, value)


def apply_conclusion(db: Session, anketa: Anketa, decision: str, comment: str | None,
                     final_pv: float, user: User):
    """Apply conclusion fields, hash PINFL, notify, generate share token."""
    anketa.final_pv = final_pv

    if anketa.risk_grade and not anketa.no_scoring_response:
        risk_rule = db.query(RiskRule).filter(
            sa_func.lower(RiskRule.category) == anketa.risk_grade.lower(),
            RiskRule.is_active == True
        ).first()
        if risk_rule and final_pv < risk_rule.min_pv:
            raise HTTPException(
                status_code=400,
                detail=f"Итоговый ПВ ({final_pv}%) ниже минимума для грейда {anketa.risk_grade} ({risk_rule.min_pv}%)"
            )

    is_reconclusion = anketa.decision is not None
    if is_reconclusion:
        if anketa.decision != decision:
            record_history(db, anketa.id, user.id, "decision", anketa.decision, decision)
        if anketa.conclusion_comment != comment:
            record_history(db, anketa.id, user.id, "conclusion_comment",
                           anketa.conclusion_comment, comment)

    if anketa.pinfl:
        salt = os.environ.get("PINFL_SALT", "fintechdrive_salt_2024")
        anketa.pinfl_hash = hashlib.sha256((salt + anketa.pinfl).encode()).hexdigest()

    anketa.conclusion_version = (anketa.conclusion_version or 0) + 1
    anketa.decision = decision
    anketa.conclusion_comment = comment
    anketa.concluded_by = user.id
    anketa.concluded_at = datetime.utcnow()
    anketa.status = decision

    decision_labels = {
        "approved": "Одобрена",
        "review": "На рассмотрении",
        "rejected_underwriter": "Отказ андеррайтера",
        "rejected_client": "Отказ клиента",
    }
    label = decision_labels.get(decision, decision)
    if user.id != anketa.created_by:
        create_notification(
            db, anketa.created_by, "anketa_concluded",
            f"Анкета #{anketa.id}: {label}",
            f"По анкете #{anketa.id} вынесено решение: {label}." +
            (f" Комментарий: {comment}" if comment else ""),
            anketa.id,
        )

    if not anketa.share_token:
        anketa.share_token = secrets.token_urlsafe(32)

    from app.telegram_service import notify_telegram
    notify_telegram(db, anketa.created_by,
        f"Анкета #{anketa.id}: {label}" +
        (f"\nКомментарий: {comment}" if comment else ""))

    return label


def query_history(db: Session, anketa_id: int, field: str | None,
                  user_filter: int | None, date_from: str | None,
                  date_to: str | None, search: str | None) -> list[dict]:
    """Build and execute history query with filters."""
    q = db.query(AnketaHistory).filter(AnketaHistory.anketa_id == anketa_id)

    if field:
        q = q.filter(AnketaHistory.field_name == field)
    if user_filter:
        q = q.filter(AnketaHistory.changed_by == user_filter)
    if date_from:
        try:
            q = q.filter(AnketaHistory.changed_at >= datetime.fromisoformat(date_from))
        except ValueError:
            pass
    if date_to:
        try:
            q = q.filter(AnketaHistory.changed_at <= datetime.fromisoformat(date_to + "T23:59:59"))
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
