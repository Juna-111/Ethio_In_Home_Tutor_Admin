from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_auth import AdminPrincipal, require_admin
from app.database import get_db
from app.models import Assignment, ParentRequest, Tutor
from app.schemas import AdminDashboardResponse

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard", response_model=AdminDashboardResponse, summary="Admin dashboard counts")
async def get_admin_dashboard(
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminDashboardResponse:
    today_start = datetime.combine(datetime.now(timezone.utc).date(), time.min, tzinfo=timezone.utc)
    pending_tutors = await db.scalar(
        select(func.count(Tutor.id)).where(Tutor.status == "pending")
    )
    pending_requests = await db.scalar(
        select(func.count(ParentRequest.id)).where(ParentRequest.status == "pending")
    )
    active_assignments = await db.scalar(
        select(func.count(Assignment.id)).where(Assignment.status == "active")
    )
    requests_today = await db.scalar(
        select(func.count(ParentRequest.id)).where(ParentRequest.created_at >= today_start)
    )

    return AdminDashboardResponse(
        admin_telegram_id=_admin.telegram_id,
        admin_role=_admin.role,
        pending_tutors=pending_tutors or 0,
        pending_requests=pending_requests or 0,
        active_assignments=active_assignments or 0,
        requests_today=requests_today or 0,
    )