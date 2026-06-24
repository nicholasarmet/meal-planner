import os
import pytest
from pathlib import Path
from unittest.mock import patch
from scripts.models import Recipe


def _recipe(title="Test Recipe"):
    return Recipe(title=title, meal_type=["dinner"])


@pytest.fixture
def app(tmp_path, monkeypatch):
    config = tmp_path / "config.yaml"
    config.write_text(f"vault_path: {tmp_path}\ndietary_mode: normal\n")
    monkeypatch.setenv("MEAL_PLANNER_CONFIG", str(config))
    monkeypatch.setenv("RECIPE_SERVER_API_KEY", "test-key")
    from scripts.recipe_server import create_app
    return create_app()


@pytest.fixture
def client(app):
    return app.test_client()


def test_missing_api_key_returns_401(client):
    resp = client.post("/add-recipe", json={"url": "https://example.com"})
    assert resp.status_code == 401
    assert "Unauthorized" in resp.get_json()["error"]


def test_wrong_api_key_returns_401(client):
    resp = client.post(
        "/add-recipe",
        json={"url": "https://example.com"},
        headers={"X-API-Key": "wrong"},
    )
    assert resp.status_code == 401


def test_missing_url_returns_400(client):
    resp = client.post("/add-recipe", json={}, headers={"X-API-Key": "test-key"})
    assert resp.status_code == 400
    assert "url" in resp.get_json()["error"].lower()


def test_non_http_url_returns_400(client):
    resp = client.post(
        "/add-recipe",
        json={"url": "ftp://something"},
        headers={"X-API-Key": "test-key"},
    )
    assert resp.status_code == 400
    assert "Invalid" in resp.get_json()["error"]


def test_valid_request_returns_200(client):
    with patch("scripts.recipe_server.ingest_from_url", return_value=_recipe()), \
         patch("scripts.recipe_server.save_recipe",
               return_value=Path("/tmp/vault/Recipes/Dinner/test.md")):
        resp = client.post(
            "/add-recipe",
            json={"url": "https://seriouseats.com/chicken-adobo"},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["status"] == "ok"
    assert data["title"] == "Test Recipe"
    assert "path" in data


def test_ingest_error_returns_500(client):
    with patch("scripts.recipe_server.ingest_from_url",
               side_effect=RuntimeError("scraping failed")):
        resp = client.post(
            "/add-recipe",
            json={"url": "https://example.com/recipe"},
            headers={"X-API-Key": "test-key"},
        )
    assert resp.status_code == 500
    assert "scraping failed" in resp.get_json()["error"]
