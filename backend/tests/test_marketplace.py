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
