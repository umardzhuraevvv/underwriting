import logging
from datetime import date

from sqlalchemy.orm import Session

from app.database import Anketa, UnderwritingRule

logger = logging.getLogger("app")


_DECISION_RU = {"approved": "одобрено", "review": "на рассмотрение", "rejected": "отказ"}


def _decision_ru(d: str) -> str:
    return _DECISION_RU.get(d, d)


def calc_annuity(principal: float, annual_rate: float, months: int) -> float:
    """Calculate annuity monthly payment."""
    if not principal or not months:
        return 0.0
    if not annual_rate:
        return principal / months
    r = annual_rate / 100 / 12
    return principal * (r * (1 + r) ** months) / ((1 + r) ** months - 1)


def calc_max_principal(annual_rate: float, months: int, max_payment: float) -> float:
    """Inverse annuity: max loan principal for a given max monthly payment."""
    if not months or max_payment <= 0:
        return 0.0
    if not annual_rate:
        return max_payment * months
    r = annual_rate / 100 / 12
    return max_payment * ((1 + r) ** months - 1) / (r * (1 + r) ** months)


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
    months = (today.year - d.year) * 12 + (today.month - d.month)
    if today.day < d.day:
        months -= 1
    return max(months, 0)


def _worst_decision(a: str | None, b: str | None) -> str:
    """Return the worst (most restrictive) of two decisions."""
    order = {"approved": 0, "review": 1, "rejected": 2}
    va = order.get(a, -1)
    vb = order.get(b, -1)
    if va >= vb:
        return a
    return b


def _calc_overdue_decision_for_category(cat: str | None, overdue_date: date | None,
                                         rules: dict, reasons: list, prefix: str) -> tuple[str, float, bool]:
    """Calculate overdue decision for a single overdue category. Returns (decision, pv_add, requires_guarantor)."""
    decision = "approved"
    pv_add = 0.0
    months = _months_since(overdue_date)

    requires_guarantor = False

    if cat and cat != "до 30 дней":
        if cat == "31-60":
            near = rules.get("overdue_31_60_threshold_near", 6)
            far = rules.get("overdue_31_60_threshold_far", 12)
            if months is not None and months < near:
                decision = rules.get("overdue_31_60_lt_near_result", "rejected")
                reasons.append(f"{prefix}Просрочка 31-60, давность {months} мес < {near} мес — {_decision_ru(decision)}")
            elif months is not None and months <= far:
                decision = rules.get("overdue_31_60_near_to_far_result", "review")
                pv_add += rules.get("overdue_31_60_near_to_far_pv_add", 5)
                reasons.append(f"{prefix}Просрочка 31-60, давность {months} мес ({near}–{far}) — {_decision_ru(decision)}, ПВ +{rules.get('overdue_31_60_near_to_far_pv_add', 5)}%")
            else:
                # Документ: 31-60 > 12 мес → одобрено без ПВ
                decision = rules.get("overdue_31_60_gt_far_result", "approved")
                pv_add += rules.get("overdue_31_60_gt_far_pv_add", 0)
                m_str = f"{months} мес" if months is not None else "нет даты"
                reasons.append(f"{prefix}Просрочка 31-60, давность {m_str} > {far} мес — {_decision_ru(decision)}")
        elif cat == "61-90":
            threshold = rules.get("overdue_61_90_threshold", 12)
            if months is not None and months > threshold:
                # Документ: 61-90 > 12 мес → одобрено + ПВ +10%
                decision = rules.get("overdue_61_90_gt_result", "approved")
                pv_add += rules.get("overdue_61_90_gt_pv_add", 10)
                reasons.append(f"{prefix}Просрочка 61-90, давность {months} мес > {threshold} мес — {_decision_ru(decision)}, ПВ +{rules.get('overdue_61_90_gt_pv_add', 10):.0f}%")
            else:
                decision = rules.get("overdue_61_90_lte_result", "rejected")
                m_str = f"{months} мес" if months is not None else "нет даты"
                reasons.append(f"{prefix}Просрочка 61-90, давность {m_str} ≤ {threshold} мес — {_decision_ru(decision)}")
        elif cat == "90+":
            threshold = rules.get("overdue_90plus_threshold", 24)
            if months is not None and months > threshold:
                # Документ: 90+ > 24 мес → на рассмотрение + ПВ +20% + обязательный поручитель
                decision = rules.get("overdue_90plus_gt_result", "review")
                pv_add += rules.get("overdue_90plus_gt_pv_add", 20)
                requires_guarantor = True
                reasons.append(f"{prefix}Просрочка 90+, давность {months} мес > {threshold} мес — {_decision_ru(decision)}, ПВ +{rules.get('overdue_90plus_gt_pv_add', 20):.0f}%, обязательный поручитель")
            else:
                decision = rules.get("overdue_90plus_lte_result", "rejected")
                m_str = f"{months} мес" if months is not None else "нет даты"
                reasons.append(f"{prefix}Просрочка 90+, давность {m_str} ≤ {threshold} мес — {_decision_ru(decision)}")
    elif cat == "до 30 дней":
        decision = rules.get("overdue_30_result", "approved")
        reasons.append(f"{prefix}Просрочка до 30 дней — {_decision_ru(decision)}")

    return decision, pv_add, requires_guarantor


