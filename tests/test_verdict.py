"""Тесты авто-вердикта: DTI-решение, просрочки, рекомендованный ПВ."""

from datetime import date
from dateutil.relativedelta import relativedelta

from app.database import Anketa
from app.services.calculation_service import calc_auto_verdict


def _make_anketa(**kwargs) -> Anketa:
    """Создаёт объект Anketa с заданными полями."""
    a = Anketa()
    # Дефолты для обязательных полей
    defaults = {
        "client_type": "individual",
        "dti": None,
        "overdue_category": None,
        "last_overdue_date": None,
        "down_payment_percent": 20,
        "company_overdue_category": None,
        "company_last_overdue_date": None,
        "director_overdue_category": None,
        "director_last_overdue_date": None,
        "guarantor_overdue_category": None,
        "guarantor_last_overdue_date": None,
    }
    defaults.update(kwargs)
    for k, v in defaults.items():
        setattr(a, k, v)
    return a


def _months_ago(n: int) -> date:
    """Возвращает дату N месяцев назад."""
    return date.today() - relativedelta(months=n)


# ===== DTI тесты =====

class TestVerdictDTI:

    def test_verdict_dti_approved(self, default_rules):
        a = _make_anketa(dti=40)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved", f"DTI 40 ≤ 50 → approved, получили {result['auto_decision']}"

    def test_verdict_dti_review(self, default_rules):
        a = _make_anketa(dti=55)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "review", f"DTI 55 > 50, ≤ 60 → review, получили {result['auto_decision']}"

    def test_verdict_dti_rejected(self, default_rules):
        a = _make_anketa(dti=65)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected", f"DTI 65 > 60 → rejected, получили {result['auto_decision']}"

    def test_verdict_dti_none(self, default_rules):
        a = _make_anketa(dti=None)
        result = calc_auto_verdict(a, default_rules)
        reasons_text = " ".join(result["auto_decision_reasons"])
        assert "DTI не рассчитан" in reasons_text, f"DTI=None → причина 'DTI не рассчитан', получили: {reasons_text}"

    def test_verdict_dti_edge_50(self, default_rules):
        a = _make_anketa(dti=50.0)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved", f"DTI ровно 50 → approved (≤50), получили {result['auto_decision']}"

    def test_verdict_dti_edge_60(self, default_rules):
        a = _make_anketa(dti=60.0)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "review", f"DTI ровно 60 → review (≤60), получили {result['auto_decision']}"


# ===== Тесты просрочек (физлицо) =====

class TestVerdictOverdue:

    def test_verdict_overdue_30_days(self, default_rules):
        a = _make_anketa(dti=30, overdue_category="до 30 дней")
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved", f"Просрочка до 30 дней → approved, получили {result['auto_decision']}"

    def test_verdict_overdue_31_60_recent(self, default_rules):
        a = _make_anketa(dti=30, overdue_category="31-60", last_overdue_date=_months_ago(2))
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected", f"31-60, 2 мес назад (<6) → rejected, получили {result['auto_decision']}"

    def test_verdict_overdue_31_60_medium(self, default_rules):
        a = _make_anketa(dti=30, overdue_category="31-60", last_overdue_date=_months_ago(8))
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "review", f"31-60, 8 мес назад (6-12) → review, получили {result['auto_decision']}"

    def test_verdict_overdue_31_60_old(self, default_rules):
        a = _make_anketa(dti=30, overdue_category="31-60", last_overdue_date=_months_ago(15))
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved", f"31-60, 15 мес назад (>12) → approved, получили {result['auto_decision']}"

    def test_verdict_overdue_61_90_recent(self, default_rules):
        a = _make_anketa(dti=30, overdue_category="61-90", last_overdue_date=_months_ago(6))
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected", f"61-90, 6 мес (≤12) → rejected, получили {result['auto_decision']}"

    def test_verdict_overdue_61_90_old(self, default_rules):
        """61-90, давность > 12 мес → approved + ПВ +10% (по документу)."""
        a = _make_anketa(dti=30, overdue_category="61-90", last_overdue_date=_months_ago(15))
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved", f"61-90, 15 мес (>12) → approved, получили {result['auto_decision']}"
        assert result["recommended_pv"] >= 15  # base 5 + 10

    def test_verdict_overdue_90plus_recent(self, default_rules):
        a = _make_anketa(dti=30, overdue_category="90+", last_overdue_date=_months_ago(12))
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected", f"90+, 12 мес (≤24) → rejected, получили {result['auto_decision']}"

    def test_verdict_overdue_90plus_old(self, default_rules):
        """90+, давность > 24 мес → review + ПВ +20% + requires_guarantor (по документу)."""
        a = _make_anketa(dti=30, overdue_category="90+", last_overdue_date=_months_ago(30))
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "review", f"90+, 30 мес (>24) → review, получили {result['auto_decision']}"
        assert result["recommended_pv"] >= 25  # base 5 + 20
        assert result["requires_guarantor"] is True


