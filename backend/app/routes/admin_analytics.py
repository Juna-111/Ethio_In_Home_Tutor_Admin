from fastapi import APIRouter, Depends
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_auth import AdminPrincipal, require_admin
from app.database import get_db
from app.models import ParentRequest, RegistrationFunnelEvent, Tutor
from app.schemas import (
    AdminAvailabilityMismatchItem,
    AdminAvailabilityMismatchResponse,
    AdminFunnelResponse,
)

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/analytics/funnel", response_model=AdminFunnelResponse, summary="Tutor registration funnel analytics")
async def get_admin_funnel_analytics(
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminFunnelResponse:
    started_events = await db.scalar(
        select(func.count(distinct(RegistrationFunnelEvent.session_id)))
        .where(RegistrationFunnelEvent.stage == "started")
    ) or 0

    submitted_events = await db.scalar(
        select(func.count(distinct(RegistrationFunnelEvent.session_id)))
        .where(RegistrationFunnelEvent.stage == "submitted")
    ) or 0

    total_tutors = await db.scalar(select(func.count(Tutor.id))) or 0
    submitted = max(submitted_events, total_tutors)
    # Ensure monotonic funnel consistency: submitted <= started
    started = max(started_events, submitted)

    approved = await db.scalar(
        select(func.count(Tutor.id)).where(Tutor.status == "verified")
    ) or 0

    # Ensure monotonic funnel consistency: approved <= submitted
    approved = min(approved, submitted)

    sub_rate = round(submitted / started, 4) if started > 0 else 0.0
    app_rate = round(approved / submitted, 4) if submitted > 0 else 0.0

    return AdminFunnelResponse(
        started=started,
        submitted=submitted,
        approved=approved,
        submission_rate=sub_rate,
        approval_rate=app_rate,
    )


@router.get(
    "/analytics/availability-mismatch",
    response_model=AdminAvailabilityMismatchResponse,
    summary="Schedule availability mismatch cross-tabulation",
)
async def get_admin_availability_mismatch(
    _admin: AdminPrincipal = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> AdminAvailabilityMismatchResponse:
    # Query pending/active parent requests
    req_res = await db.execute(
        select(ParentRequest.time_slot).where(
            ParentRequest.status.in_(["pending", "waitlisted", "active"])
        )
    )
    request_slots = [time_slot for (time_slot,) in req_res.all()]

    # Fetch only the availability payload needed for this cross-tabulation.
    tutor_res = await db.execute(
        select(Tutor.availability_schedule).where(
            Tutor.status.in_(["pending", "verified"])
        )
    )
    tutor_schedules = [availability_schedule for (availability_schedule,) in tutor_res.all()]

    # Standard slot buckets
    slots = ["Morning", "Afternoon", "Evening", "Weekend", "Flexible"]
    demand_counts = {slot: 0 for slot in slots}
    supply_counts = {slot: 0 for slot in slots}

    for time_slot in request_slots:
        slot_text = (time_slot or "").lower()
        matched = False
        for slot in slots:
            if slot.lower() in slot_text:
                demand_counts[slot] += 1
                matched = True
        if not matched:
            demand_counts["Flexible"] += 1

    for availability_schedule in tutor_schedules:
        sched_text = str(availability_schedule).lower() if availability_schedule else ""
        matched = False
        for slot in slots:
            if slot.lower() in sched_text:
                supply_counts[slot] += 1
                matched = True
        if not matched:
            supply_counts["Flexible"] += 1

    items: list[AdminAvailabilityMismatchItem] = []
    total_demand = sum(demand_counts.values())
    total_supply = sum(supply_counts.values())

    for slot in slots:
        d = demand_counts[slot]
        s = supply_counts[slot]
        gap = max(0, d - s)
        ratio = round(gap / d, 4) if d > 0 else 0.0
        items.append(
            AdminAvailabilityMismatchItem(
                slot=slot,
                demand=d,
                supply=s,
                gap=gap,
                mismatch_ratio=ratio,
            )
        )

    return AdminAvailabilityMismatchResponse(
        total_demand=total_demand,
        total_supply=total_supply,
        items=items,
    )
