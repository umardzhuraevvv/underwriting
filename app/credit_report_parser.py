"""
Parser for InfoScore (CIAC) credit history HTML reports.
Supports both Uzbek and Russian languages, individual and legal entity reports.
Extracts credit-related fields and maps them to anketa fields.

V2: HTML-table-based parsing instead of text scanning.
Fixes: detect_language, detect_entity_type, active contracts counting.
New fields: report_date, scoring_class, current_overdue_amount,
worst_active/closed_classification, lombard, overdue_episodes, etc.
"""

import re
from datetime import datetime, timedelta
from typing import Optional

from bs4 import BeautifulSoup, Tag


# ── Text normalization ─────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    """Normalize Unicode quotes/apostrophes to ASCII for reliable matching."""
    return (
        s.replace("\u2018", "'").replace("\u2019", "'")
        .replace("\u201C", '"').replace("\u201D", '"')
        .replace("\u00AB", '"').replace("\u00BB", '"')
    )


# ── Constants ──────────────────────────────────────────────────────────────────

CLASSIFICATION_ORDER = {
    "Standart": 0, "Стандартный": 0,
    "Substandart": 1, "Субстандартный": 1,
    "Qoniqarsiz": 2,
    "Shubhali": 3, "Сомнительный": 3,
    "Umidsiz": 4, "Безнадежный": 4,
}

CREDITOR_TYPES_NORMALIZE = {
    "BANK": "BANK", "БАНК": "BANK",
    "MMT": "MMT", "МФО": "MMT",
    "LOMBARD": "LOMBARD", "ЛОМБАРД": "LOMBARD",
    "RITEYLER": "RETAILER", "РЕТЕЙЛЕР": "RETAILER",
    "LT": "LEASING", "ЛК": "LEASING",
}

CREDIT_TYPE_NORMALIZE = {
    # RU
    "Микрозаем": "Микрозаем",
    "Автокредит": "Автокредит",
    "Ипотека": "Ипотека",
    "Кредитная карта (с открытием кредитной линии)": "Кредитная карта",
    "Потребительский кредит": "Потребительский",
    # UZ
    "Mikroqarz": "Микрозаем",
    "Mikrokredit": "Микрозаем",
    "Ekspress kredit": "Экспресс-кредит",
    "Ipoteka krediti": "Ипотека",
    "Avtokredit": "Автокредит",
    "Kredit liniyasi ochilmagan holda berilgan kreditlar": "Кредит",
    "Ochiq kredit liniyasi orqali ajratilgan kredit karta": "Кредитная карта",
    "Iste'mol krediti": "Потребительский",
}


# ── Helper functions ─────────────────────────────────────────────────────────


def _clean_num(s: str) -> Optional[float]:
    """Remove spaces/non-numeric chars and parse float."""
    if not s:
        return None
    cleaned = re.sub(r"[^\d,.\-]", "", s.replace("\xa0", ""))
    cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except (ValueError, TypeError):
        return None


def _determine_overdue_category(max_days: Optional[int], overdue_count: int = 0) -> str:
    """Determine overdue category based on max overdue days."""
    if max_days is None or (max_days == 0 and overdue_count == 0):
        return "до 30 дней"
    if max_days <= 30:
        return "до 30 дней"
    if max_days <= 60:
        return "31-60"
    if max_days <= 90:
        return "61-90"
    return "90+"


def _worst_classification(classifications: list[str]) -> str:
    """Return the worst (highest risk) classification from a list."""
    worst = -1
    worst_name = "н/д"
    for c in classifications:
        order = CLASSIFICATION_ORDER.get(c, -1)
        if order > worst:
            worst = order
            worst_name = c
    return worst_name


def _find_step_row(soup: BeautifulSoup, section_num: str) -> Optional[Tag]:
    """Find the step-row div for a given section number (e.g. '5.')."""
    for step in soup.find_all("div", class_="step-row"):
        num_div = step.find("div", class_="step-row__num")
        if num_div and num_div.get_text(strip=True) == section_num:
            return step
    return None


