from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_telegram_user
from app.config import settings
from app.database import get_db
from app.models import AdminUser


@dataclass(frozen=True)
class AdminPrincipal:
    telegram_id: int
    role: str


async def require_admin(
    telegram_user_id: Optional[int] = Depends(get_current_telegram_user),
    db: AsyncSession = Depends(get_db),
) -> AdminPrincipal:
    if telegram_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Telegram Mini App authentication is required.",
        )

    # The configured bootstrap owner exists before a database admin record can.
    if settings.SUPER_ADMIN_ID is not None and telegram_user_id == settings.SUPER_ADMIN_ID:
        return AdminPrincipal(telegram_id=telegram_user_id, role="super_admin")

    admin_user = await db.get(AdminUser, telegram_user_id)
    if not admin_user or not admin_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")

    return AdminPrincipal(telegram_id=telegram_user_id, role=admin_user.role)


def require_role(*roles: str):
    allowed_roles = frozenset(roles)

    async def role_dependency(
        principal: AdminPrincipal = Depends(require_admin),
    ) -> AdminPrincipal:
        if principal.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient admin role.")
        return principal

    return role_dependency