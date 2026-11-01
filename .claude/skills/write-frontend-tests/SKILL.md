---
name: write-frontend-tests
description: Write or update Vitest + React Testing Library unit tests for the Taskly frontend (frontend/src) - components, hooks, API modules and utils - following the project's mocking conventions. Use when frontend source files need new or updated tests.
---

# Write frontend tests (Vitest + Testing Library)

1. Read the source file, its sibling `*.test.ts(x)` if it exists, and 1–2 neighbouring tests to
   copy their mock setup. Test file lives next to the source: `Foo.tsx` → `Foo.test.tsx`.
2. List behaviours: rendered states (loading / empty / error / data), user interactions and the
   callbacks they fire, hook return values and cache updates, request shapes and error mapping.
   Target lines the diff changed and uncovered lines from `frontend/coverage/coverage-final.json`
   or the text report.
3. Write tests using [reference.md](reference.md) — read it before testing a hook, `lib/http.ts`,
   or a component that uses the design system.
4. Run the file first, then the full suite and typecheck via `run-tests-and-coverage`:

   ```sh
   cd frontend && npx vitest run src/features/todos/components/TodoList.test.tsx
   ```

## Rules

- Top-level `it('<user-visible behaviour>')`, no `describe` nesting; import `expect, it, vi` from `vitest`.
- Query by role, label or text (`getByRole('button', { name: 'Delete' })`); never by class or test id.
- Interactions via `userEvent.setup()`; await every interaction.
- Mock at module boundaries with `vi.mock` (design system, child components, hooks, `lib/http`).
  Do not mock the unit under test. Reset with `beforeEach(() => vi.clearAllMocks())` when mocks carry state.
- No real network or timers: stub `fetch`, use `vi.useFakeTimers()` when code depends on time.
- New test files must type-check (`npm run typecheck`).