# ===== Комбинированные тесты =====

class TestVerdictCombined:

    def test_verdict_worst_decision(self, default_rules):
        """DTI=review + overdue=approved → final=review."""
        a = _make_anketa(dti=55, overdue_category="до 30 дней")
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "review", f"DTI review + overdue approved → review, получили {result['auto_decision']}"

    def test_verdict_recommended_pv(self, default_rules):
        """pv_add=5 от просрочки 31-60 medium → recommended = min_pv(5) + 5 = 10, ПВ 8 < 10."""
        a = _make_anketa(dti=30, overdue_category="31-60", last_overdue_date=_months_ago(8), down_payment_percent=8)
        result = calc_auto_verdict(a, default_rules)
        assert result["recommended_pv"] == 10.0, f"Рекомендуемый ПВ: ожидали 10, получили {result['recommended_pv']}"
        reasons_text = " ".join(result["auto_decision_reasons"])
        assert "ниже рекомендуемого" in reasons_text, f"Ожидали предупреждение о ПВ, получили: {reasons_text}"

    def test_verdict_pv_sufficient(self, default_rules):
        """ПВ 25 > recommended 10 → нет предупреждения."""
        a = _make_anketa(dti=30, overdue_category="31-60", last_overdue_date=_months_ago(8), down_payment_percent=25)
        result = calc_auto_verdict(a, default_rules)
        reasons_text = " ".join(result["auto_decision_reasons"])
        assert "ниже рекомендуемого" not in reasons_text, f"ПВ 25 > 10, не должно быть предупреждения: {reasons_text}"


# ===== Тесты юрлицо =====

class TestVerdictLegalEntity:

    def test_verdict_legal_entity_worst_of_three(self, default_rules):
        """Юрлицо: company='до 30 дней', director='61-90' (old), guarantor='31-60' (medium) → worst = review (от director)."""
        a = _make_anketa(
            client_type="legal_entity",
            dti=30,
            company_overdue_category="до 30 дней",
            company_last_overdue_date=_months_ago(1),
            director_overdue_category="61-90",
            director_last_overdue_date=_months_ago(15),
            guarantor_overdue_category="31-60",
            guarantor_last_overdue_date=_months_ago(8),
        )
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "review", \
            f"Юрлицо: worst(approved, review, review) → review, получили {result['auto_decision']}"


# ===== Тесты кредитной истории (парсер v2) =====

