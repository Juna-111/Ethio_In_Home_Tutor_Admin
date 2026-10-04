from app.models import ParentRequest, Tutor


def test_marketplace_router_contract():
    from app.routes.parents import router
    paths = {getattr(route, "path", None) for route in router.routes}
    assert "/parents/tutors" in paths
    assert "/parents/tutors/{tutor_id}" in paths
    assert "/parents/tutors/{tutor_id}/apply" in paths
    assert "/parents/tutors/{tutor_id}/favorite" in paths


def test_marketplace_requires_telegram_identity():
    from app.routes.parents import router
    target = next(route for route in router.routes if getattr(route, "path", None) == "/parents/tutors" and "GET" in getattr(route, "methods", set()))
    assert target.dependant.dependencies
    assert any("get_optional_telegram_user" in repr(dep.call) for dep in target.dependant.dependencies)


def test_marketplace_match_scoring_prefers_subject_grade_location_and_budget():
    from app.routes.parents import _match_tutor

    request = ParentRequest(
        telegram_user_id=9001,
        parent_name="Parent",
        phone_number="+251911111111",
        student_level="High School 9-10",
        subjects=["Math"],
        preferred_gender="No preference",
        preferred_experience="Any",
        location_subcity="Bole",
        schedule_days=["Mon"],
        time_slot="5 PM - 7 PM",
        session_duration="2 hrs",
        budget_etb=500,
        status="pending",
    )
    tutor = Tutor(
        full_name="Match",
        gender="Female",
        phone_number="+251922222222",
        university="AAU",
        department="Mathematics",
        education_year="4th Year",
        subjects_qualified=["Math"],
        grades_qualified=["High School 9-10"],
        years_of_experience=2,
        expected_fee_etb=400,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule={"Mon": "5 PM - 8 PM"},
        status="verified",
        is_paused=False,
    )
    score, reasons = _match_tutor(tutor, request)
    assert score == 95.0
    assert "Teaches Math" in reasons
    assert "Matches the requested grade" in reasons
    assert "Covers the requested area" in reasons