def _find_section_table(soup: BeautifulSoup, section_num: str):
    """Find the table.table for a given section number.

    Returns (table_tag, is_no_data).
    """
    step = _find_step_row(soup, section_num)
    if not step:
        return None, True

    for sibling in step.next_siblings:
        if not isinstance(sibling, Tag):
            continue
        classes = sibling.get("class", [])
        # Stop at next main section header
        if "step-row" in classes and "bg-orange" not in classes:
            break
        if "no-data" in classes:
            return None, True
        # Table may be wrapped in a div.table-row
        if sibling.name == "div":
            tbl = sibling.find("table", class_="table")
            if tbl:
                return tbl, False
        if sibling.name == "table" and "table" in classes:
            return sibling, False

    return None, True


def _find_orange_bar(tag: Tag) -> Optional[Tag]:
    """Find nearest preceding orange bar (contract header)."""
    return tag.find_previous(
        lambda t: t.name == "div"
        and "step-row" in t.get("class", [])
        and "bg-orange" in t.get("class", [])
    )


# ── Language & entity type detection ─────────────────────────────────────────


def detect_language(soup: BeautifulSoup) -> str:
    """Detect report language using section-level markers (not header)."""
    for name_div in soup.find_all("div", class_="step-row__name"):
        text = name_div.get_text(strip=True)
        if "AMALDAGI SHARTNOMALAR" in text:
            return "uz"
        if "ДЕЙСТВУЮЩИЕ ДОГОВОРА" in text:
            return "ru"
    # Fallback: scoring labels
    scoring = soup.find("ul", class_="scoring-desc")
    if scoring:
        text = scoring.get_text()
        if "SKORING BALL" in text:
            return "uz"
        if "Скоринговый балл" in text:
            return "ru"
    return "uz"


def detect_entity_type(soup: BeautifulSoup) -> str:
    """Detect individual vs legal entity from Section 1 subject-info only."""
    keys_ul = soup.find("ul", class_="subject-info__keys")
    if not keys_ul:
        return "individual"

    keys = [_norm(li.get_text(strip=True)) for li in keys_ul.find_all("li")]

    for k in keys:
        if k in ("STIRi:", "ИНН:"):
            return "legal_entity"
    for k in keys:
        if k in ("JShShIR:", "ПИНФЛ:"):
            return "individual"

    # Fallback: check legal status value
    vals_ul = soup.find("ul", class_="subject-info__values")
    if vals_ul:
        for li in vals_ul.find_all("li"):
            text = _norm(li.get_text(strip=True))
            if "Yuridik shaxs" in text or "Юридическое лицо" in text:
                return "legal_entity"

    return "individual"


# ── Section parsers ──────────────────────────────────────────────────────────


def _parse_report_date(soup: BeautifulSoup) -> Optional[str]:
    """Extract report date from header (So'rov vaqti / Время запроса)."""
    for span in soup.find_all("span"):
        text = span.get_text(strip=True)
        if "vaqti:" in text.lower() or "запроса:" in text.lower():
            parent = span.parent
            if parent:
                m = re.search(r"(\d{4}-\d{2}-\d{2})", parent.get_text())
                if m:
                    return m.group(1)
    return None


def _parse_personal_data(soup: BeautifulSoup, lang: str, entity_type: str) -> dict:
    """Parse Section 1: personal data from subject-info key/value lists."""
    result = {}

    keys_ul = soup.find("ul", class_="subject-info__keys")
    vals_ul = soup.find("ul", class_="subject-info__values")
    if not keys_ul or not vals_ul:
        return result

    keys = [_norm(li.get_text(strip=True)) for li in keys_ul.find_all("li")]
    val_lis = vals_ul.find_all("li")

    def _get_val(label: str) -> Optional[str]:
        for i, k in enumerate(keys):
            if k == label and i < len(val_lis):
                b = val_lis[i].find("b")
                return _norm(b.get_text(strip=True)) if b else _norm(val_lis[i].get_text(strip=True))
        return None

    if entity_type == "individual":
        name_label = "F.I.O.:" if lang == "uz" else "Наименование:"
        pinfl_label = "JShShIR:" if lang == "uz" else "ПИНФЛ:"
        birth_label = "Tug'ilgan sana:" if lang == "uz" else "Дата рождения:"

        name = _get_val(name_label)
        if name:
            result["full_name"] = name

        pinfl = _get_val(pinfl_label)
        if pinfl:
            pinfl_clean = re.sub(r"\s+", "", pinfl)
            if re.match(r"^\d{14}$", pinfl_clean):
                result["pinfl"] = pinfl_clean

        birth = _get_val(birth_label)
        if birth:
            m = re.match(r"(\d{4}-\d{2}-\d{2})", birth)
            if m:
                result["birth_date"] = m.group(1)
    else:
        name_label = "Nomi:" if lang == "uz" else "Наименование:"
        inn_label = "STIRi:" if lang == "uz" else "ИНН:"

        name = _get_val(name_label)
        if name:
            result["company_name"] = name

        inn = _get_val(inn_label)
        if inn:
            inn_clean = re.sub(r"\s+", "", inn)
            if re.match(r"^\d+$", inn_clean):
                result["company_inn"] = inn_clean

    return result


