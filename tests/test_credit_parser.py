"""Tests for the InfoScore credit report parser v2."""

import os
import pytest

from app.credit_report_parser import parse_infoscore_html

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "credit_reports")


def _load(filename: str) -> dict:
    path = os.path.join(FIXTURES_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return parse_infoscore_html(f.read())


# ── Fixture 01: RU individual, clean (B1, no current overdue) ────────────────


class TestRuIndividualClean:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.r = _load("01_ru_individual_clean.html")

    def test_entity_type(self):
        assert self.r["entity_type"] == "individual"

    def test_language_detected_as_ru(self):
        """Section 5 header ДЕЙСТВУЮЩИЕ ДОГОВОРА → RU."""
        # Verify RU-specific classification label used
        assert self.r["worst_active_classification"] == "Стандартный"

    def test_personal_data(self):
        assert self.r["full_name"] == "G'Aniyev Botir Baxtiyor O'G'Li"
        assert self.r["pinfl"] == "31412810191870"
        assert self.r["birth_date"] == "1981-12-14"

    def test_scoring(self):
        assert self.r["ki_score"] == "B1 / 322"
        assert self.r["scoring_class"] == "B"
        assert self.r["scoring_number"] == 1
        assert self.r["scoring_score"] == 322

    def test_report_date(self):
        assert self.r["report_date"] == "2025-10-22"

    def test_active_obligations(self):
        assert self.r["has_current_obligations"] == "есть"
        assert self.r["obligations_count"] == 2
        assert self.r["total_obligations_amount"] == 141355593.0
        assert self.r["current_overdue_amount"] == 0.0
        assert self.r["monthly_obligations_payment"] == 5133888.0

    def test_overdue_stats(self):
        assert self.r["max_overdue_principal_days"] == 21
        assert self.r["overdue_category"] == "до 30 дней"
        assert self.r["max_overdue_principal_amount"] == 1584764.0
        assert self.r["max_continuous_overdue_percent_days"] == 21

    def test_overdue_episodes(self):
        assert len(self.r["overdue_episodes"]) > 0
        assert self.r["last_overdue_date"] == "2025-10-07"

    def test_no_systematic_overdue(self):
        assert self.r["systematic_overdue"] is False
        assert self.r["overdue_31plus_last_12m"] == 0

    def test_closed_count(self):
        assert self.r["closed_obligations_count"] == 2

    def test_creditor_types(self):
        assert sorted(self.r["creditor_types"]) == ["BANK", "MMT"]

    def test_no_lombard(self):
        assert self.r["has_lombard"] is False

    def test_contracts_detail(self):
        assert len(self.r["contracts_detail"]) == 2

    def test_applications(self):
        assert len(self.r["open_applications"]) == 10


# ── Fixture 02: UZ legal entity (B2) ─────────────────────────────────────────


class TestUzLegalEntity:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.r = _load("02_uz_legal_entity.html")

    def test_entity_type_legal(self):
        """STIRi: in Section 1 keys → legal_entity."""
        assert self.r["entity_type"] == "legal_entity"

    def test_company_data(self):
        assert "DRAGON MOTORS" in self.r["company_name"]
        assert self.r["company_inn"] == "311365845"

    def test_no_individual_fields(self):
        assert "full_name" not in self.r
        assert "pinfl" not in self.r
        assert "birth_date" not in self.r

    def test_scoring(self):
        assert self.r["ki_score"] == "B2 / 338"
        assert self.r["scoring_class"] == "B"
        assert self.r["scoring_score"] == 338

    def test_obligations(self):
        assert self.r["obligations_count"] == 1
        assert self.r["total_obligations_amount"] == 0.0

    def test_no_overdue(self):
        assert self.r["max_overdue_principal_days"] == 0
        assert self.r["overdue_category"] == "до 30 дней"

    def test_closed(self):
        assert self.r["closed_obligations_count"] == 2

    def test_classification(self):
        assert self.r["worst_active_classification"] == "Standart"
        assert self.r["worst_closed_classification"] == "Standart"


# ── Fixture 03: UZ individual, no obligations ────────────────────────────────


class TestUzNoObligations:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.r = _load("03_uz_no_obligations.html")

    def test_entity_type(self):
        assert self.r["entity_type"] == "individual"

    def test_personal_data(self):
        assert self.r["full_name"] == "Hakimova Movjuda Amirovna"
        assert self.r["pinfl"] == "40504762560014"

    def test_no_obligations(self):
        assert self.r["has_current_obligations"] == "нет"
        assert self.r["obligations_count"] == 0

    def test_zero_overdue(self):
        assert self.r["max_overdue_principal_days"] == 0
        assert self.r["overdue_category"] == "до 30 дней"
        assert len(self.r["overdue_episodes"]) == 0

    def test_empty_creditor_types(self):
        assert self.r["creditor_types"] == []

    def test_no_contracts_detail(self):
        assert len(self.r["contracts_detail"]) == 0

    def test_applications_10d(self):
        """Single recent application within 10 days of report date."""
        assert self.r["open_applications_10d"] == 1


# ── Fixture 04: UZ individual, D1 class (overdue 31-60) ─────────────────────


class TestUzDClass:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.r = _load("04_uz_d_class.html")

    def test_scoring_d_class(self):
        assert self.r["scoring_class"] == "D"
        assert self.r["scoring_number"] == 1
        assert self.r["scoring_score"] == 133

    def test_overdue_31_60(self):
        assert self.r["max_overdue_principal_days"] == 39
        assert self.r["overdue_category"] == "31-60"

    def test_current_overdue_amount(self):
        assert self.r["current_overdue_amount"] == 31528746.0

    def test_systematic_overdue(self):
        """3+ episodes of 31+ days in last 12 months → systematic."""
        assert self.r["systematic_overdue"] is True
        assert self.r["overdue_31plus_last_12m"] >= 3

    def test_creditor_types_include_lombard(self):
        assert "LOMBARD" in self.r["creditor_types"]
        assert "BANK" in self.r["creditor_types"]

    def test_closed_obligations(self):
        assert self.r["closed_obligations_count"] == 7

    def test_large_portfolio(self):
        assert self.r["obligations_count"] == 4
        assert self.r["total_obligations_amount"] > 700_000_000

    def test_overdue_episodes(self):
        episodes = self.r["overdue_episodes"]
        assert len(episodes) > 100
        # Check episode structure
        ep = episodes[0]
        assert "date" in ep
        assert "days" in ep
        assert "amount" in ep
        assert "contract_num" in ep


# ── Fixture 05: UZ individual, large portfolio (A1, 46 contracts) ────────────


class TestUzLargePortfolio:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.r = _load("05_uz_large_portfolio.html")

    def test_scoring_excellent(self):
        assert self.r["scoring_class"] == "A"
        assert self.r["scoring_score"] == 401

    def test_many_active_contracts(self):
        """Section 5 table has 5 data rows → 5 active contracts (not 46)."""
        assert self.r["obligations_count"] == 5

    def test_many_closed_contracts(self):
        assert self.r["closed_obligations_count"] == 41

    def test_total_obligations(self):
        assert self.r["total_obligations_amount"] == 32229191.0
        assert self.r["monthly_obligations_payment"] == 6496439.0

    def test_no_current_overdue(self):
        assert self.r["current_overdue_amount"] == 0.0

    def test_overdue_under_30(self):
        assert self.r["max_overdue_principal_days"] == 14
        assert self.r["overdue_category"] == "до 30 дней"

    def test_no_systematic_overdue(self):
        assert self.r["systematic_overdue"] is False

    def test_contracts_detail_count(self):
        assert len(self.r["contracts_detail"]) == 5

    def test_many_applications(self):
        assert len(self.r["open_applications"]) == 59


# ── Fixture 06: RU individual, D2 class (90+ overdue) ───────────────────────


class TestRuD2Class:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.r = _load("06_ru_d2_class.html")

    def test_scoring_d2(self):
        assert self.r["scoring_class"] == "D"
        assert self.r["scoring_number"] == 2
        assert self.r["scoring_score"] == 143

    def test_severe_overdue(self):
        assert self.r["max_overdue_principal_days"] == 174
        assert self.r["overdue_category"] == "90+"

    def test_current_overdue(self):
        assert self.r["current_overdue_amount"] == 4024425.0

    def test_systematic_overdue(self):
        assert self.r["systematic_overdue"] is True
        assert self.r["overdue_31plus_last_12m"] > 100

    def test_classification_ru(self):
        assert self.r["worst_active_classification"] == "Стандартный"
        assert self.r["worst_closed_classification"] == "Стандартный"


# ── Cross-cutting tests ──────────────────────────────────────────────────────


class TestEntityTypeNotConfused:
    """Individuals with ИНН/STIRi in contracts (Section 7) must NOT be
    detected as legal entities. Only Section 1 keys matter."""

    def test_fixture_04_is_individual(self):
        """Fixture 04 has legal entity contracts but subject is individual."""
        r = _load("04_uz_d_class.html")
        assert r["entity_type"] == "individual"

    def test_fixture_06_is_individual(self):
        """Fixture 06 has legal entity contracts but subject is individual."""
        r = _load("06_ru_d2_class.html")
        assert r["entity_type"] == "individual"


class TestLanguageDetection:
    def test_uz_detected(self):
        r = _load("04_uz_d_class.html")
        # UZ reports have UZ classification values
        assert r["worst_active_classification"] == "Standart"

    def test_ru_detected(self):
        r = _load("01_ru_individual_clean.html")
        # RU reports have RU classification values
        assert r["worst_active_classification"] == "Стандартный"


class TestClassificationWorst:
    def test_standart_is_best(self):
        """When all contracts are Standart, worst = Standart."""
        r = _load("05_uz_large_portfolio.html")
        assert r["worst_active_classification"] == "Standart"

    def test_no_classification_returns_na(self):
        """When no contracts have classification, return н/д."""
        r = _load("03_uz_no_obligations.html")
        assert r["worst_active_classification"] == "н/д"


class TestOverdueEpisodes:
    def test_episodes_have_correct_structure(self):
        r = _load("06_ru_d2_class.html")
        assert len(r["overdue_episodes"]) > 0
        ep = r["overdue_episodes"][0]
        assert isinstance(ep["date"], str)
        assert isinstance(ep["days"], int)
        assert isinstance(ep["amount"], float)
        assert isinstance(ep["contract_num"], str)
        assert isinstance(ep["is_principal"], bool)

    def test_last_overdue_date(self):
        r = _load("06_ru_d2_class.html")
        assert r["last_overdue_date"] == "2025-11-28"


class TestOpenApplications10d:
    def test_recent_applications(self):
        r = _load("03_uz_no_obligations.html")
        assert r["open_applications_10d"] == 1

    def test_no_recent_applications(self):
        r = _load("01_ru_individual_clean.html")
        assert r["open_applications_10d"] == 0

    def test_d_class_applications(self):
        r = _load("04_uz_d_class.html")
        assert r["open_applications_10d"] == 3
