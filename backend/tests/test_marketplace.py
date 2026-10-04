from types import SimpleNamespace


def test_marketplace_router_contract():
    from app.routes.parents import router
    paths = {getattr(route, "path", None) for route in router.routes}
    assert "/parents/tutors" in paths
    assert "/parents/tutors/{tutor_id}" in paths
    assert "/parents/tutors/{tutor_id}/apply" in paths
    assert "/parents/tutors/{tutor_id}/favorite" in paths


def test_marketplace_match_scoring():
    from app.routes.parents import _match_tutor
    request = SimpleNamespace(
        student_level="High School 9-10",
        subjects=["Math"],
        preferred_gender="No preference",
        location_subcity="Bole",
        schedule_days=["Mon"],
        budget_etb=500,
    )
    tutor = SimpleNamespace(
        gender="Female",
        subjects_qualified=["Math"],
        grades_qualified=["High School 9-10"],
        expected_fee_etb=400,
        base_subcity="Bole",
        coverage_areas=["Bole"],
        availability_schedule={"Mon": "5 PM - 8 PM"},
    )
    score, reasons = _match_tutor(tutor, request)
    assert score == 95.0
    assert "Teaches Math" in reasons