def _parse_scoring(soup: BeautifulSoup) -> dict:
    """Parse Section 2: scoring data from DOM elements."""
    result = {}

    # Score from h2#score_text
    score_el = soup.find("h2", id="score_text")
    score_val = None
    if score_el:
        raw = score_el.get_text(strip=True)
        if re.match(r"^\d+$", raw):
            score_val = int(raw)

    # Class from div.scoring-ball__lvl
    class_el = soup.find("div", class_="scoring-ball__lvl")
    class_val = None
    if class_el:
        raw = class_el.get_text(strip=True)
        if re.match(r"^[A-F]\d+$", raw):
            class_val = raw

    if class_val:
        m = re.match(r"([A-F])(\d+)", class_val)
        if m:
            result["scoring_class"] = m.group(1)
            result["scoring_number"] = int(m.group(2))

        if score_val is not None:
            result["ki_score"] = f"{class_val} / {score_val}"
            result["scoring_score"] = score_val
        else:
            result["ki_score"] = class_val

    return result


def _parse_claims(soup: BeautifulSoup, lang: str) -> dict:
    """Parse Section 4: summary statistics from claims-item elements."""
    result = {}
    overdue_count = 0

    labels = {
        "uz": {
            "overdue_count": "asosiy qarz (aq) bo'yicha muddati o'tgan to'lovlar soni",
            "overdue_days": "muddati o'tgan aq maksimal kuni",
            "overdue_amount": "muddati o'tgan aq maksimal summasi",
            "overdue_pct_days": "uzluksiz muddati o'tgan foiz to'lovlarining maksimal kuni",
            "overdue_pct_amount": "muddati o'tgan foiz to'lovlarining maksimal summasi",
        },
        "ru": {
            "overdue_count": "количество просрочек основного долга (од)",
            "overdue_days": "максимальная просрочка од (дни)",
            "overdue_amount": "максимальная просрочка од (сумма)",
            "overdue_pct_days": "максимальная непрерывная просрочка % (дни)",
            "overdue_pct_amount": "максимальная просрочка % (сумма)",
        },
    }
    L = labels[lang]

    for item in soup.find_all("div", class_="claims-item"):
        num_el = item.find("b", class_="claims-item__num")
        title_el = item.find("div", class_="claims-item__title")
        if not num_el or not title_el:
            continue

        val = _clean_num(num_el.get_text(strip=True))
        title = _norm(title_el.get_text(strip=True)).lower()
        if val is None:
            continue

        if L["overdue_count"] in title:
            overdue_count = int(val)
        elif L["overdue_days"] in title:
            result["max_overdue_principal_days"] = int(val)
        elif L["overdue_amount"] in title:
            result["max_overdue_principal_amount"] = val
        elif L["overdue_pct_days"] in title:
            result["max_continuous_overdue_percent_days"] = int(val)
        elif L["overdue_pct_amount"] in title:
            result["max_overdue_percent_amount"] = val

    max_days = result.get("max_overdue_principal_days")
    result["overdue_category"] = _determine_overdue_category(max_days, overdue_count)

    result.setdefault("max_overdue_principal_days", 0)
    result.setdefault("max_overdue_principal_amount", 0.0)
    result.setdefault("max_continuous_overdue_percent_days", 0)
    result.setdefault("max_overdue_percent_amount", 0.0)

    return result


