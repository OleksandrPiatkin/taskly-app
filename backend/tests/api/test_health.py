from unittest.mock import Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.dependencies import get_repository
from app.api.health import router
from app.features.todos.models import TodoRecord


@pytest.fixture
def health_repository():
    return Mock()


@pytest.fixture
def health_app(health_repository):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_repository] = lambda: health_repository
    return app


def test_health_pings_the_database_and_reports_ok(health_app, health_repository):
    with TestClient(health_app) as client:
        response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    health_repository.session.execute.assert_called_once()
    statement = health_repository.session.execute.call_args.args[0]
    assert statement.compare(select(TodoRecord.id).limit(1))


def test_health_returns_500_when_the_database_is_unreachable(health_app, health_repository):
    health_repository.session.execute.side_effect = RuntimeError("database down")
    with TestClient(health_app, raise_server_exceptions=False) as client:
        response = client.get("/api/health")
    assert response.status_code == 500
    health_repository.session.execute.assert_called_once()
