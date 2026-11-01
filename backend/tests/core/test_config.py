from unittest.mock import Mock

import pytest

from app.core import config

DB_PARTS = {
    "POSTGRES_USER": "taskly",
    "POSTGRES_PASSWORD": "s3cret",
    "POSTGRES_HOST": "db.local",
    "DB_PORT": "5433",
    "POSTGRES_DB": "tasks",
}


@pytest.fixture
def load_dotenv_mock(monkeypatch):
    load_dotenv = Mock()
    monkeypatch.setattr(config, "load_dotenv", load_dotenv)  # never read a developer's .env
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for key in DB_PARTS:
        monkeypatch.delenv(key, raising=False)
    return load_dotenv


@pytest.fixture
def db_parts(monkeypatch):
    for key, value in DB_PARTS.items():
        monkeypatch.setenv(key, value)


def test_explicit_url_wins_over_environment(load_dotenv_mock, db_parts, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://env/db")
    assert config.resolve_database_url("sqlite://") == "sqlite://"


def test_database_url_env_wins_over_parts(load_dotenv_mock, db_parts, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://env/db")
    assert config.resolve_database_url() == "postgresql+psycopg://env/db"


@pytest.mark.parametrize("database_url", [None, ""])
def test_builds_postgres_url_from_parts_without_explicit_url(load_dotenv_mock, db_parts, database_url):
    assert (
        config.resolve_database_url(database_url)
        == "postgresql+psycopg://taskly:s3cret@db.local:5433/tasks"
    )


def test_loads_repo_root_dotenv_without_overriding_environment(load_dotenv_mock):
    config.resolve_database_url("sqlite://")
    load_dotenv_mock.assert_called_once()
    path = load_dotenv_mock.call_args.args[0]
    assert path.name == ".env"
    assert (path.parent / "backend" / "app" / "core" / "config.py").is_file()
    assert load_dotenv_mock.call_args.kwargs == {"override": False}


@pytest.mark.parametrize("missing", sorted(DB_PARTS))
def test_missing_connection_part_raises_key_error(load_dotenv_mock, db_parts, monkeypatch, missing):
    monkeypatch.delenv(missing)
    with pytest.raises(KeyError, match=missing):
        config.resolve_database_url()


def test_non_numeric_port_raises_value_error(load_dotenv_mock, db_parts, monkeypatch):
    monkeypatch.setenv("DB_PORT", "not-a-port")
    with pytest.raises(ValueError):
        config.resolve_database_url()