def _parse_active_contracts(soup: BeautifulSoup, lang: str) -> dict:
    """Parse Section 5: active contracts table via HTML table parsing."""
    result = {}

    table, is_no_data = _find_section_table(soup, "5.")
    if is_no_data or not table:
        result["has_current_obligations"] = "нет"
        result["obligations_count"] = 0
        result["_contracts_from_table"] = []
        return result

    tbody = table.find("tbody")
    if not tbody:
        result["has_current_obligations"] = "нет"
        result["obligations_count"] = 0
        result["_contracts_from_table"] = []
        return result

    rows = tbody.find_all("tr")
    total_label = "Jami" if lang == "uz" else "Итого"

    data_rows = []
    jami_cells = None

    for row in rows:
        cells = row.find_all("td")
        if not cells:
            continue
        if total_label in row.get_text():
            jami_cells = cells
            continue
        first = cells[0].get_text(strip=True)
        if re.match(r"^\d+$", first):
            data_rows.append(cells)

    count = len(data_rows)
    result["has_current_obligations"] = "есть" if count > 0 else "нет"
    result["obligations_count"] = count

    # Jami row: [N, creditor, contract#, currency, balance, overdue, monthly]
    if jami_cells and len(jami_cells) >= 7:
        balance = _clean_num(jami_cells[4].get_text(strip=True))
        overdue = _clean_num(jami_cells[5].get_text(strip=True))
        monthly = _clean_num(jami_cells[6].get_text(strip=True))
        if balance is not None:
            result["total_obligations_amount"] = balance
        if overdue is not None:
            result["current_overdue_amount"] = overdue
        if monthly is not None:
            result["monthly_obligations_payment"] = monthly

    # Per-contract data from table rows
    contracts = []
    for cells in data_rows:
        if len(cells) >= 7:
            contracts.append({
                "creditor": cells[1].get_text(strip=True),
                "contract_num": cells[2].get_text(strip=True),
                "currency": cells[3].get_text(strip=True),
                "balance": _clean_num(cells[4].get_text(strip=True)) or 0.0,
                "overdue": _clean_num(cells[5].get_text(strip=True)) or 0.0,
                "monthly": _clean_num(cells[6].get_text(strip=True)) or 0.0,
            })
    result["_contracts_from_table"] = contracts

    return result


def _parse_contract_details(soup: BeautifulSoup, lang: str) -> dict:
    """Parse Section 7.x/10.x: contract details from orange bars."""
    result = {}

    active_classifications = []
    closed_classifications = []
    creditor_types_set = set()
    lombard_count = 0
    details = []

    for bar in soup.find_all(
        lambda t: t.name == "div"
        and "step-row" in t.get("class", [])
        and "bg-orange" in t.get("class", [])
    ):
        # Creditor name
        name_div = bar.find("div", class_="step-row__name")
        creditor_name = ""
        if name_div:
            span = name_div.find("span", class_="color--black")
            if span:
                creditor_name = span.get_text(strip=True)

        # Creditor type
        type_div = bar.find("div", class_="step-row__type")
        raw_type = ""
        if type_div:
            b_tags = type_div.find_all("b")
            if len(b_tags) >= 2:
                raw_type = b_tags[1].get_text(strip=True)
        norm_type = CREDITOR_TYPES_NORMALIZE.get(raw_type, "")
        if norm_type:
            creditor_types_set.add(norm_type)

        is_lombard = (
            norm_type == "LOMBARD"
            or "LOMBARD" in creditor_name.upper()
            or "ЛОМБАРД" in creditor_name.upper()
        )

        # Status, classification, credit_type from the .list div
        next_list = bar.find_next_sibling("div", class_="list")
        status = "unknown"
        classification = "н/д"
        contract_num = ""
        credit_type = ""

        if next_list:
            for item_div in next_list.find_all("div", class_="item-title"):
                text = _norm(item_div.get_text())
                b = item_div.find("b")
                val = _norm(b.get_text(strip=True)) if b else ""

                if "Shartnoma holati" in text or "Статус договора" in text:
                    if val in ("Ochiq", "Открыт"):
                        status = "open"
                    elif "Yopiq" in val or "Закрыт" in val:
                        status = "closed"

                if "Aktivlar sifati" in text or "Класс качества" in text:
                    if val:
                        classification = val

                if "Shartnoma raqami" in text or "Номер договора" in text:
                    if val:
                        contract_num = val

                if "Kredit turi" in text or "Вид кредита" in text:
                    if val:
                        credit_type = CREDIT_TYPE_NORMALIZE.get(val, val)

        if classification != "н/д":
            if status == "open":
                active_classifications.append(classification)
            elif status == "closed":
                closed_classifications.append(classification)

        if is_lombard and status == "open":
            lombard_count += 1

        details.append({
            "creditor": creditor_name,
            "creditor_type": norm_type,
            "credit_type": credit_type,
            "status": status,
            "classification": classification,
            "contract_num": contract_num,
        })

    result["worst_active_classification"] = (
        _worst_classification(active_classifications) if active_classifications else "н/д"
    )
    result["worst_closed_classification"] = (
        _worst_classification(closed_classifications) if closed_classifications else "н/д"
    )
    result["has_lombard"] = lombard_count > 0
    result["lombard_count"] = lombard_count
    result["creditor_types"] = sorted(creditor_types_set)
    result["_contracts_detail_raw"] = details

    return result


