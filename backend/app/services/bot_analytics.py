from sqlalchemy import func, select

from app.database import AsyncSessionLocal
from app.models import ParentRequest, Tutor


async def render_analytics_card() -> str:
    """Calculates KPI statistics across tutors and requests, returning HTML formatted text."""
    async with AsyncSessionLocal() as session:
        # Tutors breakdown
        total_tutors = await session.scalar(select(func.count(Tutor.id))) or 0
        verified_tutors = await session.scalar(select(func.count(Tutor.id)).where(Tutor.status == "verified")) or 0
        pending_tutors = await session.scalar(select(func.count(Tutor.id)).where(Tutor.status == "pending")) or 0
        rejected_tutors = await session.scalar(select(func.count(Tutor.id)).where(Tutor.status == "rejected")) or 0

        # Parent Requests breakdown
        total_requests = await session.scalar(select(func.count(ParentRequest.id))) or 0
        open_requests = await session.scalar(select(func.count(ParentRequest.id)).where(ParentRequest.status == "pending")) or 0
        matched_requests = await session.scalar(select(func.count(ParentRequest.id)).where(ParentRequest.status == "matched")) or 0

        # Average tutor fee
        avg_fee = await session.scalar(select(func.avg(Tutor.expected_fee_etb)).where(Tutor.status == "verified")) or 0.0

        # Top subcity demand
        subcity_res = await session.execute(
            select(ParentRequest.location_subcity, func.count(ParentRequest.id))
            .group_by(ParentRequest.location_subcity)
            .order_by(func.count(ParentRequest.id).desc())
            .limit(3)
        )
        top_subcities = subcity_res.all()

    subcities_str = ", ".join(f"{sc} ({cnt})" for sc, cnt in top_subcities) if top_subcities else "No data yet"
    ver_pct = f"{(verified_tutors / total_tutors * 100):.0f}%" if total_tutors > 0 else "0%"
    match_pct = f"{(matched_requests / total_requests * 100):.0f}%" if total_requests > 0 else "0%"

    return (
        "<b>PLATFORM ANALYTICS & KPIS</b>\n\n"
        "<blockquote><b>Tutor Community:</b> <code>" + str(total_tutors) + "</code> Total\n"
        f"├ Verified: <code>{verified_tutors}</code> ({ver_pct})\n"
        f"├ Pending: <code>{pending_tutors}</code>\n"
        f"└ Rejected: <code>{rejected_tutors}</code>\n\n"
        f"<b>Parent Tutoring Requests:</b> <code>{total_requests}</code> Total\n"
        f"├ Open / Pending: <code>{open_requests}</code>\n"
        f"└ Matched / Fulfilled: <code>{matched_requests}</code> ({match_pct})\n\n"
        f"<b>Economic Metrics:</b>\n"
        f"└ Avg Verified Fee: <code>{avg_fee:,.0f} ETB/hr</code>\n\n"
        f"<b>High-Demand Zones:</b>\n"
        f"└ {subcities_str}</blockquote>"
    )
