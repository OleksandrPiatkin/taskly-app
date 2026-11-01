import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import { todoFixture } from '../../test/todoFixture'
import { useNotice } from '../../hooks/useNotice'
import { useTodoFilters } from './hooks/useTodoFilters'
import { useTodosBusy } from './hooks/useTodosBusy'
import { useTodosQuery } from './hooks/useTodosQuery'
import { useUpdateTodoMutation } from './hooks/useUpdateTodoMutation'
import { TodosPage } from './TodosPage'
import type { Todo } from './types'

vi.mock('../../design-system', () => import('../../design-system/mocks'))
vi.mock('../../hooks/useNotice', () => ({ useNotice: vi.fn() }))
vi.mock('./hooks/useTodoFilters', () => ({ useTodoFilters: vi.fn() }))
vi.mock('./hooks/useTodosBusy', () => ({ useTodosBusy: vi.fn() }))
vi.mock('./hooks/useTodosQuery', () => ({ useTodosQuery: vi.fn() }))
vi.mock('./hooks/useUpdateTodoMutation', () => ({
  useUpdateTodoMutation: vi.fn(),
}))
vi.mock('./components/TodosHeader', () => ({
  TodosHeader: ({
    disabled,
    onCreate,
  }: {
    disabled: boolean
    onCreate: () => void
  }) => (
    <button disabled={disabled} onClick={onCreate}>
      New task
    </button>
  ),
}))
vi.mock('./components/TodoFilters', () => ({
  TodoFilters: ({
    filter,
    search,
    sort,
  }: {
    filter: string
    search: string
    sort: string
  }) => <p>{`Filters: ${filter}/${search}/${sort}`}</p>,
}))
vi.mock('./components/TodoList', () => ({
  TodoList: ({
    todos,
    hasTodos,
    loading,
    failed,
    busy,
    onCreate,
    onToggle,
    onEdit,
    onDelete,
  }: {
    todos: Todo[]
    hasTodos: boolean
    loading: boolean
    failed: boolean
    busy: boolean
    onCreate: () => void
    onToggle: (todo: Todo) => void
    onEdit: (todo: Todo) => void
    onDelete: (todo: Todo) => void
  }) => (
    <section aria-label="Task list">
      <p>{`List: ${todos.length} visible, hasTodos=${hasTodos}, loading=${loading}, failed=${failed}, busy=${busy}`}</p>
      <button onClick={onCreate}>Create from list</button>
      {todos.map((todo) => (
        <div key={todo.id}>
          <button onClick={() => onToggle(todo)}>{`Toggle ${todo.title}`}</button>
          <button onClick={() => onEdit(todo)}>{`Edit ${todo.title}`}</button>
          <button onClick={() => onDelete(todo)}>{`Delete ${todo.title}`}</button>
        </div>
      ))}
    </section>
  ),
}))
vi.mock('./components/TodoEditor', () => ({
  TodoEditor: ({
    todo,
    onClose,
    onSaved,
  }: {
    todo: Todo | 'new'
    onClose: () => void
    onSaved: (message: string) => void
  }) => (
    <div role="dialog" aria-label={todo === 'new' ? 'Editor: new' : `Editor: ${todo.title}`}>
      <button onClick={onClose}>Close editor</button>
      <button onClick={() => onSaved('Changes saved.')}>Save editor</button>
    </div>
  ),
}))
vi.mock('./components/DeleteTodoDialog', () => ({
  DeleteTodoDialog: ({
    todo,
    onClose,
    onDeleted,
  }: {
    todo: Todo
    onClose: () => void
    onDeleted: () => void
  }) => (
    <div role="dialog" aria-label={`Delete: ${todo.title}`}>
      <button onClick={onClose}>Close delete</button>
      <button onClick={onDeleted}>Confirm delete</button>
    </div>
  ),
}))
vi.mock('../../components/SuccessNotice', () => ({
  SuccessNotice: ({ message }: { message: string }) =>
    message ? <p role="status">{message}</p> : null,
}))

beforeEach(() => vi.clearAllMocks())

