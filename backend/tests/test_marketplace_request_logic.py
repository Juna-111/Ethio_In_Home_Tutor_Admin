from app.models import Child, ParentRequest
from app.schemas import ParentRequestCreate


def test_parent_request_supports_child_and_direct_tutor():
    fields = ParentRequestCreate.model_fields
    assert "child_id" in fields
    assert "child_name" in fields
    assert "preferred_tutor_id" in fields
    assert hasattr(ParentRequest, "child_id")
    assert hasattr(ParentRequest, "preferred_tutor_id")


def test_child_identity_is_scoped_to_parent():
    assert Child.__table__.c.parent_telegram_user_id is not None
    assert Child.__table__.c.normalized_name is not None
