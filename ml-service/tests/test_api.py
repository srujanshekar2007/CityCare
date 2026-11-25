from dataclasses import replace

from fastapi.testclient import TestClient

import app.api.routes as routes
from app.config import settings
from app.main import app


client = TestClient(app)


def test_health_exposes_model_state_without_internal_token():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["model_version"]


def test_private_model_info_requires_internal_token():
    response = client.get("/api/v1/model/info")
    assert response.status_code == 503


def test_duplicate_api_validates_coordinate_pair(monkeypatch):
    monkeypatch.setattr(routes, "settings", replace(settings, service_token="test-internal-token"))
    response = client.post("/api/v1/duplicates/analyze", headers={"Authorization":"Bearer test-internal-token"},
                           json={"complaint":{"id":"a","description":"x","latitude":1},"candidates":[]})
    assert response.status_code == 422


def test_duplicate_api_requires_configured_internal_secret(monkeypatch):
    monkeypatch.setattr(routes, "settings", replace(settings, service_token=None))
    response = client.post("/api/v1/duplicates/analyze", json={"complaint":{"id":"a","description":"x"},"candidates":[]})
    assert response.status_code == 503
