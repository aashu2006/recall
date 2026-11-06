import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app

TEST_VERIFY_TOKEN = "test-verify-token"


@pytest.fixture(autouse=True)
def no_real_http(monkeypatch):
    """Fail any test that tries a real network call (Gnani credits). MockTransport still works."""

    def blocked(self, request):
        raise RuntimeError(f"Real HTTP call blocked in tests: {request.method} {request.url}")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked)


@pytest.fixture
def client():
    # Never read the real .env in tests.
    app.dependency_overrides[get_settings] = lambda: Settings(
        _env_file=None, wa_verify_token=TEST_VERIFY_TOKEN
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
