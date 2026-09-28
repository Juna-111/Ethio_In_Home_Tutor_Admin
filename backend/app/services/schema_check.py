"""Detect whether the connected database has all Alembic migrations applied.

Production does not auto-create tables (only ``ENVIRONMENT=development`` does), so
a deploy that ships new code without running ``alembic upgrade head`` fails at
request time with an opaque 500. This module makes that state visible in the
``/api/v1/health`` response and in the startup log instead of leaving it to be
discovered through a confusing browser error.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("mentorlink.schema")

BACKEND_DIR = Path(__file__).resolve().parents[2]


def get_migration_head() -> Optional[str]:
    """Return the newest revision id shipped with this code, or None if unreadable."""
    try:
        from alembic.config import Config
        from alembic.script import ScriptDirectory

        cfg = Config(str(BACKEND_DIR / "alembic.ini"))
        cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
        heads = ScriptDirectory.from_config(cfg).get_heads()
        return heads[0] if len(heads) == 1 else ",".join(sorted(heads))
    except Exception as exc:  # pragma: no cover - defensive; never break health
        logger.warning("Could not read Alembic head revision: %s", exc)
        return None


async def get_schema_status(db: AsyncSession) -> dict[str, Any]:
    """Compare the database revision to the code's head revision.

    ``state`` is one of:
      * ``current``   - database is at the latest migration
      * ``behind``    - database is missing migrations (run ``alembic upgrade head``)
      * ``untracked`` - no ``alembic_version`` table (e.g. dev DB built by create_all)
      * ``unknown``   - the migration scripts could not be read
    """
    head = get_migration_head()
    current: Optional[str] = None
    tracked = True
    try:
        result = await db.execute(text("SELECT version_num FROM alembic_version"))
        rows = [row[0] for row in result.fetchall()]
        current = ",".join(sorted(rows)) if rows else None
    except Exception:
        tracked = False
        # A failed statement can leave the session/transaction unusable on Postgres.
        try:
            await db.rollback()
        except Exception:  # pragma: no cover - defensive
            pass

    if head is None:
        state = "unknown"
    elif not tracked:
        state = "untracked"
    elif current == head:
        state = "current"
    else:
        state = "behind"

    return {"state": state, "current": current, "head": head}
