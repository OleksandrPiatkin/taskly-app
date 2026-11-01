from unittest.mock import Mock, sentinel

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core import lifespan as lifespan_module


@pytest.fixture
def engine(monkeypatch):
    engine = Mock()
    monkeypatch.setattr(lifespan_module, "create_database_engine", Mock(return_value=engine))
    monkeypatch.setattr(lifespan_module, "initialize", Mock())
    monkeypatch.setattr(
        lifespan_module, "create_session_factory", Mock(return_value=sentinel.session_factory)
    )
    return engine


@pytest.fixture
def app():
    app = FastAPI(lifespan=lifespan_module.lifespan)
    app.state.database_url = "postgresql+psycopg://u:p@h/db"
    return app


def test_lifespan_initializes_database_and_disposes_engine_on_shutdown(engine, app):
    with TestClient(app):
        lifespan_module.create_database_engine.assert_called_once_with("postgresql+psycopg://u:p@h/db")
        lifespan_module.initialize.assert_called_once_with(engine)
        lifespan_module.create_session_factory.assert_called_once_with(engine)
        assert app.state.session_factory is sentinel.session_factory
        engine.dispose.assert_not_called()
    engine.dispose.assert_called_once_with()


def test_lifespan_disposes_engine_when_initialization_fails(engine, app):
    lifespan_module.initialize.side_effect = RuntimeError("schema failed")
    with pytest.raises(RuntimeError, match="schema failed"):
        with TestClient(app):
            pass
    lifespan_module.create_session_factory.assert_not_called()
    assert not hasattr(app.state, "session_factory")
    engine.dispose.assert_called_once_with()
