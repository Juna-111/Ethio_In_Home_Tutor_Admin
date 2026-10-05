from datetime import datetime, time, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.admin_auth import AdminPrincipal, require_admin
from app.database import get_db
from app.models import Assignment, ParentRequest, Tutor, TutorIncident
from app.services.matcher import get_tiered_matches

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/control-center", summary="Decision-oriented admin operations view")
async def get_admin_control_center(_admin: AdminPrincipal = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    now = datetime.now(timezone.utc)
    today_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)
    pending_requests = int(await db.scalar(select(func.count(ParentRequest.id)).where(ParentRequest.status == "pending")) or 0)
    pending_tutors = int(await db.scalar(select(func.count(Tutor.id)).where(Tutor.status == "pending")) or 0)
    active_assignments = int(await db.scalar(select(func.count(Assignment.id)).where(Assignment.status == "active")) or 0)
    requests_today = int(await db.scalar(select(func.count(ParentRequest.id)).where(ParentRequest.created_at >= today_start)) or 0)
    open_incidents = int(await db.scalar(select(func.count(TutorIncident.id)).where(TutorIncident.status == "open")) or 0)
    high_incidents = int(await db.scalar(select(func.count(TutorIncident.id)).where(TutorIncident.status == "open", TutorIncident.severity == "high")) or 0)
    total_requests = int(await db.scalar(select(func.count(ParentRequest.id))) or 0)
    assigned_requests = int(await db.scalar(select(func.count(Assignment.id))) or 0)
    conversion = round((assigned_requests / total_requests) * 100, 1) if total_requests else 0.0

    rows = await db.execute(select(Assignment.assigned_at, ParentRequest.created_at).join(ParentRequest, Assignment.request_id == ParentRequest.id))
    ages = []
    for assigned_at, created_at in rows.all():
        if assigned_at and created_at:
            if assigned_at.tzinfo is None: assigned_at = assigned_at.replace(tzinfo=timezone.utc)
            if created_at.tzinfo is None: created_at = created_at.replace(tzinfo=timezone.utc)
            delta = (assigned_at - created_at).total_seconds() / 86400
            if delta >= 0: ages.append(delta)
    avg_days = round(sum(ages) / len(ages), 1) if ages else 0.0

    attention = []
    result = await db.execute(select(ParentRequest).where(ParentRequest.status == "pending").order_by(ParentRequest.created_at.asc()).limit(3))
    for request in result.scalars().all():
        created_at = request.created_at
        if created_at.tzinfo is None: created_at = created_at.replace(tzinfo=timezone.utc)
        age_hours = round(max(0, (now - created_at).total_seconds() / 3600), 1)
        try:
            _, tiers = await get_tiered_matches(request.id, db)
            best = next((candidate for tier in ("tier1", "tier2", "tier3") for candidate in tiers[tier]), None)
        except Exception:
            best = None
        if best:
            tutor = best["tutor"]
            score = float(best.get("overall_score") or 0)
            recommendation = f"Invite {tutor.full_name} first ({score:.0f}% match)."
            evidence = [f"{score:.0f}% compatibility", f"{best['years_of_experience']:g} years experience", f"{best['expected_fee_etb']:,.0f} ETB/hour"]
        else:
            recommendation = "No verified compatible tutor is currently available; review supply coverage."
            evidence = ["No verified match returned by the canonical matcher"]
        attention.append({
            "id": f"request-{request.id}", "kind": "request",
            "severity": "critical" if age_hours >= 24 else "attention",
            "title": f"Request #{request.id} is waiting",
            "summary": f"{request.parent_name} · {request.student_level} · {', '.join(request.subjects or [])} · {request.location_subcity}",
            "entity_id": request.id, "action_label": "Review request", "action": "requests",
            "age_hours": age_hours, "recommendation": recommendation, "evidence": evidence,
        })

    if pending_tutors:
        attention.append({
            "id": "tutor-verification", "kind": "verification", "severity": "attention",
            "title": f"{pending_tutors} tutor profiles are awaiting verification",
            "summary": "Verification is the remaining human gate before a tutor becomes match-eligible.",
            "action_label": "Review tutors", "action": "tutors",
            "recommendation": "Process the oldest complete verification first.",
            "evidence": ["Only verified tutors are considered by the canonical matcher"],
        })

    incidents = await db.execute(select(TutorIncident).where(TutorIncident.status == "open").order_by(TutorIncident.created_at.asc()).limit(2))
    for incident in incidents.scalars().all():
        attention.append({
            "id": f"incident-{incident.id}", "kind": "incident", "severity": incident.severity,
            "title": f"{incident.severity.title()} tutor incident #{incident.id}",
            "summary": incident.description[:180], "entity_id": incident.id,
            "action_label": "Review incident", "action": "ops",
            "recommendation": "Review the incident before changing tutor or assignment state.",
            "evidence": ["Incident is still open"],
        })

    ranks = {"critical": 0, "high": 1, "attention": 2, "medium": 2, "low": 3}
    attention.sort(key=lambda x: (ranks.get(x["severity"], 4), -(x.get("age_hours") or 0)))
    if high_incidents:
        next_move = f"Review {high_incidents} high-severity incident(s) before routine work."
    elif attention:
        next_move = attention[0]["recommendation"] or attention[0]["title"]
    else:
        next_move = "No urgent intervention detected. Monitor marketplace health."

    return {
        "pending_requests": pending_requests, "pending_tutors": pending_tutors,
        "active_assignments": active_assignments, "open_incidents": open_incidents,
        "high_incidents": high_incidents, "requests_today": requests_today,
        "conversion_rate_pct": conversion, "avg_days_to_assign": avg_days,
        "attention": attention[:6],
        "system_posture": [
            "Matching engine: live",
            "Assignment workflow: canonical service enforced",
            f"Human attention queue: {len(attention)} item(s)",
        ],
        "next_move": next_move,
    }
