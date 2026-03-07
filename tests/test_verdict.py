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
        a = _make_anketa(dti=30, overdue_category="61-90", last_overdue_date=_months_ago(15))
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "review", f"61-90, 15 мес (>12) → review, получили {result['auto_decision']}"

    def test_verdict_overdue_90plus_recent(self, default_rules):
        a = _make_anketa(dti=30, overdue_category="90+", last_overdue_date=_months_ago(12))
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "rejected", f"90+, 12 мес (≤24) → rejected, получили {result['auto_decision']}"

    def test_verdict_overdue_90plus_old(self, default_rules):
        a = _make_anketa(dti=30, overdue_category="90+", last_overdue_date=_months_ago(30))
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "review", f"90+, 30 мес (>24) → review, получили {result['auto_decision']}"


# ===== Комбинированные тесты =====

class TestVerdictCombined:

    def test_verdict_worst_decision(self, default_rules):
        """DTI=approved + overdue=review → final=review."""
        a = _make_anketa(dti=30, overdue_category="61-90", last_overdue_date=_months_ago(15))
        result = calc_auto_verdict(a, default_rules)
        assert result["auto_decision"] == "review", f"DTI approved + overdue review → review, получили {result['auto_decision']}"

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
