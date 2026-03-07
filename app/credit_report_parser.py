"""
Parser for InfoScore (CIAC) credit history HTML reports.
Supports both Uzbek and Russian languages, individual and legal entity reports.
Extracts credit-related fields and maps them to anketa fields.
"""

import re
from typing import Optional

from bs4 import BeautifulSoup


def _norm(s: str) -> str:
    """Normalize Unicode quotes/apostrophes to ASCII for reliable matching."""
    return s.replace("\u2018", "'").replace("\u2019", "'").replace("\u201C", '"').replace("\u201D", '"').replace("\u00AB", '"').replace("\u00BB", '"')


# ── Label dictionaries per language ──────────────────────────────────────────

LABELS = {
    "uz": {
        "full_name": "F.I.O.:",
        "pinfl": "JShShIR:",
        "birth_date": "Tug'ilgan sana:",
        "entity_name": "Nomi:",
        "inn": "STIRi:",
        "score_label": "SKORING BALL:",
        "class_label": "BAHOLASH SINFI:",
        "active_section": "AMALDAGI SHARTNOMALAR",
        "total_row": "Jami",
        "no_contracts": "Mavjud emas",
        "closed": "Yopiq",
        "overdue_count": "asosiy qarz (AQ) bo'yicha muddati o'tgan to'lovlar soni",
        "overdue_days": "muddati o'tgan AQ maksimal kuni",
        "overdue_amount": "muddati o'tgan AQ maksimal summasi",
        "overdue_pct_days": "uzluksiz muddati o'tgan foiz to'lovlarining maksimal kuni",
        "overdue_pct_amount": "muddati o'tgan foiz to'lovlarining maksimal summasi",
        "overdue_principal_marker": "asosiy qarz bo'yicha muddati o'tgan to'lovlar",
        "overdue_percent_marker": "foiz bo'yicha muddati o'tgan to'lovlar",
    },
    "ru": {
        "full_name": "Наименование:",
        "pinfl": "ПИНФЛ:",
        "birth_date": "Дата рождения:",
        "entity_name": "Наименование:",
        "inn": "ИНН:",
        "score_label": "Скоринговый балл:",
        "class_label": "Класс оценки:",
        "active_section": "ДЕЙСТВУЮЩИЕ ДОГОВОРА",
        "total_row": "Итого",
        "no_contracts": "Не имеется",
        "closed": "Закрыт",
        "overdue_count": "количество просрочек основного долга (ОД)",
        "overdue_days": "максимальная просрочка ОД (дни)",
        "overdue_amount": "максимальная просрочка ОД (сумма)",
        "overdue_pct_days": "максимальная непрерывная просрочка % (дни)",
        "overdue_pct_amount": "максимальная просрочка % (сумма)",
        "overdue_principal_marker": "просроченные платежи основного долга",
        "overdue_percent_marker": "просроченные платежи процента",
    },
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


def detect_language(texts: list[str]) -> str:
    """Detect report language from first text element."""
    if texts and any("СУБЪЕКТ КРЕДИТНОЙ" in t or "Кредитное бюро" in t for t in texts[:5]):
        return "ru"
    return "uz"


def detect_entity_type(texts: list[str]) -> str:
    """Detect individual vs legal entity."""
    for t in texts:
        if t in ("STIRi:", "ИНН:"):
            return "legal_entity"
    for t in texts:
        if t in ("JShShIR:", "ПИНФЛ:"):
            return "individual"
    for t in texts:
        if t in ("Yuridik shaxs", "Юридическое лицо"):
            return "legal_entity"
    return "individual"


# ── Main parser ──────────────────────────────────────────────────────────────


def parse_infoscore_html(html_content: str) -> dict:
    """
    Parse InfoScore/CIAC credit history HTML report.

    Returns a dict with:
      - entity_type: "individual" or "legal_entity"
      - All extracted anketa-compatible fields
    """
    soup = BeautifulSoup(html_content, "html.parser")
    result = {}

    texts = [_norm(t.strip()) for t in soup.stripped_strings if t.strip()]
    if not texts:
        return result

    lang = detect_language(texts)
    entity_type = detect_entity_type(texts)
    L = LABELS[lang]

    result["entity_type"] = entity_type

    # ── 1. Personal data (Section 1) ─────────────────────────────────────

    def _find_value_after_label(label: str) -> Optional[str]:
        """Find label in texts, return the text element after it."""
        for i, t in enumerate(texts):
            if t.strip() == label:
                if i + 1 < len(texts):
                    return texts[i + 1].strip()
        return None

    # Section 1 uses a block layout: all labels first, then all values.
    # Labels start at index ~26. We find the label indices and then map
    # values by offset from the end of labels block.

    if entity_type == "individual":
        # Individual: F.I.O / JShShIR / Birth date
        # Find the label block and extract by position
        label_list_uz = [
            "F.I.O.:", "JShShIR:", "Tug'ilgan sana:", "Jinsi:",
            "Huquqiy maqomi:", "Ro'yhatdan o'tgan manzili:",
            "Yashash manzili:", "Telefon raqami:", "Elektron pochtasi:",
        ]
        label_list_ru = [
            "Наименование:", "ПИНФЛ:", "Дата рождения:", "Пол:",
            "Юридический статус:", "Адрес по прописке:",
            "Адрес проживания:", "Номер телефона:", "Электронная почта:",
        ]
        label_list = label_list_uz if lang == "uz" else label_list_ru

        # Find where the first label appears
        first_label_idx = None
        for i, t in enumerate(texts):
            if t == label_list[0]:
                first_label_idx = i
                break

        if first_label_idx is not None:
            # Count consecutive labels
            num_labels = 0
            for j in range(first_label_idx, min(first_label_idx + 15, len(texts))):
                if texts[j] in label_list:
                    num_labels += 1

            # Values start right after all labels
            val_start = first_label_idx + num_labels

            # Map: label_index → value_index
            label_positions = {}
            label_idx = 0
            for j in range(first_label_idx, first_label_idx + num_labels):
                if texts[j] in label_list:
                    label_positions[texts[j]] = label_idx
                    label_idx += 1

            # Extract values
            name_label = L["full_name"]
            if name_label in label_positions and val_start + label_positions[name_label] < len(texts):
                result["full_name"] = texts[val_start + label_positions[name_label]]

            pinfl_label = L["pinfl"]
            if pinfl_label in label_positions and val_start + label_positions[pinfl_label] < len(texts):
                pinfl_raw = texts[val_start + label_positions[pinfl_label]]
                pinfl_clean = re.sub(r"\s+", "", pinfl_raw)
                if re.match(r"^\d{14}$", pinfl_clean):
                    result["pinfl"] = pinfl_clean

            birth_label = L["birth_date"]
            if birth_label in label_positions and val_start + label_positions[birth_label] < len(texts):
                birth_raw = texts[val_start + label_positions[birth_label]]
                m = re.match(r"(\d{4}-\d{2}-\d{2})", birth_raw)
                if m:
                    result["birth_date"] = m.group(1)

    else:
        # Legal entity: Nomi / STIRi
        label_list_uz = [
            "Nomi:", "Huquqiy maqomi:", "STIRi:", "IFUT:",
            "Ro'yhatdan o'tgan manzili:", "Joylashgan manzili:",
            "Ta'sischilar:", "Telefon raqami:", "Elektron pochtasi:",
        ]
        label_list_ru = [
            "Наименование:", "Юридический статус:", "ИНН:", "ОКЭД:",
            "Адрес регистрации:", "Адрес местонахождения:",
            "Учредители:", "Номер телефона:", "Электронная почта:",
        ]
        label_list = label_list_uz if lang == "uz" else label_list_ru

        first_label_idx = None
        for i, t in enumerate(texts):
            if t == label_list[0]:
                first_label_idx = i
                break

        if first_label_idx is not None:
            num_labels = 0
            for j in range(first_label_idx, min(first_label_idx + 15, len(texts))):
                if texts[j] in label_list:
                    num_labels += 1

            val_start = first_label_idx + num_labels

            label_positions = {}
            label_idx = 0
            for j in range(first_label_idx, first_label_idx + num_labels):
                if texts[j] in label_list:
                    label_positions[texts[j]] = label_idx
                    label_idx += 1

            # Company name
            name_label = L["entity_name"]
            if name_label in label_positions and val_start + label_positions[name_label] < len(texts):
                result["company_name"] = texts[val_start + label_positions[name_label]]

            # INN
            inn_label = L["inn"]
            if inn_label in label_positions and val_start + label_positions[inn_label] < len(texts):
                inn_raw = texts[val_start + label_positions[inn_label]]
                inn_clean = re.sub(r"\s+", "", inn_raw)
                if re.match(r"^\d+$", inn_clean):
                    result["company_inn"] = inn_clean

    # ── 2. Scoring (Section 2) — ki_score ────────────────────────────────

    score_val = None
    class_val = None

    score_label = L["score_label"]
    class_label = L["class_label"]

    for i, t in enumerate(texts):
        if t == score_label and i + 1 < len(texts):
            raw = texts[i + 1].strip()
            if re.match(r"^\d+$", raw):
                score_val = raw
        elif t == class_label and i + 1 < len(texts):
            raw = texts[i + 1].strip()
            m = re.match(r"([A-Z]\d+)", raw)
            if m:
                class_val = m.group(1)

    if class_val:
        if score_val:
            result["ki_score"] = f"{class_val} / {score_val}"
        else:
            result["ki_score"] = class_val

    # ── 3. Summary statistics (Section 4) ────────────────────────────────
    # Pattern: value, '-', label (match by label text)

    overdue_count_internal = 0

    for i, t in enumerate(texts):
        t_lower = t.lower().strip()

        if L["overdue_count"].lower() in t_lower:
            if i >= 2:
                val = _clean_num(texts[i - 2])
                if val is not None:
                    overdue_count_internal = int(val)

        elif L["overdue_days"].lower() in t_lower:
            if i >= 2:
                val = _clean_num(texts[i - 2])
                if val is not None:
                    result["max_overdue_principal_days"] = int(val)

        elif L["overdue_amount"].lower() in t_lower:
            if i >= 2:
                val = _clean_num(texts[i - 2])
                if val is not None:
                    result["max_overdue_principal_amount"] = val

        elif L["overdue_pct_days"].lower() in t_lower:
            if i >= 2:
                val = _clean_num(texts[i - 2])
                if val is not None:
                    result["max_continuous_overdue_percent_days"] = int(val)

        elif L["overdue_pct_amount"].lower() in t_lower:
            if i >= 2:
                val = _clean_num(texts[i - 2])
                if val is not None:
                    result["max_overdue_percent_amount"] = val

    # ── 4. Active contracts (Section 5) ──────────────────────────────────

    active_count = 0
    total_balance = None
    total_monthly = None

    # Find active section
    active_section_idx = None
    for i, t in enumerate(texts):
        if L["active_section"] in t:
            active_section_idx = i
            break

    if active_section_idx is not None:
        # Check for "no contracts"
        no_contracts = L["no_contracts"]
        if no_contracts and active_section_idx + 2 < len(texts):
            # Check within next 5 elements
            for j in range(active_section_idx + 1, min(active_section_idx + 6, len(texts))):
                if texts[j] == no_contracts:
                    result["has_current_obligations"] = "нет"
                    result["obligations_count"] = 0
                    break

        # Find Jami/Итого row for totals
        total_label = L["total_row"]
        for i in range(active_section_idx, min(active_section_idx + 200, len(texts))):
            if texts[i] == total_label:
                # After Jami: total_balance, overdue_amount, monthly_total
                if i + 3 < len(texts):
                    bal = _clean_num(texts[i + 1])
                    monthly = _clean_num(texts[i + 3])
                    if bal is not None:
                        total_balance = bal
                    if monthly is not None:
                        total_monthly = monthly
                break

        # Count active contracts by finding the max row number before Jami/Итого
        # Table header indicators
        if "has_current_obligations" not in result:
            in_table_header = False
            table_started = False
            for i in range(active_section_idx + 1, min(active_section_idx + 200, len(texts))):
                t = texts[i]
                if t == total_label:
                    break
                # Detect next major section (e.g. "6.")
                if re.match(r"^\d+\.$", t):
                    break
                # Look for table header "№" to know table started
                if t == "№":
                    table_started = True
                    continue
                # After table starts, small integers (1-99) followed by a text = row numbers
                if table_started and re.match(r"^[1-9]\d?$", t):
                    num = int(t)
                    if num > active_count and num < 100:
                        active_count = num

    if total_balance is not None:
        result["total_obligations_amount"] = total_balance
    if total_monthly is not None:
        result["monthly_obligations_payment"] = total_monthly

    if "has_current_obligations" not in result:
        if active_count > 0:
            result["has_current_obligations"] = "есть"
            result["obligations_count"] = active_count
        else:
            result["has_current_obligations"] = "нет"
            result["obligations_count"] = 0

    # ── 5. Closed contracts count ────────────────────────────────────────

    closed_uz = sum(1 for t in texts if t == "Yopiq")
    closed_ru = sum(1 for t in texts if t == "Закрыт")
    result["closed_obligations_count"] = closed_uz + closed_ru

    # ── 6. Last overdue date ─────────────────────────────────────────────

    overdue_dates = []
    for i, t in enumerate(texts):
        t_lower = t.lower()
        is_overdue_marker = (
            L["overdue_principal_marker"].lower() in t_lower
            or L["overdue_percent_marker"].lower() in t_lower
        )
        if is_overdue_marker:
            # Look for dates in surrounding context (before and after)
            for j in range(max(0, i - 3), min(len(texts), i + 15)):
                m = re.search(r"\[?(\d{4}-\d{2}-\d{2})\]?", texts[j])
                if m:
                    overdue_dates.append(m.group(1))

    if overdue_dates:
        result["last_overdue_date"] = max(overdue_dates)

    # ── 7. Overdue category ──────────────────────────────────────────────

    max_days = result.get("max_overdue_principal_days")
    result["overdue_category"] = _determine_overdue_category(max_days, overdue_count_internal)

    # Set defaults for zero overdue fields
    if "max_overdue_principal_days" not in result:
        result["max_overdue_principal_days"] = 0
    if "max_overdue_principal_amount" not in result:
        result["max_overdue_principal_amount"] = 0.0
    if "max_continuous_overdue_percent_days" not in result:
        result["max_continuous_overdue_percent_days"] = 0
    if "max_overdue_percent_amount" not in result:
        result["max_overdue_percent_amount"] = 0.0

    return result
