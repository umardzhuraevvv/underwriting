from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.database import Anketa, User
from app.auth import get_user_permissions


def get_stats_data(db: Session, user: User, period: str,
                   date_from: str | None, date_to: str | None,
                   client_type: str | None) -> dict:
    """Get anketa statistics for the dashboard funnel."""
    now = datetime.utcnow()
    if period == "week":
        start = now - timedelta(days=7)
        end = now
    elif period == "custom" and date_from and date_to:
        start = datetime.fromisoformat(date_from)
        end = datetime.fromisoformat(date_to) + timedelta(days=1)
    else:  # month
        start = now - timedelta(days=30)
        end = now

    perms = get_user_permissions(user, db)
    base = db.query(Anketa).filter(Anketa.created_at >= start, Anketa.created_at <= end)

    # Filter by permissions: users without anketa_view_all see only their own
    if not perms.get("anketa_view_all"):
        base = base.filter(Anketa.created_by == user.id)

    # Filter by client_type if provided
    if client_type:
        base = base.filter(Anketa.client_type == client_type)

    total = base.count()
    draft = base.filter(Anketa.status == "draft").count()
    saved = base.filter(Anketa.status == "saved").count()
    approved = base.filter(Anketa.status == "approved").count()
    review = base.filter(Anketa.status == "review").count()
    rejected_underwriter = base.filter(Anketa.status == "rejected_underwriter").count()
    rejected_client = base.filter(Anketa.status == "rejected_client").count()
    deleted = base.filter(Anketa.status == "deleted").count()

    return {
        "total": total,
        "draft": draft,
        "saved": saved,
        "approved": approved,
        "review": review,
        "rejected_underwriter": rejected_underwriter,
        "rejected_client": rejected_client,
        "deleted": deleted,
    }


