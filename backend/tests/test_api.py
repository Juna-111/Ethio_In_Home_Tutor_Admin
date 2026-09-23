import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ParentRequest, Tutor


@pytest.mark.asyncio
async def test_healthcheck(async_client: AsyncClient):
    """Verifies the health check endpoint returns 200 and healthy database status."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_create_parent_request_success(async_client: AsyncClient, db_session: AsyncSession):
    """Verifies that a valid parent intake payload is saved with status 'pending'."""
    payload = {
        "telegram_user_id": 123456789,
        "parent_name": "Abebe Kebede",
        "phone_number": "+251911223344",
        "student_level": "High School 9-10",
        "subjects": ["Maths", "Physics"],
        "preferred_gender": "Male",
        "preferred_experience": "University Student",
        "location_subcity": "Bole",
        "location_landmark": "Around Edna Mall",
        "schedule_days": ["Mon", "Wed", "Fri"],
        "time_slot": "4:30 PM - 6:30 PM",
        "session_duration": "2 hrs",
        "budget_etb": 4500.0
    }

    response = await async_client.post("/api/v1/parents/request", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["status"] == "pending"
    assert data["parent_name"] == "Abebe Kebede"
    assert data["location_subcity"] == "Bole"
    assert data["subjects"] == ["Maths", "Physics"]

    # Verify directly against database
    query = select(ParentRequest).where(ParentRequest.id == data["id"])
    result = await db_session.execute(query)
    record = result.scalar_one_or_none()
    assert record is not None
    assert record.parent_name == "Abebe Kebede"
    assert record.status == "pending"
    assert record.budget_etb == 4500.0


@pytest.mark.asyncio
async def test_create_parent_request_validation_failure(async_client: AsyncClient):
    """Verifies that invalid payloads (e.g. non-positive budget, missing fields) return 422."""
    invalid_payload = {
        "parent_name": "Abebe",
        "phone_number": "+251911223344",
        "student_level": "Primary 1-4",
        "subjects": [],  # Empty subjects list should fail validation
        "preferred_experience": "University Student",
        "location_subcity": "Bole",
        "schedule_days": "Mon/Wed",
        "time_slot": "5:00 PM",
        "session_duration": "1 hr",
        "budget_etb": -100.0  # Invalid negative budget
    }

    response = await async_client.post("/api/v1/parents/request", json=invalid_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_tutor_success(async_client: AsyncClient, db_session: AsyncSession):
    """Verifies that a valid tutor profile is registered with status 'pending'."""
    payload = {
        "telegram_user_id": 987654321,
        "full_name": "Sara Tadesse",
        "gender": "Female",
        "phone_number": "+251922334455",
        "university": "Addis Ababa University (AAiT)",
        "department": "Electrical & Computer Engineering",
        "education_year": "4th Year",
        "subjects_qualified": ["Maths", "Physics", "Chemistry"],
        "grades_qualified": ["Primary 5-8", "High School 9-10"],
        "years_of_experience": 2.5,
        "expected_fee_etb": 350.0,
        "base_subcity": "Yeka",
        "coverage_areas": ["Yeka", "Bole", "Arada"],
        "availability_schedule": {
            "weekdays": "after 5 PM",
            "weekends": "all day"
        },
        "id_document_url": "https://example.com/uploads/sara_id.jpg"
    }

    response = await async_client.post("/api/v1/tutors/register", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"] is not None
    assert data["status"] == "pending"
    assert data["full_name"] == "Sara Tadesse"
    assert data["gender"] == "Female"
    assert data["base_subcity"] == "Yeka"
    assert data["subjects_qualified"] == ["Maths", "Physics", "Chemistry"]

    # Verify directly against database
    query = select(Tutor).where(Tutor.id == data["id"])
    result = await db_session.execute(query)
    record = result.scalar_one_or_none()
    assert record is not None
    assert record.full_name == "Sara Tadesse"
    assert record.status == "pending"
    assert record.expected_fee_etb == 350.0


@pytest.mark.asyncio
async def test_register_tutor_duplicate_telegram_id(async_client: AsyncClient):
    """Verifies duplicate prevention when a tutor with existing telegram_user_id registers."""
    payload = {
        "telegram_user_id": 987654321,  # Already created in previous test
        "full_name": "Sara Duplicate",
        "gender": "Female",
        "phone_number": "+251922334499",
        "university": "AAU",
        "department": "Computer Science",
        "education_year": "Graduate",
        "subjects_qualified": ["Maths"],
        "grades_qualified": ["High School 9-10"],
        "years_of_experience": 1.0,
        "expected_fee_etb": 400.0,
        "base_subcity": "Bole",
        "coverage_areas": ["Bole"],
        "availability_schedule": "Weekends"
    }

    response = await async_client.post("/api/v1/tutors/register", json=payload)
    assert response.status_code == 400
    assert "already registered" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_tutor_validation_failure(async_client: AsyncClient):
    """Verifies validation failure on invalid tutor data (e.g. empty coverage areas, negative fee)."""
    invalid_payload = {
        "full_name": "T",  # Too short
        "gender": "Male",
        "phone_number": "123",
        "university": "AAU",
        "department": "Physics",
        "education_year": "3rd Year",
        "subjects_qualified": [],  # Empty
        "grades_qualified": ["High School 9-10"],
        "expected_fee_etb": 0.0,  # Must be > 0
        "base_subcity": "Arada",
        "coverage_areas": [],  # Empty
        "availability_schedule": "Flexible"
    }

    response = await async_client.post("/api/v1/tutors/register", json=invalid_payload)
    assert response.status_code == 422


def test_normalize_database_url_neon():
    """Verifies that channel_binding and sslmode are stripped, scheme is postgresql+asyncpg, and ssl='require' is set."""
    from app.database import normalize_database_url

    raw_neon_url = "postgresql://user:secret@ep-cool-flower-123456.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=prefer"
    clean_url, connect_args = normalize_database_url(raw_neon_url)

    assert clean_url.startswith("postgresql+asyncpg://")
    assert "channel_binding" not in clean_url
    assert "sslmode" not in clean_url
    assert connect_args == {"ssl": "require"}


def test_normalize_database_url_sqlite():
    """Verifies that non-PostgreSQL URLs like SQLite pass through untouched without SSL connect_args."""
    from app.database import normalize_database_url

    raw_sqlite_url = "sqlite+aiosqlite:///./test.db"
    clean_url, connect_args = normalize_database_url(raw_sqlite_url)

    assert clean_url == raw_sqlite_url
    assert connect_args == {}

