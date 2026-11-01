from sqlalchemy import create_engine, inspect

from app.core.database import create_database_engine, create_session_factory, initialize


def test_engine_uses_the_postgresql_psycopg_driver():
    url = "postgresql+psycopg://taskly:taskly@localhost:5432/taskly"
    engine = create_database_engine(url)
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.dialect.name == "postgresql"
        assert engine.dialect.driver == "psycopg"
        assert engine.url.database == "taskly"
    finally:
        engine.dispose()


def test_session_factory_is_bound_and_keeps_objects_loaded_after_commit():
    engine = create_engine("sqlite://")
    try:
        factory = create_session_factory(engine)
        assert factory.kw["bind"] is engine
        assert factory.kw["expire_on_commit"] is False
        with factory() as session:
            assert session.get_bind() is engine
    finally:
        engine.dispose()


def test_initialize_creates_the_todos_table():
    engine = create_engine("sqlite://")
    try:
        assert not inspect(engine).has_table("todos")
        initialize(engine)
        columns = {column["name"] for column in inspect(engine).get_columns("todos")}
        assert columns == {
            "id", "title", "description", "priority", "due_date", "completed", "created_at", "updated_at",
        }
    finally:
        engine.dispose()
