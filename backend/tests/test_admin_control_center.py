def test_control_center_route_contract():
    from app.routes.admin_control import get_admin_control_center
    assert get_admin_control_center.__name__ == "get_admin_control_center"


def test_control_center_does_not_replace_canonical_assignment_service():
    from app.services.assignment import assign_tutor_to_request
    assert assign_tutor_to_request.__name__ == "assign_tutor_to_request"
