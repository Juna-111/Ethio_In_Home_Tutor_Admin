from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def log_action(
    db: AsyncSession,
    actor_id: int,
    action: str,
    target_type: str,
    target_id: int,
    reason: Optional[str] = None,
    source: str = "miniapp",
) -> AuditLog:
    """Add an audit event to the caller's transaction; the caller owns commit/rollback."""
    event = AuditLog(
        actor_telegram_id=actor_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        reason=reason,
        source=source,
    )
    db.add(event)
    return event