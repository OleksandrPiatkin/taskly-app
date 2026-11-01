---
name: write-backend-tests
description: Write or update pytest unit tests for the Taskly FastAPI backend (backend/app) following the project's fixtures and mocking conventions. Use when backend source files need new or updated tests.
---

# Write backend tests (pytest)

1. Read the source file and its test file (`backend/tests/<mirrored path>/test_<module>.py`) and
   `backend/tests/conftest.py`. Reuse existing fixtures; add new shared fixtures to `conftest.py`
   only if two or more test files need them.
2. List the behaviours to cover: each public function/endpoint, each branch (`if`, `except`,
   early `return`), each status code. Target the lines the diff changed and any lines reported
   as missing in `backend/coverage/coverage.json`.
3. Write tests using the patterns in [reference.md](reference.md) — read it before writing the
   first test for a new kind of module (router, repository, dependency, config, lifespan).
4. Run only the file you changed first, then the full suite via `run-tests-and-coverage`:

   ```sh
   cd backend && python -m pytest tests/features/todos/test_router.py -q
   ```

## Rules

- No real database, network or `.env`: mock the SQLAlchemy `Session`/engine, use the `client`
  fixture for HTTP, patch `load_dotenv` in config tests.
- One behaviour per test; name it `test_<what>_<expected>()`. Use `parametrize` for input tables.
- Assert observable results (status, JSON, return value) **and** the important interactions
  (`commit`, `rollback`, `close`, repository calls). Do not assert private details that do not matter.
- Pydantic validation is part of the API contract: test it through the router (422 + repository
  not called), not by unit-testing `schemas.py`.
