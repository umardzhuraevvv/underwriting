"""Тесты расчётов: аннуитет, доход, ПВ, DTI, worst_overdue."""

from types import SimpleNamespace

from app.services.calculation_service import (
    calc_annuity,
    calc_total_monthly_income,
    run_calculations,
    _worst_overdue_category,
)
from app.database import Anketa


def _make_anketa(**kwargs) -> Anketa:
    """Создаёт объект Anketa с заданными полями (без сохранения в БД)."""
    a = Anketa()
    for k, v in kwargs.items():
        setattr(a, k, v)
    return a


# ===== calc_annuity =====

class TestCalcAnnuity:

    def test_annuity_basic(self):
        result = calc_annuity(1_000_000, 24, 12)
        assert abs(result - 94_560) < 200, f"Ожидали ~94560, получили {result}"

    def test_annuity_zero_rate(self):
        result = calc_annuity(1_200_000, 0, 12)
        assert result == 0.0, "При нулевой ставке и проверке `not annual_rate` должен вернуть 0.0"

    def test_annuity_zero_principal(self):
        result = calc_annuity(0, 24, 12)
        assert result == 0.0, "При нулевом principal должен вернуть 0.0"

    def test_annuity_none_values(self):
        assert calc_annuity(None, 24, 12) == 0.0, "None principal → 0.0"
        assert calc_annuity(1_000_000, None, 12) == 0.0, "None rate → 0.0"
        assert calc_annuity(1_000_000, 24, None) == 0.0, "None months → 0.0"
        assert calc_annuity(1_000_000, 24, 0) == 0.0, "0 months → 0.0"

    def test_annuity_long_term(self):
        result = calc_annuity(5_000_000, 18, 60)
        assert 100_000 < result < 200_000, f"60 мес 18% — ожидали разумный результат, получили {result}"

    def test_annuity_high_rate(self):
        result = calc_annuity(1_000_000, 48, 12)
        simple = 1_000_000 / 12
        assert result > simple, f"При высокой ставке платёж ({result}) должен быть > {simple}"


# ===== calc_total_monthly_income =====

class TestCalcTotalMonthlyIncome:

    def test_income_individual_salary_only(self):
        a = _make_anketa(
            client_type="individual",
            total_salary=600_000, salary_period_months=6,
            main_activity_income=None, main_activity_period=None,
            additional_income_total=None, additional_income_period=None,
            other_income_total=None, other_income_period=None,
        )
        result = calc_total_monthly_income(a)
        assert result == 100_000.0, f"600000/6 = 100000, получили {result}"

    def test_income_individual_all_sources(self):
        a = _make_anketa(
            client_type="individual",
            total_salary=600_000, salary_period_months=6,       # 100k
            main_activity_income=300_000, main_activity_period=3,  # 100k
            additional_income_total=120_000, additional_income_period=6,  # 20k
            other_income_total=60_000, other_income_period=3,       # 20k
        )
        result = calc_total_monthly_income(a)
        assert result == 240_000.0, f"Ожидали 240000, получили {result}"

    def test_income_individual_no_data(self):
        a = _make_anketa(
            client_type="individual",
            total_salary=None, salary_period_months=None,
            main_activity_income=None, main_activity_period=None,
            additional_income_total=None, additional_income_period=None,
            other_income_total=None, other_income_period=None,
        )
        result = calc_total_monthly_income(a)
        assert result == 0.0, f"Все None → 0.0, получили {result}"

    def test_income_legal_entity(self):
        a = _make_anketa(
            client_type="legal_entity",
            company_revenue_total=1_200_000, company_revenue_period=12,  # 100k
            director_income_total=600_000, director_income_period=6,      # 100k
        )
        result = calc_total_monthly_income(a)
        assert result == 200_000.0, f"Ожидали 200000, получили {result}"

    def test_income_partial_data(self):
        a = _make_anketa(
            client_type="individual",
            total_salary=600_000, salary_period_months=6,
            main_activity_income=None, main_activity_period=None,
            additional_income_total=100_000, additional_income_period=None,  # period=None → не считается
            other_income_total=None, other_income_period=None,
        )
        result = calc_total_monthly_income(a)
        assert result == 100_000.0, f"Только salary считается, получили {result}"


# ===== run_calculations =====

