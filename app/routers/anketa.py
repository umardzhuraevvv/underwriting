import hashlib
import json
import logging
import os
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

logger = logging.getLogger("app")
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db, Anketa, User, RiskRule, EditRequest, Notification, AnketaViewLog
from app.auth import get_current_user, get_user_permissions
from app.services.pdf_service import generate_anketa_pdf
from app.services.calculation_service import run_calculations, load_rules, calc_auto_verdict
from app.services.anketa_service import (
    anketa_to_detail, record_history, create_notification,
    check_anketa_access, check_duplicate_field,
    validate_anketa_for_save, notify_admins_on_save,
    notify_admins_on_edit_request,
    apply_anketa_updates, apply_conclusion, query_history,
)
from app.services.analytics_service import (
    get_stats_data, get_analytics_data, get_employee_stats_data,
    get_monthly_trend, get_dti_distribution,
    get_inspector_stats, get_avg_amount_trend,
)
from app.schemas import (
    ConclusionRequest, DeleteAnketaRequest,
    AnketaUpdate, EditRequestCreate, EditRequestOut,
    AnketaCreateResponse, AnketaListItem, AnketaDetail,
    NotificationOut, CountResponse, OkResponse,
    OkIdResponse, DeleteResponse, ViewLogEntry,
    DuplicateCheckResponse,
)

router = APIRouter(prefix="/api/v1/anketas", tags=["anketas"])
public_router = APIRouter(prefix="/api/v1/public", tags=["public"])


# ---------- Endpoints ----------