def calc_auto_verdict(anketa: Anketa, rules: dict, risk_rules: list | None = None) -> dict:
    """Calculate automatic underwriting verdict based on rules.

    risk_rules: list of dicts {"category": "E", "min_pv": 20.0} from RiskRule table.
    """
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

    requires_guarantor = False

    if is_legal:
        # For legal entities: check company, director, guarantor overdue separately
        # then take worst decision of all three
        overdue_decision = "approved"

        # Company overdue
        comp_decision, comp_pv, comp_guar = _calc_overdue_decision_for_category(
            anketa.company_overdue_category, anketa.company_last_overdue_date,
            rules, reasons, "[Компания] "
        )
        pv_add += comp_pv
        requires_guarantor = requires_guarantor or comp_guar
        overdue_decision = _worst_decision(overdue_decision, comp_decision)

        # Director overdue
        dir_decision, dir_pv, dir_guar = _calc_overdue_decision_for_category(
            anketa.director_overdue_category, anketa.director_last_overdue_date,
            rules, reasons, "[Директор] "
        )
        pv_add += dir_pv
        requires_guarantor = requires_guarantor or dir_guar
        overdue_decision = _worst_decision(overdue_decision, dir_decision)

        # Guarantor overdue
        guar_decision, guar_pv, guar_guar = _calc_overdue_decision_for_category(
            anketa.guarantor_overdue_category, anketa.guarantor_last_overdue_date,
            rules, reasons, "[Поручитель] "
        )
        pv_add += guar_pv
        overdue_decision = _worst_decision(overdue_decision, guar_decision)

    else:
        # Individual: use same function
        overdue_decision, ind_pv, ind_guar = _calc_overdue_decision_for_category(
            anketa.overdue_category, anketa.last_overdue_date,
            rules, reasons, ""
        )
        pv_add += ind_pv
        requires_guarantor = requires_guarantor or ind_guar

    # --- Current overdue: auto reject ---
    current_overdue_decision = "approved"
    current_overdue_amt = getattr(anketa, 'current_overdue_amount', None)
    if current_overdue_amt and current_overdue_amt > 0:
        current_overdue_decision = rules.get("current_overdue_result", "rejected")
        reasons.append(f"Текущая просрочка {current_overdue_amt:,.0f} сум — {_decision_ru(current_overdue_decision)}")

    # --- Credit report: systematic overdue ---
    systematic_decision = "approved"
    if getattr(anketa, 'systematic_overdue', False):
        systematic_decision = rules.get("systematic_overdue_result", "rejected")
        reasons.append(f"Систематическая просрочка (3+ эпизодов 31+ дней за 12 мес) — {_decision_ru(systematic_decision)}")

    # --- Credit report: worst active classification ---
    # Документ: если по действующим обязательствам классификация ниже "Стандартный" → отказ
    classification_decision = "approved"
    worst_class = getattr(anketa, 'worst_active_classification', None)
    STANDARD_CLASSES = {"Стандартный", "Standart", "Standard", "н/д", None}
    if worst_class and worst_class not in STANDARD_CLASSES:
        classification_decision = rules.get("bad_classification_result", "rejected")
        reasons.append(f"Класс активов (действующие): {worst_class} — {_decision_ru(classification_decision)}")

    # --- Credit report: worst closed classification ---
    # Документ: если по закрытым обязательствам ниже "Субстандартный" → отказ
    closed_classification_decision = "approved"
    closed_class = getattr(anketa, 'worst_closed_classification', None)
    CLOSED_OK_CLASSES = {"Стандартный", "Standart", "Standard", "Субстандартный", "Substandart", "н/д", None}
    if closed_class and closed_class not in CLOSED_OK_CLASSES:
        closed_classification_decision = rules.get("closed_classification_result", "rejected")
        reasons.append(f"Класс активов (закрытые): {closed_class} — {_decision_ru(closed_classification_decision)}")

    # --- Credit report: lombard ---
    # Документ: наличие ломбардных обязательств → автоматический отказ
    lombard_decision = "approved"
    if getattr(anketa, 'has_lombard', False):
        lombard_decision = rules.get("lombard_result", "rejected")
        reasons.append(f"Ломбардные обязательства — {_decision_ru(lombard_decision)}")

    # --- Scoring class D/E → auto reject ---
    scoring_class_decision = "approved"
    sc = getattr(anketa, 'scoring_class', None)
    if sc and sc.upper() in ("D", "E"):
        scoring_class_decision = rules.get("scoring_class_de_result", "rejected")
        reasons.append(f"Скоринговый класс {sc.upper()} — {_decision_ru(scoring_class_decision)}")

    # --- Age check ---
    min_age = rules.get("min_age", 21)
    max_age = rules.get("max_age", 65)
    age_decision = "approved"
    bd = getattr(anketa, 'birth_date', None)
    if bd:
        try:
            if isinstance(bd, str):
                bd = date.fromisoformat(bd)
            today = date.today()
            age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
            if age < min_age:
                age_decision = "rejected"
                reasons.append(f"Возраст {age} лет < {min_age} — отказ")
            elif age > max_age:
                age_decision = "rejected"
                reasons.append(f"Возраст {age} лет > {max_age} — отказ")
        except (ValueError, TypeError):
            pass

    # --- Open applications in last 10 days ---
    open_apps_decision = "approved"
    open_apps_count = getattr(anketa, 'open_applications_count', None)
    if open_apps_count and open_apps_count > 0:
        open_apps_decision = rules.get("open_apps_result", "review")
        reasons.append(f"Открытые заявки за 10 дней: {open_apps_count} — {_decision_ru(open_apps_decision)}")

    # --- Final decision = worst of all checks ---
    final = _worst_decision(dti_decision, overdue_decision)
    final = _worst_decision(final, current_overdue_decision)
    final = _worst_decision(final, systematic_decision)
    final = _worst_decision(final, classification_decision)
    final = _worst_decision(final, closed_classification_decision)
    final = _worst_decision(final, lombard_decision)
    final = _worst_decision(final, scoring_class_decision)
    final = _worst_decision(final, age_decision)
    final = _worst_decision(final, open_apps_decision)

    # --- Recommended PV ---
    base_pv = rules.get("min_pv_percent", 5)

    # If risk grade matches a RiskRule, use its min_pv as the base (usually 20% for E/F grades)
    grade = getattr(anketa, 'risk_grade', None)
    no_scoring = getattr(anketa, 'no_scoring_response', False)
    if grade and not no_scoring and risk_rules:
        matched = next((r for r in risk_rules if r["category"].lower() == grade.lower()), None)
        if matched and matched["min_pv"] > base_pv:
            base_pv = matched["min_pv"]
            reasons.append(f"Риск-грейд {grade} — мин. ПВ {base_pv:.0f}%")

    current_pv = anketa.down_payment_percent or 0
    recommended_pv = base_pv + pv_add
    if current_pv < recommended_pv:
        reasons.append(f"Текущий ПВ {current_pv:.0f}% ниже рекомендуемого {recommended_pv:.0f}%")

    # --- DTI suggestions: if DTI > threshold, suggest min PV or max car price ---
    dti_suggestion_pv = None
    dti_suggestion_price = None
    income = anketa.total_monthly_income or 0
    obligations = anketa.monthly_obligations_payment or 0
    rate = anketa.interest_rate or 0
    term = anketa.lease_term_months or 0
    price = anketa.purchase_price or 0

    if dti is not None and dti > max_approve and income > 0 and rate > 0 and term > 0 and price > 0:
        max_payment = income * max_approve / 100 - obligations
        if max_payment > 0:
            max_principal = calc_max_principal(rate, term, max_payment)
            # Min PV for DTI ≤ 50% at current car price
            if max_principal < price:
                min_pv_for_dti = round((1 - max_principal / price) * 100, 1)
                min_pv_for_dti = max(min_pv_for_dti, recommended_pv)
                dti_suggestion_pv = min_pv_for_dti
                reasons.append(f"Для DTI ≤ {max_approve}%: увеличьте ПВ до {min_pv_for_dti:.0f}%")
            # Max car price for DTI ≤ 50% at current PV%
            if current_pv > 0:
                max_price = max_principal / (1 - current_pv / 100)
                dti_suggestion_price = round(max_price)
                reasons.append(f"Или выберите авто до {max_price:,.0f} сум при ПВ {current_pv:.0f}%")

    logger.info(
        "Авто-вердикт для анкеты #%s: %s, DTI=%.1f%%",
        getattr(anketa, 'id', '?'), final, anketa.dti or 0,
    )

    return {
        "auto_decision": final,
        "auto_decision_reasons": reasons,
        "recommended_pv": round(recommended_pv, 1),
        "dti_suggestion_pv": dti_suggestion_pv,
        "dti_suggestion_price": dti_suggestion_price,
        "requires_guarantor": requires_guarantor,
    }