function setup({
  query = {},
  mutation = {},
  busy = false,
  visible = [todoFixture],
  message = '',
}: {
  query?: Record<string, unknown>
  mutation?: Record<string, unknown>
  busy?: boolean
  visible?: Todo[]
  message?: string
} = {}) {
  const notify = vi.fn()
  const mutateAsync = vi.fn()
  const refetch = vi.fn().mockResolvedValue(undefined)
  vi.mocked(useTodosQuery).mockReturnValue({
    data: [todoFixture],
    isPending: false,
    isFetching: false,
    isError: false,
    error: null,
    refetch,
    ...query,
  } as unknown as ReturnType<typeof useTodosQuery>)
  vi.mocked(useUpdateTodoMutation).mockReturnValue({
    error: null,
    reset: vi.fn(),
    mutateAsync,
    ...mutation,
  } as unknown as ReturnType<typeof useUpdateTodoMutation>)
  vi.mocked(useTodosBusy).mockReturnValue(busy)
  vi.mocked(useNotice).mockReturnValue({ message, notify })
  vi.mocked(useTodoFilters).mockReturnValue({
    filter: 'active',
    search: 'demo',
    sort: 'due',
    visible,
    setFilter: vi.fn(),
    setSearch: vi.fn(),
    setSort: vi.fn(),
  })
  return { notify, mutateAsync, refetch }
}

it('displays a query failure and resets mutation errors before retrying', async () => {
  const user = userEvent.setup()
  const refetch = vi.fn().mockResolvedValue(undefined)
  const reset = vi.fn()
  vi.mocked(useTodosQuery).mockReturnValue({
    data: [],
    isPending: false,
    isFetching: false,
    isError: true,
    error: new Error('The server is unavailable.'),
    refetch,
  } as unknown as ReturnType<typeof useTodosQuery>)
  vi.mocked(useUpdateTodoMutation).mockReturnValue({
    error: null,
    reset,
    mutateAsync: vi.fn(),
  } as unknown as ReturnType<typeof useUpdateTodoMutation>)
  vi.mocked(useTodosBusy).mockReturnValue(false)
  vi.mocked(useNotice).mockReturnValue({ message: '', notify: vi.fn() })
  vi.mocked(useTodoFilters).mockReturnValue({
    filter: 'all',
    search: '',
    sort: 'newest',
    visible: [],
    setFilter: vi.fn(),
    setSearch: vi.fn(),
    setSort: vi.fn(),
  })
  render(<TodosPage />)
  expect(screen.getByTestId('alert')).toHaveTextContent(
    'The server is unavailable.',
  )
  await user.click(screen.getByRole('button', { name: 'Try again' }))
  await waitFor(() => expect(refetch).toHaveBeenCalledTimes(1))
  expect(reset).toHaveBeenCalledTimes(1)
  expect(reset.mock.invocationCallOrder[0]).toBeLessThan(
    refetch.mock.invocationCallOrder[0],
  )
})

it('passes query and filter state to the header, filters and list', () => {
  setup()
  render(<TodosPage />)
  expect(useTodoFilters).toHaveBeenCalledWith([todoFixture])
  expect(screen.getByText('Filters: active/demo/due')).toBeVisible()
  expect(
    screen.getByText(
      'List: 1 visible, hasTodos=true, loading=false, failed=false, busy=false',
    ),
  ).toBeVisible()
  expect(screen.getByRole('button', { name: 'New task' })).toBeEnabled()
  expect(screen.queryByTestId('alert')).not.toBeInTheDocument()
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
})

it('treats a pending query without data as loading with no tasks', () => {
  setup({ query: { data: undefined, isPending: true }, visible: [] })
  render(<TodosPage />)
  expect(useTodoFilters).toHaveBeenCalledWith([])
  expect(screen.getByRole('button', { name: 'New task' })).toBeDisabled()
  expect(
    screen.getByText(
      'List: 0 visible, hasTodos=false, loading=true, failed=false, busy=false',
    ),
  ).toBeVisible()
})