@router.get("/check-duplicate", response_model=DuplicateCheckResponse)
def check_duplicate(
    field: str = Query(...),
    value: str = Query(...),
    exclude_id: int | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Real-time duplicate check for a single field."""
    return {"duplicates": check_duplicate_field(db, field, value, exclude_id)}


@router.post("", response_model=AnketaCreateResponse)
def create_anketa(
    client_type: str = Query("individual"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new draft anketa."""
    perms = get_user_permissions(user, db)
    if not perms.get("anketa_create"):
        raise HTTPException(status_code=403, detail="Нет права на создание анкет")
    anketa = Anketa(created_by=user.id, status="draft", client_type=client_type)
    db.add(anketa)
    db.commit()
    db.refresh(anketa)
    logger.info("Анкета #%d создана пользователем %s", anketa.id, user.email)
    return {"id": anketa.id, "status": anketa.status}


@router.get("/verdict-rules")
def get_verdict_rules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return underwriting rules as {rule_key: value} for client-side preview."""
    return load_rules(db)


@router.get("/risk-rules")
def get_risk_rules(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return active risk rules for client-side PV validation."""
    rules = db.query(RiskRule).filter(RiskRule.is_active == True).order_by(RiskRule.category).all()
    return [{"category": r.category, "min_pv": r.min_pv} for r in rules]


@router.get("/stats")
def get_stats(
    period: str = Query("month"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    client_type: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get anketa statistics for the dashboard funnel."""
    if period == "custom" and date_from and date_to:
        try:
            datetime.fromisoformat(date_from)
            datetime.fromisoformat(date_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат даты")
    return get_stats_data(db, user, period, date_from, date_to, client_type)


@router.get("", response_model=list[AnketaListItem])
def list_anketas(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List all anketas with summary info (excluding deleted)."""
    perms = get_user_permissions(user, db)
    query = db.query(Anketa).filter(Anketa.status != "deleted")
    if not perms.get("anketa_view_all"):
        query = query.filter(Anketa.created_by == user.id)
    anketas = query.order_by(Anketa.id.desc()).all()
    result = []
    for a in anketas:
        result.append({
            "id": a.id,
            "status": a.status,
            "client_type": getattr(a, 'client_type', None) or "individual",
            "full_name": a.full_name,
            "company_name": a.company_name,
            "car_brand": a.car_brand,
            "car_model": a.car_model,
            "car_specs": a.car_specs,
            "car_year": a.car_year,
            "purchase_price": a.purchase_price,
            "down_payment_percent": a.down_payment_percent,
            "dti": a.dti,
            "decision": a.decision,
            "created_by": a.created_by,
            "created_at": str(a.created_at) if a.created_at else None,
            "creator_name": a.creator.full_name if a.creator else None,
        })
    return result


# ---------- Notifications ----------

@router.get("/notifications/list", response_model=list[NotificationOut])
def list_notifications(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get latest notifications for the current user."""
    notifs = db.query(Notification).filter(
        Notification.user_id == user.id
    ).order_by(Notification.id.desc()).limit(50).all()
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "message": n.message,
            "anketa_id": n.anketa_id,
            "is_read": n.is_read,
            "created_at": str(n.created_at) if n.created_at else None,
        }
        for n in notifs
    ]


@router.get("/notifications/unread-count", response_model=CountResponse)
def unread_notification_count(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    count = db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read == False
    ).count()
    return {"count": count}


@router.patch("/notifications/{notif_id}/read", response_model=OkResponse)
def mark_notification_read(
    notif_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.query(Notification).filter(Notification.id == notif_id, Notification.user_id == user.id).first()
    if not n:
        raise HTTPException(status_code=404, detail="Уведомление не найдено")
    n.is_read = True
    db.commit()
    return {"ok": True}


@router.post("/notifications/read-all", response_model=OkResponse)
def mark_all_notifications_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(Notification).filter(
        Notification.user_id == user.id, Notification.is_read == False
    ).update({"is_read": True})
    db.commit()
    return {"ok": True}


# ---------- Analytics ----------

@router.get("/analytics")
def get_analytics(
    period: str = Query("month"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    client_type: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Extended analytics: approval rate, avg DTI, trend, risk distribution."""
    if period == "custom" and date_from and date_to:
        try:
            datetime.fromisoformat(date_from)
            datetime.fromisoformat(date_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат даты")
    return get_analytics_data(db, user, period, date_from, date_to, client_type)


@router.get("/analytics/monthly-trend")
def analytics_monthly_trend(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Тренд анкет по месяцам (последние 12 месяцев)."""
    perms = get_user_permissions(user, db)
    if not perms.get("analytics_view"):
        raise HTTPException(status_code=403, detail="Нет права: analytics_view")
    return get_monthly_trend(db)


@router.get("/analytics/dti-distribution")
def analytics_dti_distribution(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Распределение анкет по DTI."""
    perms = get_user_permissions(user, db)
    if not perms.get("analytics_view"):
        raise HTTPException(status_code=403, detail="Нет права: analytics_view")
    return get_dti_distribution(db)


@router.get("/analytics/inspector-stats")
def analytics_inspector_stats(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Топ инспекторов по количеству анкет."""
    perms = get_user_permissions(user, db)
    if not perms.get("analytics_view"):
        raise HTTPException(status_code=403, detail="Нет права: analytics_view")
    return get_inspector_stats(db)


@router.get("/analytics/amount-trend")
def analytics_amount_trend(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Средняя сумма лизинга по месяцам."""
    perms = get_user_permissions(user, db)
    if not perms.get("analytics_view"):
        raise HTTPException(status_code=403, detail="Нет права: analytics_view")
    return get_avg_amount_trend(db)


@router.get("/edit-requests", response_model=list[EditRequestOut])
def list_edit_requests(
    status: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List edit requests. Users with anketa_view_all see all; others see their own."""
    er_perms = get_user_permissions(user, db)
    query = db.query(EditRequest)
    if not er_perms.get("anketa_view_all"):
        query = query.filter(EditRequest.requested_by == user.id)
    if status:
        query = query.filter(EditRequest.status == status)
    requests = query.order_by(EditRequest.id.desc()).all()

    result = []
    for r in requests:
        anketa = db.query(Anketa).filter(Anketa.id == r.anketa_id).first()
        is_legal = anketa and (getattr(anketa, 'client_type', None) == 'legal_entity')
        client_name = None
        if anketa:
            client_name = anketa.company_name if is_legal else anketa.full_name
        result.append(EditRequestOut(
            id=r.id,
            anketa_id=r.anketa_id,
            requester_name=r.requester.full_name if r.requester else "—",
            reason=r.reason,
            status=r.status,
            reviewer_name=r.reviewer.full_name if r.reviewer else None,
            review_comment=r.review_comment,
            created_at=str(r.created_at) if r.created_at else None,
            reviewed_at=str(r.reviewed_at) if r.reviewed_at else None,
            anketa_client_name=client_name,
            anketa_status=anketa.status if anketa else None,
        ))
    return result


@router.get("/{anketa_id}", response_model=AnketaDetail)
def get_anketa(
    anketa_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get full anketa details."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    check_anketa_access(anketa, user, db)
    # Record view
    db.add(AnketaViewLog(anketa_id=anketa.id, user_id=user.id))
    db.commit()
    return anketa_to_detail(anketa, db)


@router.get("/{anketa_id}/pdf")
def download_anketa_pdf(
    anketa_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Скачать PDF анкеты."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    check_anketa_access(anketa, user, db)

    creator = db.query(User).filter(User.id == anketa.created_by).first()
    concluder = None
    if anketa.concluded_by:
        concluder = db.query(User).filter(User.id == anketa.concluded_by).first()

    pdf_bytes = generate_anketa_pdf(anketa, creator, concluder)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="anketa_{anketa_id}.pdf"'},
    )


@router.patch("/{anketa_id}", response_model=AnketaDetail)
def update_anketa(
    anketa_id: int,
    data: AnketaUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update anketa fields (only if draft)."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    check_anketa_access(anketa, user, db)
    # Permission check: only creator or users with anketa_edit can edit
    if anketa.created_by != user.id:
        perms = get_user_permissions(user, db)
        if not perms.get("anketa_edit"):
            raise HTTPException(status_code=403, detail="Нет права на редактирование анкет")
    if anketa.status != "draft":
        raise HTTPException(status_code=400, detail="Редактировать можно только черновики")

    update_data = data.model_dump(exclude_unset=True)
    apply_anketa_updates(db, anketa, update_data, user.id)
    run_calculations(anketa)

    db.commit()
    db.refresh(anketa)
    return anketa_to_detail(anketa, db)


@router.post("/{anketa_id}/save", response_model=AnketaDetail)
def save_anketa(
    anketa_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Finalize anketa: validate, recalculate, set status to saved."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    check_anketa_access(anketa, user, db)
    if anketa.status != "draft":
        raise HTTPException(status_code=400, detail="Сохранить можно только черновики")

    errors = validate_anketa_for_save(anketa, db)
    if errors:
        raise HTTPException(status_code=422, detail=errors)

    # Run calculations
    run_calculations(anketa)

    # Auto-verdict
    rules = load_rules(db)
    verdict = calc_auto_verdict(anketa, rules)
    anketa.auto_decision = verdict["auto_decision"]
    anketa.auto_decision_reasons = json.dumps(verdict["auto_decision_reasons"], ensure_ascii=False)
    anketa.recommended_pv = verdict["recommended_pv"]

    # If anketa was edited via approved edit request → set status to "review"
    has_approved_edit = db.query(EditRequest).filter(
        EditRequest.anketa_id == anketa.id,
        EditRequest.status == "approved",
    ).first()
    if has_approved_edit:
        anketa.status = "review"
        anketa.decision = None
        anketa.concluded_by = None
        anketa.concluded_at = None
        anketa.conclusion_comment = None
    else:
        anketa.status = "saved"

    # Notify about duplicates and Telegram
    notify_admins_on_save(db, anketa, user)

    db.commit()
    db.refresh(anketa)
    logger.info(
        "Анкета #%d сохранена пользователем %s, авто-вердикт: %s, DTI=%.1f%%",
        anketa.id, user.email, anketa.auto_decision, anketa.dti or 0,
    )
    return anketa_to_detail(anketa, db)


@router.post("/{anketa_id}/conclude", response_model=AnketaDetail)
def conclude_anketa(
    anketa_id: int,
    data: ConclusionRequest,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set underwriter conclusion on a saved anketa. Supports re-conclusion."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    check_anketa_access(anketa, user, db)
    # Permission check: anketa_conclude required
    perms = get_user_permissions(user, db)
    if not perms.get("anketa_conclude"):
        raise HTTPException(status_code=403, detail="Нет права на вынесение заключения")

    # Allow conclusion for saved anketas and re-conclusion for already concluded
    allowed_statuses = {"saved", "approved", "review", "rejected_underwriter", "rejected_client"}
    if anketa.status not in allowed_statuses:
        raise HTTPException(status_code=400, detail="Заключение можно дать только для сохранённой анкеты")

    valid_decisions = {"approved", "review", "rejected_underwriter", "rejected_client"}
    if data.decision not in valid_decisions:
        raise HTTPException(status_code=400, detail=f"Недопустимое решение. Допустимые: {', '.join(valid_decisions)}")

    # Validate final_pv (required)
    if data.final_pv is None:
        raise HTTPException(status_code=400, detail="Укажите итоговый ПВ%")

    apply_conclusion(db, anketa, data.decision, data.comment, data.final_pv, user)

    db.commit()
    db.refresh(anketa)
    logger.info("Анкета #%d заключена: %s, пользователем %s", anketa.id, data.decision, user.email)

    # Отправить webhook-уведомления асинхронно (не блокирует ответ)
    from app.services.webhook_service import notify_webhooks
    background_tasks.add_task(notify_webhooks, db, f"anketa.{data.decision}", anketa)

    return anketa_to_detail(anketa, db)


@router.delete("/{anketa_id}", response_model=DeleteResponse)
def delete_anketa(
    anketa_id: int,
    data: DeleteAnketaRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Soft-delete an anketa (only by creator or users with anketa_delete permission)."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    if anketa.created_by != user.id:
        perms = get_user_permissions(user, db)
        if not perms.get("anketa_delete"):
            raise HTTPException(status_code=403, detail="Нет права на удаление анкет")
    if anketa.status == "deleted":
        raise HTTPException(status_code=400, detail="Анкета уже удалена")
    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="Укажите причину удаления")

    old_status = anketa.status
    reason = data.reason.strip()

    # Record history
    record_history(db, anketa.id, user.id, "status", old_status, "deleted")
    record_history(db, anketa.id, user.id, "deletion_reason", None, reason)

    # Hash PINFL for dedup (keep data in DB)
    if anketa.pinfl:
        salt = os.environ.get("PINFL_SALT", "fintechdrive_salt_2024")
        anketa.pinfl_hash = hashlib.sha256((salt + anketa.pinfl).encode()).hexdigest()

    anketa.status = "deleted"
    anketa.deleted_at = datetime.utcnow()
    anketa.deleted_by = user.id
    anketa.deletion_reason = reason

    db.commit()
    logger.warning("Анкета #%d удалена пользователем %s, причина: %s", anketa.id, user.email, reason)
    return {"ok": True, "id": anketa.id}


# ---------- Edit Requests ----------

@router.post("/{anketa_id}/edit-request", response_model=OkIdResponse)
def create_edit_request(
    anketa_id: int,
    data: EditRequestCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a request to edit a saved/concluded anketa."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    check_anketa_access(anketa, user, db)

    if anketa.status in ("draft", "deleted"):
        raise HTTPException(status_code=400, detail="Запрос на правку не нужен для черновика или удалённой анкеты")

    # Check for existing pending request
    existing = db.query(EditRequest).filter(
        EditRequest.anketa_id == anketa_id,
        EditRequest.status == "pending",
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Уже есть ожидающий запрос на правку для этой анкеты")

    if not data.reason or not data.reason.strip():
        raise HTTPException(status_code=400, detail="Укажите причину")

    req = EditRequest(
        anketa_id=anketa_id,
        requested_by=user.id,
        reason=data.reason.strip(),
    )
    db.add(req)

    notify_admins_on_edit_request(db, anketa_id, user, data.reason.strip())

    db.commit()
    db.refresh(req)
    return {"ok": True, "id": req.id}


@router.get("/{anketa_id}/history")
def get_anketa_history(
    anketa_id: int,
    field: str | None = None,
    user_filter: int | None = Query(None, alias="user"),
    date_from: str | None = None,
    date_to: str | None = None,
    search: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get change history for an anketa with optional filters."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    check_anketa_access(anketa, user, db)
    return query_history(db, anketa_id, field, user_filter, date_from, date_to, search)


@router.get("/{anketa_id}/view-log", response_model=list[ViewLogEntry])
def get_view_log(
    anketa_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get view log for an anketa."""
    anketa = db.query(Anketa).filter(Anketa.id == anketa_id).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    check_anketa_access(anketa, user, db)

    entries = db.query(AnketaViewLog).filter(
        AnketaViewLog.anketa_id == anketa_id
    ).order_by(AnketaViewLog.id.desc()).all()

    return [
        {
            "id": e.id,
            "user_name": e.viewer.full_name if e.viewer else "—",
            "viewed_at": str(e.viewed_at) if e.viewed_at else None,
        }
        for e in entries
    ]


# ---------- Employee Stats ----------

@router.get("/employee-stats/data")
def get_employee_stats(
    period: str = Query("month"),
    date_from: str | None = Query(None),
    date_to: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get per-employee stats."""
    perms = get_user_permissions(user, db)

    # Only users with analytics_view can access
    if not perms.get("analytics_view"):
        raise HTTPException(status_code=403, detail="Нет права: analytics_view")

    if period == "custom" and date_from and date_to:
        try:
            datetime.fromisoformat(date_from)
            datetime.fromisoformat(date_to)
        except ValueError:
            raise HTTPException(status_code=400, detail="Неверный формат даты")

    return get_employee_stats_data(db, user, period, date_from, date_to)


# ---------- Public API (no auth) ----------

@public_router.get("/anketa/{token}", response_model=AnketaDetail)
def get_public_anketa(token: str, db: Session = Depends(get_db)):
    """Return anketa data by share_token (no authentication required)."""
    anketa = db.query(Anketa).filter(
        Anketa.share_token == token,
        Anketa.status != "deleted",
    ).first()
    if not anketa:
        raise HTTPException(status_code=404, detail="Анкета не найдена")
    return anketa_to_detail(anketa, db)
