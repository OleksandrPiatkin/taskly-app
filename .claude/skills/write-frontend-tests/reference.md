# Frontend test patterns

Copied from, or consistent with, the existing tests in `frontend/src/`.

## Membership, not exact collections

When the behaviour is "X is present", assert membership — never equality with a full collection
(every rendered item, all object keys, the complete list of mock calls). Exact collections break on
every unrelated addition.

```ts
expect(screen.getByRole('button', { name: 'Clear search' })).toBeInTheDocument()
expect(payload).toMatchObject({ title: 'Write tests' })          // not: toEqual({...every key})
expect(onChange).toHaveBeenCalledWith('done')                     // not: toEqual(onChange.mock.calls)
```

Use exact equality only when exactness *is* the behaviour (e.g. a request body with only writable fields).

## Components — mock the design system and children

```tsx
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { todoFixture } from '../../../test/todoFixture'
import { TodoItem } from './TodoItem'

vi.mock('../../../design-system', () => import('../../../design-system/mocks'))

it('asks to delete the task when the delete button is pressed', async () => {
  const user = userEvent.setup()
  const onDelete = vi.fn()
  render(<TodoItem todo={todoFixture} onDelete={onDelete} /* other required props */ />)
  await user.click(screen.getByRole('button', { name: /delete/i }))
  expect(onDelete).toHaveBeenCalledWith(todoFixture)
})
```

Read the component's props type before rendering; pass `vi.fn()` for every callback.
`vi.mock` is hoisted — the factory must not reference variables declared in the test file
(use `vi.hoisted` if you really need that).

## Hooks using TanStack Query

If `src/test/queryClientWrapper.tsx` exists, **reuse its `createQueryWrapper()`** (returns
`{ client, wrapper }` with a fresh client per call) instead of defining a new wrapper. The example
below shows what it does; only define one inline if the helper is missing.

Waiting: TanStack Query state (e.g. `useIsMutating`) can update a tick after the mutation settles —
assert it with `await waitFor(...)`, never with fixed sleeps.

```tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { todosApi } from '../api/todos'
import { todoKeys } from '../api/queryKeys'

vi.mock('../api/todos', () => ({
  todosApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() },
}))

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return { client, wrapper }
}

it('prepends the created task to the cached list', async () => {
  const { client, wrapper } = setup()
  client.setQueryData(todoKeys.list, [{ ...todoFixture, id: 1 }])
  vi.mocked(todosApi.create).mockResolvedValue(todoFixture)
  const { result } = renderHook(() => useCreateTodoMutation(), { wrapper })
  await result.current.mutateAsync(todoFixture)
  expect(client.getQueryData(todoKeys.list)).toEqual([todoFixture, { ...todoFixture, id: 1 }])
})
```

Create a new `QueryClient` per test — never import the app singleton from `lib/queryClient`.
For queries: `await waitFor(() => expect(result.current.isSuccess).toBe(true))`, and check the
`AbortSignal` was passed to `todosApi.list`. Plain state hooks (`useTodoFilters`, `useNotice`)
need no wrapper: use `renderHook` + `act`.

## `lib/http.ts` — stub `fetch`

```ts
import { afterEach, expect, it, vi } from 'vitest'
import { request } from './http'

afterEach(() => vi.unstubAllGlobals())

function respond(status: number, body?: unknown) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body })
}

it('uses the server detail message for failed requests', async () => {
  vi.stubGlobal('fetch', respond(404, { detail: 'Task not found.' }))
  await expect(request('/todos/1')).rejects.toThrow('Task not found.')
})
```

Branches to cover: success JSON; 204 → `undefined`; JSON headers merged with caller headers;
422 → validation message; non-string `detail` or unreadable body → generic message; `fetch`
rejecting → "Cannot connect…"; `fetch` rejecting with an aborted signal → original error re-thrown.

## API modules — mock `request`

See `src/features/todos/api/todos.test.ts`: `vi.mock('../../../lib/http', () => ({ request: vi.fn() }))`
and assert the exact path and `init` (method, body with only writable fields).

## Providers

`AppProviders` accepts a `client` prop — pass a fresh `QueryClient` and assert children render.
