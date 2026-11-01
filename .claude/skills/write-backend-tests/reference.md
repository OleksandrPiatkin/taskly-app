# Backend test patterns

All examples follow the existing tests in `backend/tests/`. Imports are absolute from `app.`.

## Membership, not exact collections

When the behaviour is "X is present", assert membership — never equality with a full collection
(all routes, all keys, every call). Exact collections break on every unrelated addition.

```python
paths = app.openapi()["paths"]
assert {"get", "post"} <= set(paths["/api/todos"])      # not: assert paths.keys() == {...}
```

Use exact equality only when exactness *is* the behaviour (e.g. a response body, `assert_called_once_with`).

## Router — via the `client` fixture

`client` mounts only the todos router with `get_repository` overridden by `repository_mock`
(an autospec of `TodoRepository`), so a wrong method name fails the test.

```python
def test_get_returns_404_when_task_is_missing(client, repository_mock):
    repository_mock.get.return_value = None
    response = client.get("/api/todos/7")
    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found."}
    repository_mock.get.assert_called_once_with(7)


@pytest.mark.parametrize("todo_id", [0, -1])
def test_rejects_non_positive_ids(client, repository_mock, todo_id):
    assert client.get(f"/api/todos/{todo_id}").status_code == 422
    repository_mock.get.assert_not_called()
```

`DELETE` success returns 204 with an empty body: assert `response.content == b""`.

## Repository — with a mocked Session

```python
from unittest.mock import Mock
from sqlalchemy.orm import Session

from app.features.todos.repository import TodoRepository


def test_create_commits_and_returns_the_saved_task():
    session = Mock(spec=Session)
    # refresh() is where the DB would assign an id; emulate it so mapping to Todo succeeds.
    session.refresh.side_effect = lambda record: setattr(record, "id", 7)
    todo = TodoRepository(session).create(TodoCreate(title="Write tests"))
    assert todo.id == 7 and todo.title == "Write tests"
    session.add.assert_called_once()
    session.commit.assert_called_once_with()
```

For `get`/`update`/`delete`, set `session.get.return_value` to `model_factory(todo_values)` or `None`.
For `update`, check only fields in the patch changed (`exclude_unset`) and `updated_at` moved forward.

## Generator dependency — `get_repository`

```python
session = Mock()
app = SimpleNamespace(state=SimpleNamespace(session_factory=Mock(return_value=session)))
dependency = get_repository(Request({"type": "http", "app": app}))
repository = next(dependency)
assert repository.session is session
with pytest.raises(StopIteration):
    next(dependency)              # normal exit → close only
session.close.assert_called_once_with()
session.rollback.assert_not_called()
```

Error path: after `next(dependency)`, call `dependency.throw(RuntimeError("boom"))` inside
`pytest.raises(RuntimeError)`, then assert `rollback` and `close` were both called.

## Config — environment isolation

```python
from app.core import config


def test_builds_postgres_url_from_parts(monkeypatch):
    monkeypatch.setattr(config, "load_dotenv", lambda *a, **k: None)  # never read a developer's .env
    monkeypatch.delenv("DATABASE_URL", raising=False)
    for key, value in {"POSTGRES_USER": "u", "POSTGRES_PASSWORD": "p", "POSTGRES_HOST": "h",
                       "DB_PORT": "5433", "POSTGRES_DB": "d"}.items():
        monkeypatch.setenv(key, value)
    assert config.resolve_database_url() == "postgresql+psycopg://u:p@h:5433/d"
```

Also cover: an explicit argument wins over `DATABASE_URL`, and `DATABASE_URL` wins over the parts.

## Lifespan, factory, health — no real database

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core import lifespan as lifespan_module


def test_lifespan_creates_session_factory_and_disposes_engine(monkeypatch):
    engine = Mock()
    monkeypatch.setattr(lifespan_module, "create_database_engine", Mock(return_value=engine))
    monkeypatch.setattr(lifespan_module, "initialize", Mock())
    monkeypatch.setattr(lifespan_module, "create_session_factory", Mock(return_value="factory"))
    app = FastAPI(lifespan=lifespan_module.lifespan)
    app.state.database_url = "sqlite://"
    with TestClient(app):
        assert app.state.session_factory == "factory"
    engine.dispose.assert_called_once_with()
```

Also test that `dispose()` still runs when `initialize` raises. `create_app("sqlite://")` does not
connect until startup, so assert `app.state.database_url` and registered route paths without
entering the lifespan. For `health`, mount its router on a bare `FastAPI` with
`dependency_overrides[get_repository]` returning a `Mock()` repository and assert
`repo.session.execute` was called.

`database.create_session_factory` / `initialize`: use a real in-memory engine
(`create_engine("sqlite://")`) — it is local and fast — and assert the factory is bound and
`expire_on_commit` is `False`, and that `initialize` creates the `todos` table.
