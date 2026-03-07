"""Генерация PDF анкеты через WeasyPrint."""

import json
import os
from datetime import date, datetime

from jinja2 import Environment, FileSystemLoader

_TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
_env = Environment(loader=FileSystemLoader(_TEMPLATES_DIR), autoescape=True)

DECISION_LABELS = {
    "approved": "Одобрено",
    "review": "На рассмотрение",
    "rejected": "Отклонено",
    "rejected_underwriter": "Отклонено (андеррайтер)",
    "rejected_client": "Отклонено (клиент)",
}


def _fmt_number(value) -> str:
    """Форматирование числа: 1234567.89 → '1 234 567.89'."""
    if value is None:
        return "—"
    try:
        num = float(value)
    except (ValueError, TypeError):
        return "—"
    if num == int(num):
        return f"{int(num):,}".replace(",", " ")
    return f"{num:,.2f}".replace(",", " ")


def _fmt_date(value) -> str:
    """Форматирование даты в DD.MM.YYYY."""
    if value is None:
        return "—"
    if isinstance(value, (date, datetime)):
        return value.strftime("%d.%m.%Y")
    return str(value)


def _fmt_datetime(value) -> str:
    """Форматирование datetime в DD.MM.YYYY HH:MM."""
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d.%m.%Y")
    return str(value)


def generate_anketa_pdf(anketa, creator, concluder=None) -> bytes:
    """Генерирует PDF байты из анкеты.

    Args:
        anketa: объект Anketa (SQLAlchemy model)
        creator: объект User — создатель анкеты
        concluder: объект User | None — кто заключил анкету
    Returns:
        bytes — содержимое PDF
    """
    # Парсим причины авто-вердикта из JSON
    auto_reasons = []
    if anketa.auto_decision_reasons:
        try:
            auto_reasons = json.loads(anketa.auto_decision_reasons)
        except (json.JSONDecodeError, TypeError):
            auto_reasons = [anketa.auto_decision_reasons]

    is_legal = anketa.client_type == "legal_entity"
    # Нумерация секций после специфичных блоков
    next_section = 9 if is_legal else 5
    next_section_conclusion = next_section + 1 if anketa.auto_decision else next_section

    template = _env.get_template("anketa_pdf.html")
    html_content = template.render(
        anketa=anketa,
        creator=creator,
        concluder_name=concluder.full_name if concluder else "—",
        client_type_label="Юридическое лицо" if is_legal else "Физическое лицо",
        created_at=_fmt_datetime(anketa.created_at),
        birth_date=_fmt_date(anketa.birth_date),
        last_overdue_date=_fmt_date(anketa.last_overdue_date),
        concluded_at=_fmt_datetime(anketa.concluded_at),
        generated_at=_fmt_datetime(datetime.now()),
        auto_reasons=auto_reasons,
        decision_labels=DECISION_LABELS,
        next_section=next_section,
        next_section_conclusion=next_section_conclusion,
        fmt_number=_fmt_number,
        fmt_date=_fmt_date,
    )

    from weasyprint import HTML
    pdf_bytes = HTML(string=html_content).write_pdf()
    return pdf_bytes