def _parse_overdue_tables(soup: BeautifulSoup) -> dict:
    """Parse all overdue-table elements for overdue episodes."""
    result = {}
    episodes = []
    seen = set()

    for ot in soup.find_all("table", class_="overdue-table"):
        # Find associated contract number from nearest preceding orange bar
        contract_num = ""
        bar = _find_orange_bar(ot)
        if bar:
            next_list = bar.find_next_sibling("div", class_="list")
            if next_list:
                for item_div in next_list.find_all("div", class_="item-title"):
                    text = _norm(item_div.get_text())
                    if "Shartnoma raqami" in text or "Номер договора" in text:
                        b = item_div.find("b")
                        if b:
                            contract_num = _norm(b.get_text(strip=True))
                        break

        # Is this principal or interest overdue?
        step_line = ot.find_previous("div", class_="step-line")
        is_principal = True
        if step_line:
            title_div = step_line.find("div", class_="step-line__title")
            if title_div:
                t = title_div.get_text(strip=True).lower()
                if "foiz" in t or "процент" in t:
                    is_principal = False

        for tr in ot.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 4:
                continue

            date_text = cells[1].get_text(strip=True)
            days_text = cells[2].get_text(strip=True)
            amount_text = cells[3].get_text(strip=True)

            m_date = re.search(r"(\d{4}-\d{2}-\d{2})", date_text)
            days = _clean_num(days_text)
            amount = _clean_num(amount_text)

            if m_date and days is not None:
                key = (m_date.group(1), int(days), amount or 0.0, contract_num)
                if key not in seen:
                    seen.add(key)
                    episodes.append({
                        "date": m_date.group(1),
                        "days": int(days),
                        "amount": amount or 0.0,
                        "contract_num": contract_num,
                        "is_principal": is_principal,
                    })

    result["overdue_episodes"] = episodes

    if episodes:
        dates = [e["date"] for e in episodes]
        result["last_overdue_date"] = max(dates)

    return result


def _parse_applications(soup: BeautifulSoup, lang: str) -> dict:
    """Parse Section 6: applications without contracts."""
    result = {}

    table, is_no_data = _find_section_table(soup, "6.")
    if is_no_data or not table:
        result["open_applications"] = []
        return result

    tbody = table.find("tbody")
    if not tbody:
        result["open_applications"] = []
        return result

    # Detect column count from header
    thead = table.find("thead")
    num_cols = 0
    if thead:
        num_cols = len(thead.find_all("th"))

    applications = []
    for row in tbody.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 6:
            continue
        first = cells[0].get_text(strip=True)
        if not re.match(r"^\d+$", first):
            continue

        creditor = cells[1].get_text(strip=True)
        date_text = cells[3].get_text(strip=True)

        if num_cols >= 9:
            # RU 9-col format: amount+currency combined in col 6
            combined = cells[6].get_text(strip=True)
            amount_match = re.search(r"([\d\s,.]+)", combined)
            amount = _clean_num(amount_match.group(1)) if amount_match else 0.0
            currency = "UZS"
            if "USD" in combined:
                currency = "USD"
            elif "EUR" in combined:
                currency = "EUR"
        else:
            # UZ or old-RU 8-col: currency=col4, amount=col5
            currency = cells[4].get_text(strip=True)
            amount = _clean_num(cells[5].get_text(strip=True))
            if currency in ("So'm", "Сум", "So`m"):
                currency = "UZS"

        m_date = re.search(r"(\d{4}-\d{2}-\d{2})", date_text)
        applications.append({
            "date": m_date.group(1) if m_date else None,
            "amount": amount or 0.0,
            "creditor": creditor,
            "currency": currency,
        })

    result["open_applications"] = applications
    return result


