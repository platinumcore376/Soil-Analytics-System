"""Shared fixtures.

Tests run against an IN-MEMORY SQLITE database — the configured PostgreSQL
(Supabase in the current .env) is never touched. That isolation works because:

  * every model column is a generic SQLAlchemy type (String/Float/DateTime/
    Boolean), so the schema builds identically on SQLite;
  * all app DB access goes through app.database's module globals (engine,
    SessionLocal, get_db) which are read at call time, so swapping them here —
    BEFORE app.main is imported and its lifespan runs init_db() — reroutes
    everything, including the startup create_all.

Environment overrides must happen before the first `app.config` import:
pydantic-settings gives real environment variables precedence over .env files.
"""
import itertools
import os
import tempfile

os.environ["JWT_SECRET"] = "unit-test-secret-0123456789abcdefghijklmnop"
os.environ["SARVAM_API_KEY"] = ""  # deterministic: TTS is "not configured" unless a test patches it
# Pin to the app default: a developer's local .env may enable the retention sweep
# (e.g. IMAGE_RETENTION_HOURS=1), which would make sweep tests depend on their machine.
os.environ["IMAGE_RETENTION_HOURS"] = "0"
# Never touches real DB — test runs on in-memory SQLite.
os.environ["DATABASE_URL"] = "sqlite://"
_tmp = tempfile.mkdtemp(prefix="soil-health-tests-")
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
os.environ["PROCESSED_DIR"] = os.path.join(_tmp, "processed")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database as database

# StaticPool keeps the single in-memory database alive across TestClient's
# worker threads; check_same_thread=False is required for the same reason.
_test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    future=True,
)


@event.listens_for(_test_engine, "connect")
def _enable_fks(dbapi_conn, _record):
    # SQLite ignores ON DELETE CASCADE unless foreign keys are switched on.
    dbapi_conn.execute("PRAGMA foreign_keys=ON")


database.engine = _test_engine
database.SessionLocal = sessionmaker(bind=_test_engine, autoflush=False, autocommit=False)

# Import order matters: app.main's lifespan calls init_db(), which must already
# see the swapped engine when TestClient triggers startup.
from app.database import Base  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    # Context manager so the lifespan (init_db → create_all on SQLite) runs.
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _fresh_db():
    """Every test starts from an empty schema — no cross-test bleed."""
    Base.metadata.drop_all(bind=_test_engine)
    Base.metadata.create_all(bind=_test_engine)
    yield


_phone_seq = itertools.count(1)


@pytest.fixture
def make_user(client):
    """Register a fresh user; returns auth headers plus the raw credentials."""

    def _make(name: str = "Test Farmer", password: str = "testpass123"):
        phone = f"9{next(_phone_seq):09d}"
        r = client.post(
            "/auth/register",
            json={"phone": phone, "name": name, "password": password},
        )
        assert r.status_code == 201, r.text
        body = r.json()
        return {
            "headers": {"Authorization": f"Bearer {body['access_token']}"},
            "phone": phone,
            "password": password,
            "user": body["user"],
        }

    return _make


@pytest.fixture
def make_field(client):
    """Create a farm + field for the given auth headers; returns (farm, field)."""

    def _make(headers, farm_name="Unit Farm", field_name="Unit Field"):
        farm = client.post(
            "/farms",
            json={"name": farm_name, "location": "Testville"},
            headers=headers,
        )
        assert farm.status_code == 201, farm.text
        field = client.post(
            "/fields",
            json={"farm_id": farm.json()["id"], "name": field_name, "area_hectares": 1.0},
            headers=headers,
        )
        assert field.status_code == 201, field.text
        return farm.json(), field.json()

    return _make


# Index-scale readings (NOT kg/ha) reused across tests.
HEALTHY_READINGS = {
    "nitrogen": 90,
    "phosphorus": 45,
    "potassium": 45,
    "ph": 6.5,
    "organic_matter": 3.0,
    "moisture": 30,
}
DEPLETED_READINGS = {
    "nitrogen": 8,
    "phosphorus": 6,
    "potassium": 8,
    "ph": 4.6,
    "organic_matter": 0.3,
    "moisture": 10,
}
