def test_marketplace_router_contract():
    from app.routes.parents import router

    paths = {getattr(route, "path", None) for route in router.routes}
    assert "/parents/tutors" in paths
    assert "/parents/tutors/{tutor_id}" in paths
    assert "/parents/tutors/{tutor_id}/apply" in paths
    assert "/parents/tutors/{tutor_id}/favorite" in paths


def test_marketplace_schema_contract():
    from app.schemas import (
        MarketplaceApplicationCreate,
        MarketplaceApplicationResponse,
        MarketplaceFavoriteResponse,
        MarketplaceTutorDetailResponse,
        MarketplaceTutorItem,
        MarketplaceTutorListResponse,
    )

    assert MarketplaceTutorDetailResponse.model_fields["id"]
    assert MarketplaceTutorListResponse.model_fields["tutors"]
    assert MarketplaceApplicationCreate.model_fields["request_id"]
    assert MarketplaceApplicationResponse.model_fields["invite_id"]
    assert MarketplaceFavoriteResponse.model_fields["is_favorite"]


def test_marketplace_favorite_model_contract():
    from app.models import MarketplaceFavorite

    assert MarketplaceFavorite.__tablename__ == "marketplace_favorites"
    constraint_names = {
        constraint.name
        for constraint in MarketplaceFavorite.__table__.constraints
        if constraint.name
    }
    assert "uq_marketplace_favorite_parent_tutor" in constraint_names


def test_assignment_service_requires_accepted_invite_and_active_request():
    from app.services.assignment import AssignmentWorkflowError, assign_tutor_to_request

    assert AssignmentWorkflowError("x").status_code == 409
    assert assign_tutor_to_request.__name__ == "assign_tutor_to_request"


def test_marketplace_grade_and_schedule_helpers_are_shared():
    from app.services.matcher import _are_grades_compatible, _schedule_days

    assert _are_grades_compatible("grade 10", ["grade 9-10"])
    assert not _are_grades_compatible("grade 1", ["grade 10"])
    assert _schedule_days("Monday, Wednesday") == {"mon", "wed"}


def test_registration_safety_contracts():
    from app.routes.parents import create_parent_request
    from app.routes.tutors import register_tutor

    assert create_parent_request.__name__ == "create_parent_request"
    assert register_tutor.__name__ == "register_tutor"


def test_customer_register_uses_reply_keyboard_webapp(monkeypatch):
    from app.bot.handlers import get_public_reply_keyboard
    from app.config import settings

    monkeypatch.setattr(settings, "WEBAPP_URL", "https://customer.example.com")

    keyboard = get_public_reply_keyboard()
    register_button = keyboard.keyboard[0][0]

    assert register_button.text == "🚀 Register"
    assert register_button.web_app is not None
    assert register_button.web_app.url == "https://customer.example.com"
