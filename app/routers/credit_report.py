"""Роутер для парсинга кредитных историй (КАТМ / InfoScore)."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File

from app.auth import get_current_user
from app.database import User
from app.limiter import limiter
from app.credit_report_parser import parse_infoscore_html

logger = logging.getLogger("app")

router = APIRouter(prefix="/api/v1/credit-report", tags=["credit-report"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


@router.post("/parse")
@limiter.limit("30/minute")
async def parse_credit_report(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
):
    """Парсинг HTML-файла кредитной истории (InfoScore/CIAC). Возвращает JSON."""
    content = await file.read()

    if not content:
        raise HTTPException(status_code=422, detail="Файл пустой")

    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=422, detail="Файл слишком большой (макс. 5 МБ)")

    try:
        html_text = content.decode("utf-8")
    except UnicodeDecodeError:
        try:
            html_text = content.decode("cp1251")
        except Exception:
            raise HTTPException(status_code=422, detail="Не удалось прочитать файл. Поддерживаются кодировки UTF-8 и CP1251")

    try:
        result = parse_infoscore_html(html_text)
    except Exception:
        logger.exception("Ошибка парсинга кредитной истории, user=%s", user.id)
        raise HTTPException(
            status_code=422,
            detail="Не удалось разобрать кредитную историю. Проверьте формат файла.",
        )

    logger.info(
        "Кредитная история разобрана: user=%s, entity=%s, name=%s",
        user.id, result.get("entity_type"), result.get("full_name") or result.get("company_name"),
    )
    return result
