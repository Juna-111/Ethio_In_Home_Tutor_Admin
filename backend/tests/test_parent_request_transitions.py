from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routes.parents import cancel_parent_request


class FakeDB:
    def __init__(self, rowcount, owned_request=None):
        self.rowcount = rowcount
        self.owned_request = owned_request
        self.committed = False
        self.rolled_back = False
        self.executed_statement = None

    async def execute(self, statement):
        self.executed_statement = statement
        return SimpleNamespace(rowcount=self.rowcount)

    async def commit(self):
        self.committed = True

    async def rollback(self):
        self.rolled_back = True

    async def scalar(self, statement):
        return self.owned_request


@pytest.mark.asyncio
async def test_parent_cancel_uses_conditional_update_and_commits_only_one_row():
    db = FakeDB(rowcount=1)

    result = await cancel_parent_request(request_id=42, db=db, verified_user_id=123)

    assert result["ok"] is True
    assert result["request_id"] == 42
    assert result["status"] == "cancelled"
    assert db.committed is True
    assert db.rolled_back is False
    # The status predicate must be part of the single UPDATE, not a prior read.
    sql = str(db.executed_statement.compile(compile_kwargs={"literal_binds": True}))
    assert "'pending'" in sql
    assert "'reviewing'" in sql


@pytest.mark.asyncio
async def test_parent_cancel_returns_conflict_when_request_is_no_longer_cancellable():
    db = FakeDB(rowcount=0, owned_request=SimpleNamespace(id=42, status="assigned"))

    with pytest.raises(HTTPException) as exc:
        await cancel_parent_request(request_id=42, db=db, verified_user_id=123)

    assert exc.value.status_code == 409
    assert db.rolled_back is False
    assert db.committed is False


@pytest.mark.asyncio
async def test_parent_cancel_returns_not_found_for_request_owned_by_another_user():
    db = FakeDB(rowcount=0, owned_request=None)

    with pytest.raises(HTTPException) as exc:
        await cancel_parent_request(request_id=42, db=db, verified_user_id=123)

    assert exc.value.status_code == 404
    assert db.rolled_back is False