it('disables creating and retrying while a task change is running', () => {
  setup({ busy: true, query: { error: new Error('Server down.') } })
  render(<TodosPage />)
  expect(screen.getByRole('button', { name: 'New task' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Try again' })).toBeDisabled()
})

it('disables retrying while the list is refetching', () => {
  setup({ query: { error: new Error('Server down.'), isFetching: true } })
  render(<TodosPage />)
  expect(screen.getByRole('button', { name: 'Try again' })).toBeDisabled()
})

it('shows a toggle error in preference to the query error', () => {
  setup({
    query: { error: new Error('Query failed.') },
    mutation: { error: new Error('Toggle failed.') },
  })
  render(<TodosPage />)
  expect(screen.getByTestId('alert')).toHaveTextContent('Toggle failed.')
  expect(screen.getByTestId('alert')).not.toHaveTextContent('Query failed.')
})

it.each([
  [false, true, 'Another task complete. Well done!'],
  [true, false, 'Task marked as active.'],
])(
  'toggles a task with completed=%s and announces the saved state',
  async (completed, savedCompleted, notice) => {
    const user = userEvent.setup()
    const todo = { ...todoFixture, completed }
    const { mutateAsync, notify } = setup({ visible: [todo] })
    mutateAsync.mockResolvedValue({ ...todo, completed: savedCompleted })
    render(<TodosPage />)
    await user.click(
      screen.getByRole('button', { name: `Toggle ${todo.title}` }),
    )
    await waitFor(() => expect(notify).toHaveBeenCalledWith(notice))
    expect(mutateAsync).toHaveBeenCalledWith({
      id: todo.id,
      input: { completed: !completed },
    })
  },
)

it('does not toggle a task while another change is running', async () => {
  const user = userEvent.setup()
  const { mutateAsync, notify } = setup({ busy: true })
  render(<TodosPage />)
  await user.click(
    screen.getByRole('button', { name: `Toggle ${todoFixture.title}` }),
  )
  expect(mutateAsync).not.toHaveBeenCalled()
  expect(notify).not.toHaveBeenCalled()
})

it('does not announce anything when a toggle fails', async () => {
  const user = userEvent.setup()
  const { mutateAsync, notify } = setup()
  mutateAsync.mockRejectedValue(new Error('Toggle failed.'))
  render(<TodosPage />)
  await user.click(
    screen.getByRole('button', { name: `Toggle ${todoFixture.title}` }),
  )
  await waitFor(() => expect(mutateAsync).toHaveBeenCalledTimes(1))
  expect(notify).not.toHaveBeenCalled()
})

it('opens the editor for a new task from the header and from the list', async () => {
  const user = userEvent.setup()
  setup()
  render(<TodosPage />)
  await user.click(screen.getByRole('button', { name: 'New task' }))
  expect(screen.getByRole('dialog', { name: 'Editor: new' })).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Close editor' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Create from list' }))
  expect(screen.getByRole('dialog', { name: 'Editor: new' })).toBeVisible()
})

it('closes the editor and announces the notice after saving an edit', async () => {
  const user = userEvent.setup()
  const { notify } = setup()
  render(<TodosPage />)
  await user.click(
    screen.getByRole('button', { name: `Edit ${todoFixture.title}` }),
  )
  expect(
    screen.getByRole('dialog', { name: `Editor: ${todoFixture.title}` }),
  ).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Save editor' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(notify).toHaveBeenCalledExactlyOnceWith('Changes saved.')
})

it('opens delete confirmation and announces a completed deletion', async () => {
  const user = userEvent.setup()
  const { notify } = setup()
  render(<TodosPage />)
  await user.click(
    screen.getByRole('button', { name: `Delete ${todoFixture.title}` }),
  )
  expect(
    screen.getByRole('dialog', { name: `Delete: ${todoFixture.title}` }),
  ).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Confirm delete' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(notify).toHaveBeenCalledExactlyOnceWith('Task deleted.')
})

it('closes delete confirmation without announcing anything', async () => {
  const user = userEvent.setup()
  const { notify } = setup()
  render(<TodosPage />)
  await user.click(
    screen.getByRole('button', { name: `Delete ${todoFixture.title}` }),
  )
  await user.click(screen.getByRole('button', { name: 'Close delete' }))
  expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  expect(notify).not.toHaveBeenCalled()
})

it('shows the current success notice', () => {
  setup({ message: 'Task deleted.' })
  render(<TodosPage />)
  expect(screen.getByRole('status')).toHaveTextContent('Task deleted.')
})
