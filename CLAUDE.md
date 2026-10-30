# Taskly App

Full-stack todo app: React + TypeScript frontend (`frontend/`), FastAPI backend (`backend/`).
Both test suites are fully mocked — no database, network or Docker is needed to run them.

## Commands

Always run commands from the package directory. Running pytest from the repo root picks up
`pytest.ini` instead of `backend/pyproject.toml`, silently disabling branch coverage and the
coverage omit list — the numbers are then wrong.

Backend (Python 3.12 is the target runtime; see `backend/Dockerfile`). Locally, backend commands run
inside the virtualenv at `backend/.venv` (created once from the repo root):

```sh
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -r backend/requirements.txt
```

If the venv is not activated, call its interpreter directly: `.venv/bin/python -m pytest` (from `backend/`).
In CI there is no venv; `python` is the job's Python 3.12. Never install packages yourself.

```sh
cd backend
python -m pytest                                   # tests
python -m pytest --cov=app --cov-report=term-missing --cov-report=xml --cov-report=json
                                                   # coverage → backend/coverage/{coverage.xml,coverage.json,html/}
```

Frontend (Node >= 22.12):

```sh
cd frontend
npm ci --ignore-scripts
npm test                                           # vitest run
npm run test:coverage                              # → frontend/coverage/{lcov.info,coverage-summary.json}
npm run typecheck
```

Known noise: `StarletteDeprecationWarning` about `httpx`/`httpx2` comes from FastAPI's TestClient.
Ignore it; do not change dependencies to silence it.

## Layout

- `backend/app/features/todos/` — router, repository, schemas (Pydantic v2), validators, mappers, models (SQLAlchemy 2)
- `backend/app/{api,core}/` — dependencies, health endpoint, config, database, lifespan; `app/factory.py` builds the app
- `frontend/src/features/todos/` — `TodosPage`, `components/`, `hooks/` (TanStack Query), `api/`, `utils/`
- `frontend/src/lib/http.ts` — `fetch` wrapper; `frontend/src/design-system/` — UI kit (excluded from coverage, has Storybook stories)

Coverage scope is defined in `backend/pyproject.toml` (`[tool.coverage.run] omit`) and
`frontend/vite.config.ts` (`test.coverage.exclude`). Do not write tests just for excluded files
(schemas, models, `main.py`, `design-system/**`, `types.ts`, `index.ts`, stories, styles).

## Test conventions

Backend (`backend/tests/` mirrors `backend/app/`, files named `test_<module>.py`):
- Plain `def test_<behaviour>()` functions, no classes; `@pytest.mark.parametrize` for input variations.
- Reuse fixtures from `tests/conftest.py`: `client` (router mounted on a bare `FastAPI` with
  `dependency_overrides`), `repository_mock`, `todo_values`, `todo`, `model_factory`.
- Repository mocks come from `tests/mocks.py` (`create_autospec(TodoRepository)`); session/engine
  doubles use `unittest.mock.Mock`. Use `monkeypatch` for environment variables.
- Assert on status code, JSON body and the mock call (`assert_called_once_with`, `assert_not_called`).

Frontend (test file next to the source: `Foo.tsx` → `Foo.test.tsx`, `foo.ts` → `foo.test.ts`):
- Vitest + Testing Library + `@testing-library/user-event`; jest-dom matchers are set up in `src/test/setup.ts`.
- Top-level `it('<behaviour>')` blocks, no `describe` nesting; import `expect, it, vi` from `vitest`.
- Mock the design system with `vi.mock('<relative>/design-system', () => import('<relative>/design-system/mocks'))`.
- Mock child components and modules with `vi.mock`; mock `lib/http` `request` in API tests, stub
  `fetch` with `vi.stubGlobal` when testing `lib/http.ts` itself.
- Hooks: `renderHook` with a fresh `QueryClient` (`retry: false`) wrapped in `QueryClientProvider`.
- Use `src/test/todoFixture.ts` for task data. Query by role/label/text, not by test id or class.

## Rules for writing tests

- Never modify production code under `backend/app/` or `frontend/src/` (except `*.test.ts(x)`),
  configs, lockfiles or dependencies. If code looks buggy, report it; do not "fix" it in a test PR.
- No `skip`, `xfail`, `.only`, `.todo`, snapshot-only tests, or assertions that always pass.
- Tests must be deterministic: no real network, timers or dates without fakes/fixed values.
- Every new test must pass locally, and the full suite must stay green, before you finish.