class TestVerdictCreditReport:

    def test_systematic_overdue_rejects(self, default_rules):
        """systematic_overdue=True → rejected."""
        a = _make_anketa(dti=40, systematic_overdue=True)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected"
        reasons = " ".join(result["auto_decision_reasons"])
        assert "Систематическая просрочка" in reasons

    def test_systematic_overdue_false_no_effect(self, default_rules):
        """systematic_overdue=False → не влияет."""
        a = _make_anketa(dti=40, systematic_overdue=False)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"

    def test_bad_classification_rejects(self, default_rules):
        """worst_active_classification='Безнадежный' → rejected (по документу: ниже стандартного → отказ)."""
        a = _make_anketa(dti=40, worst_active_classification="Безнадежный")
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected"

    def test_bad_classification_uzbek(self, default_rules):
        """worst_active_classification='Umidsiz' (узб.) → rejected."""
        a = _make_anketa(dti=40, worst_active_classification="Umidsiz")
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected"

    def test_substandard_classification_rejects(self, default_rules):
        """worst_active_classification='Субстандартный' → rejected (по документу: ниже стандартного → отказ)."""
        a = _make_anketa(dti=40, worst_active_classification="Субстандартный")
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected"

    def test_good_classification_no_effect(self, default_rules):
        """worst_active_classification='Стандартный' → не влияет."""
        a = _make_anketa(dti=40, worst_active_classification="Стандартный")
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"

    def test_lombard_rejects(self, default_rules):
        """has_lombard=True → rejected (по документу: ломбард → отказ)."""
        a = _make_anketa(dti=40, has_lombard=True)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected"

    def test_lombard_false_no_effect(self, default_rules):
        """has_lombard=False → не влияет."""
        a = _make_anketa(dti=40, has_lombard=False)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"

    def test_combined_multiple_bad_signals(self, default_rules):
        """DTI review + systematic_overdue + lombard → rejected (worst wins)."""
        a = _make_anketa(dti=55, systematic_overdue=True, has_lombard=True)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected"


# ===== Тесты риск-грейд + ПВ =====

class TestVerdictRiskGradePV:
    """Проверяем что risk_grade E/F поднимает базовый ПВ до min_pv из RiskRule."""

    RISK_RULES = [
        {"category": "E", "min_pv": 20.0},
        {"category": "E1", "min_pv": 20.0},
        {"category": "F", "min_pv": 20.0},
        {"category": "F1", "min_pv": 25.0},
    ]

    def test_grade_e_base_pv_20(self, default_rules):
        """risk_grade=E → recommended_pv = 20 (а не 5)."""
        a = _make_anketa(dti=40, risk_grade="E", down_payment_percent=10)
        result = calc_auto_verdict(a, default_rules, risk_rules=self.RISK_RULES)
        assert result["recommended_pv"] == 20.0

    def test_grade_f1_base_pv_25(self, default_rules):
        """risk_grade=F1 → recommended_pv = 25."""
        a = _make_anketa(dti=40, risk_grade="F1", down_payment_percent=10)
        result = calc_auto_verdict(a, default_rules, risk_rules=self.RISK_RULES)
        assert result["recommended_pv"] == 25.0

    def test_grade_e_plus_lombard(self, default_rules):
        """risk_grade=E (base 20) + lombard → rejected (lombard is hard reject now)."""
        a = _make_anketa(dti=40, risk_grade="E", has_lombard=True, down_payment_percent=10)
        result = calc_auto_verdict(a, default_rules, risk_rules=self.RISK_RULES)
        assert result["auto_decision"] == "rejected"
        assert result["recommended_pv"] == 20.0  # No PV add from lombard

    def test_grade_e_plus_bad_classification(self, default_rules):
        """risk_grade=E (base 20) + bad classification → rejected (classification is hard reject now)."""
        a = _make_anketa(dti=40, risk_grade="E", worst_active_classification="Безнадежный", down_payment_percent=10)
        result = calc_auto_verdict(a, default_rules, risk_rules=self.RISK_RULES)
        assert result["auto_decision"] == "rejected"
        assert result["recommended_pv"] == 20.0  # No PV add from classification

    def test_no_grade_stays_base_5(self, default_rules):
        """Без risk_grade → базовый ПВ = 5%."""
        a = _make_anketa(dti=40, down_payment_percent=3)
        result = calc_auto_verdict(a, default_rules, risk_rules=self.RISK_RULES)
        assert result["recommended_pv"] == 5.0

    def test_no_scoring_response_ignores_grade(self, default_rules):
        """no_scoring_response=True → грейд игнорируется, базовый ПВ = 5%."""
        a = _make_anketa(dti=40, risk_grade="E", no_scoring_response=True, down_payment_percent=3)
        result = calc_auto_verdict(a, default_rules, risk_rules=self.RISK_RULES)
        assert result["recommended_pv"] == 5.0

    def test_unknown_grade_stays_base(self, default_rules):
        """Неизвестный грейд (не в RiskRule) → базовый ПВ = 5%."""
        a = _make_anketa(dti=40, risk_grade="Z99", down_payment_percent=3)
        result = calc_auto_verdict(a, default_rules, risk_rules=self.RISK_RULES)
        assert result["recommended_pv"] == 5.0

    def test_without_risk_rules_param(self, default_rules):
        """Без risk_rules параметра (обратная совместимость) → базовый ПВ = 5%."""
        a = _make_anketa(dti=40, risk_grade="E", down_payment_percent=3)
        result = calc_auto_verdict(a, default_rules)
        assert result["recommended_pv"] == 5.0