def _count_closed_contracts(soup: BeautifulSoup) -> int:
    """Count closed contracts from contract detail status fields."""
    count = 0
    for bar in soup.find_all(
        lambda t: t.name == "div"
        and "step-row" in t.get("class", [])
        and "bg-orange" in t.get("class", [])
    ):
        next_list = bar.find_next_sibling("div", class_="list")
        if not next_list:
            continue
        for item_div in next_list.find_all("div", class_="item-title"):
            text = _norm(item_div.get_text())
            if "Shartnoma holati" in text or "Статус договора" in text:
                b = item_div.find("b")
                if b:
                    val = _norm(b.get_text(strip=True))
                    if "Yopiq" in val or "Закрыт" in val:
                        count += 1
                break
    return count


def _merge_contracts(table_data: list, detail_data: list) -> list:
    """Merge Section 5 table data with Section 7.x detail data."""
    detail_by_num = {}
    for d in detail_data:
        if d.get("contract_num"):
            detail_by_num[d["contract_num"]] = d

    merged = []
    for td in table_data:
        contract_num = td.get("contract_num", "")
        detail = detail_by_num.get(contract_num, {})
        merged.append({
            "creditor": td.get("creditor", ""),
            "creditor_type": detail.get("creditor_type", ""),
            "credit_type": detail.get("credit_type", ""),
            "status": detail.get("status", "open"),
            "classification": detail.get("classification", "н/д"),
            "balance": td.get("balance", 0.0),
            "overdue": td.get("overdue", 0.0),
            "monthly": td.get("monthly", 0.0),
        })
    return merged


