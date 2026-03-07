from datetime import date

from sqlalchemy.orm import Session

from app.database import Anketa, UnderwritingRule


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