# ===== Тесты текущей просрочки =====

class TestVerdictCurrentOverdue:

    def test_current_overdue_rejects(self, default_rules):
        """current_overdue_amount > 0 → rejected."""
        a = _make_anketa(dti=40, current_overdue_amount=500000)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected"
        reasons = " ".join(result["auto_decision_reasons"])
        assert "Текущая просрочка" in reasons

    def test_current_overdue_zero_no_effect(self, default_rules):
        """current_overdue_amount = 0 → не влияет."""
        a = _make_anketa(dti=40, current_overdue_amount=0)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"

    def test_current_overdue_none_no_effect(self, default_rules):
        """current_overdue_amount = None → не влияет."""
        a = _make_anketa(dti=40, current_overdue_amount=None)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"

    def test_current_overdue_overrides_good_dti(self, default_rules):
        """DTI хороший, но текущая просрочка → rejected."""
        a = _make_anketa(dti=20, current_overdue_amount=4024425)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected"

    def test_current_overdue_amount_in_reason(self, default_rules):
        """Сумма просрочки отображается в причине."""
        a = _make_anketa(dti=40, current_overdue_amount=1500000)
        result = calc_auto_verdict(a, default_rules)
        reasons = " ".join(result["auto_decision_reasons"])
        assert "1,500,000" in reasons


# ===== Тесты скоринговый класс D/E =====

class TestVerdictScoringClass:

    def test_scoring_class_d_rejects(self, default_rules):
        """scoring_class='D' → rejected."""
        a = _make_anketa(dti=40, scoring_class="D")
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected"
        reasons = " ".join(result["auto_decision_reasons"])
        assert "Скоринговый класс D" in reasons

    def test_scoring_class_e_rejects(self, default_rules):
        """scoring_class='E' → rejected."""
        a = _make_anketa(dti=40, scoring_class="E")
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected"

    def test_scoring_class_c_no_effect(self, default_rules):
        """scoring_class='C' → не влияет."""
        a = _make_anketa(dti=40, scoring_class="C")
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"

    def test_scoring_class_none_no_effect(self, default_rules):
        """scoring_class=None → не влияет."""
        a = _make_anketa(dti=40, scoring_class=None)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"


# ===== Тесты закрытая классификация =====

class TestVerdictClosedClassification:

    def test_closed_bad_rejects(self, default_rules):
        """worst_closed_classification='Сомнительный' → rejected."""
        a = _make_anketa(dti=40, worst_closed_classification="Сомнительный")
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected"
        reasons = " ".join(result["auto_decision_reasons"])
        assert "закрытые" in reasons

    def test_closed_qoniqarsiz_rejects(self, default_rules):
        """worst_closed_classification='Qoniqarsiz' → rejected."""
        a = _make_anketa(dti=40, worst_closed_classification="Qoniqarsiz")
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected"

    def test_closed_substandard_ok(self, default_rules):
        """worst_closed_classification='Субстандартный' → OK (допустимо для закрытых)."""
        a = _make_anketa(dti=40, worst_closed_classification="Субстандартный")
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"

    def test_closed_standard_ok(self, default_rules):
        """worst_closed_classification='Стандартный' → OK."""
        a = _make_anketa(dti=40, worst_closed_classification="Стандартный")
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"

    def test_closed_none_ok(self, default_rules):
        """worst_closed_classification=None → OK."""
        a = _make_anketa(dti=40, worst_closed_classification=None)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"


# ===== Тесты возраста =====