class TestRunCalculations:

    def test_calculations_down_payment(self):
        a = _make_anketa(
            purchase_price=10_000_000, down_payment_percent=20,
            interest_rate=24, lease_term_months=12,
            client_type="individual",
            total_salary=600_000, salary_period_months=6,
            main_activity_income=None, main_activity_period=None,
            additional_income_total=None, additional_income_period=None,
            other_income_total=None, other_income_period=None,
            monthly_obligations_payment=0,
            overdue_category=None,
        )
        run_calculations(a)
        assert a.down_payment_amount == 2_000_000.0, f"ПВ сумма: ожидали 2000000, получили {a.down_payment_amount}"
        assert a.remaining_amount == 8_000_000.0, f"Остаток: ожидали 8000000, получили {a.remaining_amount}"

    def test_calculations_monthly_payment(self):
        a = _make_anketa(
            purchase_price=10_000_000, down_payment_percent=20,
            interest_rate=24, lease_term_months=12,
            client_type="individual",
            total_salary=600_000, salary_period_months=6,
            main_activity_income=None, main_activity_period=None,
            additional_income_total=None, additional_income_period=None,
            other_income_total=None, other_income_period=None,
            monthly_obligations_payment=0,
            overdue_category=None,
        )
        run_calculations(a)
        expected = round(calc_annuity(8_000_000, 24, 12), 2)
        assert a.monthly_payment == expected, f"Ежемесячный платёж: ожидали {expected}, получили {a.monthly_payment}"

    def test_calculations_dti(self):
        a = _make_anketa(
            purchase_price=10_000_000, down_payment_percent=20,
            interest_rate=24, lease_term_months=12,
            client_type="individual",
            total_salary=None, salary_period_months=None,
            main_activity_income=None, main_activity_period=None,
            additional_income_total=None, additional_income_period=None,
            other_income_total=None, other_income_period=None,
            monthly_obligations_payment=10_000,
            overdue_category=None,
        )
        # Вручную зададим income через total_salary
        a.total_salary = 600_000
        a.salary_period_months = 6  # income = 100_000
        run_calculations(a)
        # dti = (monthly_payment + 10_000) / 100_000 * 100
        payment = a.monthly_payment or 0
        expected_dti = round((payment + 10_000) / 100_000 * 100, 2)
        assert a.dti == expected_dti, f"DTI: ожидали {expected_dti}, получили {a.dti}"

    def test_calculations_dti_zero_income(self):
        a = _make_anketa(
            purchase_price=10_000_000, down_payment_percent=20,
            interest_rate=24, lease_term_months=12,
            client_type="individual",
            total_salary=None, salary_period_months=None,
            main_activity_income=None, main_activity_period=None,
            additional_income_total=None, additional_income_period=None,
            other_income_total=None, other_income_period=None,
            monthly_obligations_payment=0,
            overdue_category=None,
        )
        run_calculations(a)
        assert a.dti is None, f"При нулевом доходе DTI должен быть None, получили {a.dti}"

    def test_calculations_no_price(self):
        a = _make_anketa(
            purchase_price=None, down_payment_percent=20,
            interest_rate=24, lease_term_months=12,
            client_type="individual",
            total_salary=600_000, salary_period_months=6,
            main_activity_income=None, main_activity_period=None,
            additional_income_total=None, additional_income_period=None,
            other_income_total=None, other_income_period=None,
            monthly_obligations_payment=0,
            overdue_category=None,
        )
        run_calculations(a)
        assert a.down_payment_amount is None, "Без цены ПВ сумма = None"
        assert a.remaining_amount is None, "Без цены остаток = None"


# ===== _worst_overdue_category =====

class TestWorstOverdueCategory:

    def test_worst_overdue_single(self):
        result = _worst_overdue_category("до 30 дней")
        assert result == "до 30 дней", f"Ожидали 'до 30 дней', получили '{result}'"

    def test_worst_overdue_mixed(self):
        result = _worst_overdue_category("до 30 дней", "61-90", "31-60")
        assert result == "61-90", f"Ожидали '61-90', получили '{result}'"

    def test_worst_overdue_all_none(self):
        result = _worst_overdue_category(None, None)
        assert result is None, f"Все None → None, получили '{result}'"

    def test_worst_overdue_with_90plus(self):
        result = _worst_overdue_category("31-60", "90+")
        assert result == "90+", f"Ожидали '90+', получили '{result}'"
