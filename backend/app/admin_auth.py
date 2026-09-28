from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_telegram_user
from app.config import settings
from app.database import get_db
from app.models import AdminUser

LEGACY_ADMIN_ROLES = frozenset({"matcher", "verifier"})
STANDARD_ADMIN_ROLE = "admin"
SUPER_ADMIN_ROLE = "super_admin"


def _normalize_role(raw_role: str) -> str:
    if raw_role in LEGACY_ADMIN_ROLES:
        return STANDARD_ADMIN_ROLE
    return raw_role


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

    if settings.SUPER_ADMIN_ID is not None and telegram_user_id == settings.SUPER_ADMIN_ID:
        return AdminPrincipal(telegram_id=telegram_user_id, role=SUPER_ADMIN_ROLE)

    admin_user = await db.get(AdminUser, telegram_user_id)
    if not admin_user or not admin_user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required.")

    role = _normalize_role(admin_user.role)
    return AdminPrincipal(telegram_id=telegram_user_id, role=role)


def require_role(*roles: str):
    allowed_roles = frozenset(_normalize_role(r) for r in roles)

    async def role_dependency(
        principal: AdminPrincipal = Depends(require_admin),
    ) -> AdminPrincipal:
        if principal.role not in allowed_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient admin role.")
        return principal

    return role_dependency