def get_analytics_data(db: Session, user: User, period: str,
                       date_from: str | None, date_to: str | None,
                       client_type: str | None) -> dict:
    """Extended analytics: approval rate, avg DTI, trend, risk distribution."""
    now = datetime.utcnow()

    if period == "week":
        current_start = now - timedelta(days=7)
        current_end = now
        prev_start = current_start - timedelta(days=7)
        prev_end = current_start
        # Trend: 7 daily points
        trend_points = 7
        trend_delta = timedelta(days=1)
        trend_fmt = lambda d: d.strftime("%d.%m")
    elif period == "custom" and date_from and date_to:
        current_start = datetime.fromisoformat(date_from)
        current_end = datetime.fromisoformat(date_to) + timedelta(days=1)
        delta = current_end - current_start
        prev_start = current_start - delta
        prev_end = current_start
        trend_points = min(7, max(1, delta.days))
        trend_delta = timedelta(days=max(1, delta.days // trend_points))
        trend_fmt = lambda d: d.strftime("%d.%m")
    else:  # month
        current_start = now - timedelta(days=30)
        current_end = now
        prev_start = current_start - timedelta(days=30)
        prev_end = current_start
        # Trend: 4 weekly points
        trend_points = 4
        trend_delta = timedelta(days=7)
        trend_fmt = lambda d: d.strftime("%d.%m")

    perms_analytics = get_user_permissions(user, db)

    def build_base(start, end):
        q = db.query(Anketa).filter(Anketa.created_at >= start, Anketa.created_at <= end)
        if not perms_analytics.get("anketa_view_all"):
            q = q.filter(Anketa.created_by == user.id)
        if client_type:
            q = q.filter(Anketa.client_type == client_type)
        return q

    # Current period
    cur_base = build_base(current_start, current_end)
    current_total = cur_base.count()
    cur_approved = cur_base.filter(Anketa.status == "approved").count()
    cur_rejected = cur_base.filter(Anketa.status.in_(["rejected_underwriter", "rejected_client"])).count()
    cur_decided = cur_approved + cur_rejected
    approval_rate = round(cur_approved / cur_decided * 100, 1) if cur_decided > 0 else 0

    avg_dti_row = cur_base.filter(Anketa.status != "draft", Anketa.dti.isnot(None)).with_entities(
        sa_func.avg(Anketa.dti)
    ).scalar()
    avg_dti = round(float(avg_dti_row), 1) if avg_dti_row else 0

    # Previous period
    prev_base = build_base(prev_start, prev_end)
    prev_total = prev_base.count()
    prev_approved = prev_base.filter(Anketa.status == "approved").count()
    prev_rejected = prev_base.filter(Anketa.status.in_(["rejected_underwriter", "rejected_client"])).count()
    prev_decided = prev_approved + prev_rejected
    prev_approval_rate = round(prev_approved / prev_decided * 100, 1) if prev_decided > 0 else 0

    prev_avg_dti_row = prev_base.filter(Anketa.status != "draft", Anketa.dti.isnot(None)).with_entities(
        sa_func.avg(Anketa.dti)
    ).scalar()
    prev_avg_dti = round(float(prev_avg_dti_row), 1) if prev_avg_dti_row else 0

    # Risk distribution
    risk_rows = cur_base.filter(Anketa.risk_grade.isnot(None)).with_entities(
        Anketa.risk_grade, sa_func.count()
    ).group_by(Anketa.risk_grade).all()
    risk_distribution = {row[0]: row[1] for row in risk_rows}

    # Trend
    trend = []
    for i in range(trend_points):
        t_start = current_start + trend_delta * i
        t_end = t_start + trend_delta
        t_base = build_base(t_start, t_end)
        t_total = t_base.count()
        t_approved = t_base.filter(Anketa.status == "approved").count()
        trend.append({
            "label": trend_fmt(t_start),
            "total": t_total,
            "approved": t_approved,
        })

    return {
        "current_total": current_total,
        "prev_total": prev_total,
        "approval_rate": approval_rate,
        "prev_approval_rate": prev_approval_rate,
        "avg_dti": avg_dti,
        "prev_avg_dti": prev_avg_dti,
        "risk_distribution": risk_distribution,
        "trend": trend,
    }


def get_employee_stats_data(db: Session, user: User, period: str,
                            date_from: str | None, date_to: str | None) -> list[dict]:
    """Get per-employee stats: total, approved, rejected, review, approval_rate, avg_dti, avg_processing_hours."""
    perms = get_user_permissions(user, db)

    now = datetime.utcnow()
    if period == "week":
        start = now - timedelta(days=7)
        end = now
    elif period == "custom" and date_from and date_to:
        start = datetime.fromisoformat(date_from)
        end = datetime.fromisoformat(date_to) + timedelta(days=1)
    else:
        start = now - timedelta(days=30)
        end = now

    base = db.query(Anketa).filter(
        Anketa.created_at >= start,
        Anketa.created_at <= end,
        Anketa.status != "deleted",
    )

    # If no anketa_view_all, only show own stats
    if not perms.get("anketa_view_all"):
        base = base.filter(Anketa.created_by == user.id)

    anketas = base.all()

    # Group by created_by
    by_user: dict[int, list] = {}
    for a in anketas:
        by_user.setdefault(a.created_by, []).append(a)

    # Load user names
    user_ids = list(by_user.keys())
    users_map = {}
    if user_ids:
        users_list = db.query(User).filter(User.id.in_(user_ids)).all()
        users_map = {u.id: u.full_name for u in users_list}

    result = []
    for uid, user_anketas in by_user.items():
        total = len(user_anketas)
        approved = sum(1 for a in user_anketas if a.status == "approved")
        rejected = sum(1 for a in user_anketas if a.status in ("rejected_underwriter", "rejected_client"))
        review = sum(1 for a in user_anketas if a.status == "review")
        decided = approved + rejected
        approval_rate = round(approved / decided * 100, 1) if decided > 0 else 0

        dtis = [a.dti for a in user_anketas if a.dti is not None and a.status != "draft"]
        avg_dti = round(sum(dtis) / len(dtis), 1) if dtis else 0

        # Avg processing hours: time from created_at to concluded_at
        processing_hours = []
        for a in user_anketas:
            if a.concluded_at and a.created_at:
                diff = (a.concluded_at - a.created_at).total_seconds() / 3600
                processing_hours.append(diff)
        avg_hours = round(sum(processing_hours) / len(processing_hours), 1) if processing_hours else 0

        result.append({
            "user_id": uid,
            "user_name": users_map.get(uid, f"User #{uid}"),
            "total": total,
            "approved": approved,
            "rejected": rejected,
            "review": review,
            "approval_rate": approval_rate,
            "avg_dti": avg_dti,
            "avg_processing_hours": avg_hours,
        })

    # Sort by total desc
    result.sort(key=lambda x: x["total"], reverse=True)
    return result
