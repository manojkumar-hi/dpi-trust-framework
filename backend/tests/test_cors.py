import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

def test_cors_allowed_origin_localhost():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Authorization"
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "Authorization" in response.headers.get("access-control-allow-headers", "")

def test_cors_allowed_origin_127():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Idempotency-Key"
        }
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"
    assert "Idempotency-Key" in response.headers.get("access-control-allow-headers", "")

def test_cors_disallowed_origin():
    response = client.options(
        "/health",
        headers={
            "Origin": "http://malicious.com",
            "Access-Control-Request-Method": "GET"
        }
    )
    assert response.status_code == 400
    assert response.text == "Disallowed CORS origin"


