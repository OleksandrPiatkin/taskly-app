from datetime import date, datetime, timezone
from unittest.mock import Mock

import pytest

from sqlalchemy import select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from app.features.todos import repository as repository_module
from app.features.todos.models import TodoRecord
from app.features.todos.repository import TodoRepository
from app.features.todos.schemas import Todo, TodoCreate, TodoUpdate


def test_list_maps_models_and_orders_tasks_newest_first(model_factory, todo_values, todo):
    session = Mock(spec=Session)
    session.scalars.return_value = [model_factory(todo_values)]
    assert TodoRepository(session).list() == [todo]
    statement = session.scalars.call_args.args[0]
    expected = select(TodoRecord).order_by(TodoRecord.created_at.desc(), TodoRecord.id.desc())
    assert statement.compare(expected)
    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert "ORDER BY todos.created_at DESC, todos.id DESC" in compiled


def test_get_returns_none_for_missing_task():
    session = Mock(spec=Session)
    session.get.return_value = None
    assert TodoRepository(session).get(404) is None
    session.get.assert_called_once_with(TodoRecord, 404)


FIXED_NOW = datetime(2026, 10, 5, 9, 30, tzinfo=timezone.utc)


@pytest.fixture
def fixed_now(monkeypatch):
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            assert tz is timezone.utc
            return FIXED_NOW

    monkeypatch.setattr(repository_module, "datetime", FixedDateTime)
    return FIXED_NOW


def test_get_maps_an_existing_task(model_factory, todo_values, todo):
    session = Mock(spec=Session)
    session.get.return_value = model_factory(todo_values)
    assert TodoRepository(session).get(7) == todo
    session.get.assert_called_once_with(TodoRecord, 7)


def test_create_stores_payload_with_timestamps_and_returns_saved_task(fixed_now):
    session = Mock(spec=Session)
    # refresh() is where the DB would assign an id; emulate it so mapping to Todo succeeds.
    session.refresh.side_effect = lambda record: setattr(record, "id", 11)
    payload = TodoCreate(title="Write tests", description="backend", priority="low", due_date=date(2026, 11, 3))
    todo = TodoRepository(session).create(payload)
    record = session.add.call_args.args[0]
    assert isinstance(record, TodoRecord)
    assert record.created_at == record.updated_at == fixed_now
    assert todo == Todo(
        id=11, title="Write tests", description="backend", priority="low",
        due_date=date(2026, 11, 3), completed=False, created_at=fixed_now, updated_at=fixed_now,
    )
    session.add.assert_called_once_with(record)
    session.commit.assert_called_once_with()
    session.refresh.assert_called_once_with(record)


def test_update_changes_only_patched_fields_and_bumps_updated_at(model_factory, todo_values, fixed_now):
    session = Mock(spec=Session)
    record = model_factory(todo_values)
    session.get.return_value = record
    todo = TodoRepository(session).update(7, TodoUpdate(completed=True))
    assert todo.completed is True
    assert todo.title == todo_values["title"]
    assert todo.description == todo_values["description"]
    assert todo.priority == "high"
    assert todo.created_at == todo_values["created_at"]
    assert todo.updated_at == fixed_now
    session.get.assert_called_once_with(TodoRecord, 7)
    session.commit.assert_called_once_with()
    session.refresh.assert_called_once_with(record)


def test_update_can_clear_the_due_date(model_factory, todo_values, fixed_now):
    session = Mock(spec=Session)
    session.get.return_value = model_factory({**todo_values, "due_date": date(2026, 10, 15)})
    todo = TodoRepository(session).update(7, TodoUpdate(due_date=None))
    assert todo.due_date is None


def test_update_returns_none_without_committing_for_missing_task():
    session = Mock(spec=Session)
    session.get.return_value = None
    assert TodoRepository(session).update(404, TodoUpdate(title="New")) is None
    session.get.assert_called_once_with(TodoRecord, 404)
    session.commit.assert_not_called()
    session.refresh.assert_not_called()


def test_delete_removes_existing_task_and_commits(model_factory, todo_values):
    session = Mock(spec=Session)
    record = model_factory(todo_values)
    session.get.return_value = record
    assert TodoRepository(session).delete(7) is True
    session.delete.assert_called_once_with(record)
    session.commit.assert_called_once_with()


def test_delete_returns_false_without_committing_for_missing_task():
    session = Mock(spec=Session)
    session.get.return_value = None
    assert TodoRepository(session).delete(404) is False
    session.get.assert_called_once_with(TodoRecord, 404)
    session.delete.assert_not_called()
    session.commit.assert_not_called()