def _compute_overdue_summary(result: dict):
    """Aggregate overdue_episodes into summary by category and time period.

    Categories: до 30 дней, 31-60 дней, 61-90 дней, 90+ дней.
    Periods counted from report_date: total, last_6m, last_12m, last_24m.
    """
    episodes = result.get("overdue_episodes", [])
    report_date = result.get("report_date")

    categories = ["до 30 дней", "31-60 дней", "61-90 дней", "90+ дней"]

    def _empty_bucket():
        return {"total": 0, "last_6m": 0, "last_12m": 0, "last_24m": 0,
                "max_amount": 0.0, "last_date": None,
                "last_date_6m": None, "last_date_12m": None, "last_date_24m": None}

    if not episodes or not report_date:
        result["overdue_summary"] = {cat: _empty_bucket() for cat in categories}
        return

    try:
        rd = datetime.strptime(report_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        result["overdue_summary"] = {cat: _empty_bucket() for cat in categories}
        return

    cutoff_6m = rd - timedelta(days=183)
    cutoff_12m = rd - timedelta(days=365)
    cutoff_24m = rd - timedelta(days=730)

    summary = {cat: _empty_bucket() for cat in categories}

    for ep in episodes:
        days = ep.get("days", 0)
        amount = ep.get("amount", 0.0) or 0.0
        ep_date_str = ep.get("date")

        if days <= 30:
            cat = "до 30 дней"
        elif days <= 60:
            cat = "31-60 дней"
        elif days <= 90:
            cat = "61-90 дней"
        else:
            cat = "90+ дней"

        bucket = summary[cat]
        bucket["total"] += 1

        if amount > bucket["max_amount"]:
            bucket["max_amount"] = amount

        if ep_date_str:
            if bucket["last_date"] is None or ep_date_str > bucket["last_date"]:
                bucket["last_date"] = ep_date_str

            try:
                ep_date = datetime.strptime(ep_date_str, "%Y-%m-%d")
                if ep_date >= cutoff_6m:
                    bucket["last_6m"] += 1
                    if bucket["last_date_6m"] is None or ep_date_str > bucket["last_date_6m"]:
                        bucket["last_date_6m"] = ep_date_str
                if ep_date >= cutoff_12m:
                    bucket["last_12m"] += 1
                    if bucket["last_date_12m"] is None or ep_date_str > bucket["last_date_12m"]:
                        bucket["last_date_12m"] = ep_date_str
                if ep_date >= cutoff_24m:
                    bucket["last_24m"] += 1
                    if bucket["last_date_24m"] is None or ep_date_str > bucket["last_date_24m"]:
                        bucket["last_date_24m"] = ep_date_str
            except (ValueError, TypeError):
                pass

    result["overdue_summary"] = summary


def _compute_overdue_derived(result: dict):
    """Compute systematic_overdue and overdue_31plus_last_12m."""
    episodes = result.get("overdue_episodes", [])
    report_date = result.get("report_date")

    if not report_date or not episodes:
        result.setdefault("overdue_31plus_last_12m", 0)
        result.setdefault("systematic_overdue", False)
        return

    try:
        rd = datetime.strptime(report_date, "%Y-%m-%d")
    except (ValueError, TypeError):
        result.setdefault("overdue_31plus_last_12m", 0)
        result.setdefault("systematic_overdue", False)
        return

    cutoff = rd - timedelta(days=365)
    count_31plus = 0

    for ep in episodes:
        if ep.get("days", 0) >= 31 and ep.get("date"):
            try:
                ep_date = datetime.strptime(ep["date"], "%Y-%m-%d")
                if ep_date >= cutoff:
                    count_31plus += 1
            except (ValueError, TypeError):
                pass

    result["overdue_31plus_last_12m"] = count_31plus
    result["systematic_overdue"] = count_31plus >= 3


# ── Main parser ──────────────────────────────────────────────────────────────


def parse_infoscore_html(html_content: str) -> dict:
    """
    Parse InfoScore/CIAC credit history HTML report.

    Returns a dict with:
      - entity_type: "individual" or "legal_entity"
      - All extracted anketa-compatible fields
      - New v2 fields: report_date, scoring_class, current_overdue_amount, etc.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    result = {}

    lang = detect_language(soup)
    entity_type = detect_entity_type(soup)
    result["entity_type"] = entity_type

    # Report date
    result["report_date"] = _parse_report_date(soup)

    # Section 1: Personal data
    result.update(_parse_personal_data(soup, lang, entity_type))

    # Section 2: Scoring
    result.update(_parse_scoring(soup))

    # Section 4: Claims (summary statistics)
    result.update(_parse_claims(soup, lang))

    # Section 5: Active contracts
    active = _parse_active_contracts(soup, lang)
    contracts_from_table = active.pop("_contracts_from_table", [])
    result.update(active)

    # Section 7/10: Contract details
    details = _parse_contract_details(soup, lang)
    detail_raw = details.pop("_contracts_detail_raw", [])
    result.update(details)

    # Merge table + detail data
    result["contracts_detail"] = _merge_contracts(contracts_from_table, detail_raw)

    # Section 6: Applications
    result.update(_parse_applications(soup, lang))

    # Applications in last 10 days
    report_date = result.get("report_date")
    apps = result.get("open_applications", [])
    if report_date and apps:
        try:
            rd = datetime.strptime(report_date, "%Y-%m-%d")
            cutoff = rd - timedelta(days=10)
            result["open_applications_10d"] = sum(
                1 for a in apps
                if a.get("date") and datetime.strptime(a["date"], "%Y-%m-%d") >= cutoff
            )
        except (ValueError, TypeError):
            result["open_applications_10d"] = 0
    else:
        result["open_applications_10d"] = 0

    # Overdue episodes
    result.update(_parse_overdue_tables(soup))

    # Closed contracts count
    result["closed_obligations_count"] = _count_closed_contracts(soup)

    # Overdue summary by category
    _compute_overdue_summary(result)

    # Derived overdue fields
    _compute_overdue_derived(result)

    return result