class TestVerdictAge:

    def test_age_below_21_rejects(self, default_rules):
        """Возраст 20 лет → rejected."""
        young_date = date(date.today().year - 20, date.today().month, date.today().day)
        a = _make_anketa(dti=40, birth_date=young_date)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected"
        reasons = " ".join(result["auto_decision_reasons"])
        assert "Возраст" in reasons and "< 21" in reasons

    def test_age_above_65_rejects(self, default_rules):
        """Возраст 66 лет → rejected."""
        old_date = date(date.today().year - 66, date.today().month, date.today().day)
        a = _make_anketa(dti=40, birth_date=old_date)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected"
        reasons = " ".join(result["auto_decision_reasons"])
        assert "Возраст" in reasons and "> 65" in reasons

    def test_age_21_ok(self, default_rules):
        """Возраст ровно 21 → approved."""
        bd = date(date.today().year - 21, date.today().month, date.today().day)
        a = _make_anketa(dti=40, birth_date=bd)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"

    def test_age_65_ok(self, default_rules):
        """Возраст ровно 65 → approved."""
        bd = date(date.today().year - 65, date.today().month, date.today().day)
        a = _make_anketa(dti=40, birth_date=bd)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"

    def test_age_none_no_effect(self, default_rules):
        """birth_date=None → не влияет."""
        a = _make_anketa(dti=40, birth_date=None)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"

    def test_age_string_date(self, default_rules):
        """birth_date как строка '1980-01-15' → тоже работает."""
        a = _make_anketa(dti=40, birth_date="1980-01-15")
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"


# ===== Тесты открытых заявок =====

class TestVerdictOpenApplications:

    def test_open_apps_review(self, default_rules):
        """open_applications_count > 0 → review."""
        a = _make_anketa(dti=40, open_applications_count=3)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "review"
        reasons = " ".join(result["auto_decision_reasons"])
        assert "Открытые заявки" in reasons

    def test_open_apps_zero_no_effect(self, default_rules):
        """open_applications_count = 0 → не влияет."""
        a = _make_anketa(dti=40, open_applications_count=0)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"

    def test_open_apps_none_no_effect(self, default_rules):
        """open_applications_count = None → не влияет."""
        a = _make_anketa(dti=40, open_applications_count=None)
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "approved"


# ===== Тесты requires_guarantor =====

class TestVerdictGuarantor:

    def test_90plus_old_requires_guarantor(self, default_rules):
        """90+ давность >24м → requires_guarantor = True."""
        a = _make_anketa(dti=30, overdue_category="90+", last_overdue_date=_months_ago(30))
        result = calc_auto_verdict(a, default_rules)
        assert result["requires_guarantor"] is True

    def test_no_overdue_no_guarantor(self, default_rules):
        """Без просрочки → requires_guarantor = False."""
        a = _make_anketa(dti=40)
        result = calc_auto_verdict(a, default_rules)
        assert result["requires_guarantor"] is False

    def test_61_90_old_no_guarantor(self, default_rules):
        """61-90 давность >12м → requires_guarantor = False."""
        a = _make_anketa(dti=30, overdue_category="61-90", last_overdue_date=_months_ago(15))
        result = calc_auto_verdict(a, default_rules)
        assert result["requires_guarantor"] is False


# ===== Тесты overdue PV additions по документу =====

class TestVerdictOverduePV:

    def test_31_60_old_no_pv(self, default_rules):
        """31-60 > 12м → одобрено БЕЗ ПВ (по документу)."""
        a = _make_anketa(dti=30, overdue_category="31-60", last_overdue_date=_months_ago(15), down_payment_percent=5)
        result = calc_auto_verdict(a, default_rules)
        assert result["recommended_pv"] == 5.0  # Без надбавки

    def test_61_90_old_pv_10(self, default_rules):
        """61-90 > 12м → approved + ПВ +10%."""
        a = _make_anketa(dti=30, overdue_category="61-90", last_overdue_date=_months_ago(15), down_payment_percent=5)
        result = calc_auto_verdict(a, default_rules)
        assert result["recommended_pv"] == 15.0  # 5 + 10

    def test_90plus_old_pv_20(self, default_rules):
        """90+ > 24м → review + ПВ +20%."""
        a = _make_anketa(dti=30, overdue_category="90+", last_overdue_date=_months_ago(30), down_payment_percent=5)
        result = calc_auto_verdict(a, default_rules)
        assert result["recommended_pv"] == 25.0  # 5 + 20
