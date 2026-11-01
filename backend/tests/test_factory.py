from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

from app import factory
from app.core import config
from app.core import lifespan as lifespan_module


@pytest.fixture(autouse=True)
def no_dotenv(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", Mock())
    monkeypatch.delenv("DATABASE_URL", raising=False)


def test_create_app_stores_explicit_database_url():
    app = factory.create_app("sqlite://")
    assert app.state.database_url == "sqlite://"
    assert app.title == "Taskly API"
    assert app.version == "1.0.0"


def test_create_app_falls_back_to_database_url_env(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://env/db")
    assert factory.create_app().state.database_url == "postgresql+psycopg://env/db"


def test_create_app_registers_health_and_todo_routes():
    app = factory.create_app("sqlite://")
    # Included routers are not flattened into app.routes; the OpenAPI schema is the public contract.
    paths = app.openapi()["paths"]
    expected = {
        "/api/health": {"get"},
        "/api/todos": {"get", "post"},
        "/api/todos/{todo_id}": {"get", "patch", "delete"},
    }
    for path, operations in expected.items():
        assert path in paths
        assert operations <= set(paths[path])


def test_create_app_wires_lifespan_session_factory_into_requests(monkeypatch):
    engine = Mock()
    session = Mock()
    monkeypatch.setattr(lifespan_module, "create_database_engine", Mock(return_value=engine))
    monkeypatch.setattr(lifespan_module, "initialize", Mock())
    monkeypatch.setattr(lifespan_module, "create_session_factory", Mock(return_value=Mock(return_value=session)))
    app = factory.create_app("postgresql+psycopg://u:p@h/db")
    with TestClient(app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    lifespan_module.create_database_engine.assert_called_once_with("postgresql+psycopg://u:p@h/db")
    session.execute.assert_called_once()
    session.close.assert_called_once_with()
    engine.dispose.assert_called_once_with()
