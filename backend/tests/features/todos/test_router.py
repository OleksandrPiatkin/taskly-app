import pytest

from app.features.todos.schemas import TodoCreate, TodoUpdate


def test_list_returns_tasks_from_repository(client, repository_mock, todo):
    repository_mock.list.return_value = [todo]
    response = client.get("/api/todos")
    assert response.status_code == 200
    assert response.json() == [todo.model_dump(mode="json")]
    repository_mock.list.assert_called_once_with()


def test_create_trims_input_and_returns_created_task(client, repository_mock, todo):
    repository_mock.create.return_value = todo
    response = client.post("/api/todos", json={"title": "  Plan the sprint  ", "priority": "high"})
    assert response.status_code == 201
    assert response.json() == todo.model_dump(mode="json")
    repository_mock.create.assert_called_once_with(
        TodoCreate(title="Plan the sprint", priority="high")
    )


@pytest.mark.parametrize("payload", [
    {"title": "   "},
    {"title": "x" * 121},
    {"title": "Task", "priority": "urgent"},
    {"title": "Task", "due_date": "2026-02-30"},
])
def test_invalid_create_never_calls_repository(client, repository_mock, payload):
    assert client.post("/api/todos", json=payload).status_code == 422
    repository_mock.create.assert_not_called()


def test_get_returns_the_task(client, repository_mock, todo):
    repository_mock.get.return_value = todo
    response = client.get("/api/todos/7")
    assert response.status_code == 200
    assert response.json() == todo.model_dump(mode="json")
    repository_mock.get.assert_called_once_with(7)


def test_get_returns_404_when_task_is_missing(client, repository_mock):
    repository_mock.get.return_value = None
    response = client.get("/api/todos/7")
    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found."}
    repository_mock.get.assert_called_once_with(7)


@pytest.mark.parametrize("method", ["get", "patch", "delete"])
@pytest.mark.parametrize("todo_id", ["0", "-1", "abc"])
def test_rejects_invalid_ids_without_calling_repository(client, repository_mock, method, todo_id):
    kwargs = {"json": {"title": "x"}} if method == "patch" else {}
    response = getattr(client, method)(f"/api/todos/{todo_id}", **kwargs)
    assert response.status_code == 422
    getattr(repository_mock, method if method != "patch" else "update").assert_not_called()


def test_update_trims_input_and_returns_updated_task(client, repository_mock, todo):
    repository_mock.update.return_value = todo
    response = client.patch("/api/todos/7", json={"title": "  Plan the sprint  ", "due_date": None})
    assert response.status_code == 200
    assert response.json() == todo.model_dump(mode="json")
    repository_mock.update.assert_called_once_with(7, TodoUpdate(title="Plan the sprint", due_date=None))
    patch = repository_mock.update.call_args.args[1]
    assert patch.model_fields_set == {"title", "due_date"}


def test_update_returns_404_when_task_is_missing(client, repository_mock):
    repository_mock.update.return_value = None
    response = client.patch("/api/todos/7", json={"completed": True})
    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found."}
    repository_mock.update.assert_called_once_with(7, TodoUpdate(completed=True))


@pytest.mark.parametrize("payload", [
    {},
    {"title": None},
    {"completed": None},
    {"title": "   "},
    {"completed": "yes"},
    {"unknown": 1},
])
def test_invalid_update_never_calls_repository(client, repository_mock, payload):
    assert client.patch("/api/todos/7", json=payload).status_code == 422
    repository_mock.update.assert_not_called()


def test_delete_returns_204_with_empty_body(client, repository_mock):
    repository_mock.delete.return_value = True
    response = client.delete("/api/todos/7")
    assert response.status_code == 204
    assert response.content == b""
    repository_mock.delete.assert_called_once_with(7)


def test_delete_returns_404_when_task_is_missing(client, repository_mock):
    repository_mock.delete.return_value = False
    response = client.delete("/api/todos/7")
    assert response.status_code == 404
    assert response.json() == {"detail": "Task not found."}
    repository_mock.delete.assert_called_once_with(7)


def test_count_returns_total_and_completed(client, repository_mock, todo):
    done = todo.model_copy(update={"id": 8, "completed": True})
    repository_mock.list.return_value = [todo, done, done]
    response = client.get("/api/todos/count")
    assert response.status_code == 200
    assert response.json() == {"total": 3, "completed": 2}
    repository_mock.list.assert_called_once_with()
    repository_mock.get.assert_not_called()


def test_count_returns_zeros_when_there_are_no_tasks(client, repository_mock):
    repository_mock.list.return_value = []
    response = client.get("/api/todos/count")
    assert response.status_code == 200
    assert response.json() == {"total": 0, "completed": 0}
