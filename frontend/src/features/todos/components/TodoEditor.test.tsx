import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import { todoFixture } from '../../../test/todoFixture'
import { useCreateTodoMutation } from '../hooks/useCreateTodoMutation'
import { useUpdateTodoMutation } from '../hooks/useUpdateTodoMutation'
import type { TodoInput } from '../types'
import { TodoEditor } from './TodoEditor'

vi.mock('../../../design-system', () => import('../../../design-system/mocks'))
vi.mock('../hooks/useCreateTodoMutation', () => ({
  useCreateTodoMutation: vi.fn(),
}))
vi.mock('../hooks/useUpdateTodoMutation', () => ({
  useUpdateTodoMutation: vi.fn(),
}))
vi.mock('./TodoForm', () => ({
  TodoForm: ({
    initial,
    busy,
    error,
    onSubmit,
    onCancel,
  }: {
    initial?: TodoInput
    busy: boolean
    error: string | null
    onSubmit: (input: TodoInput) => Promise<void>
    onCancel: () => void
  }) => (
    <div>
      <p>{initial ? `Editing ${initial.title}` : 'Empty form'}</p>
      <p>{busy ? 'Form busy' : 'Form idle'}</p>
      {error && <p>{`Form error: ${error}`}</p>}
      <button onClick={() => void onSubmit(todoFixture)}>Submit form</button>
      <button onClick={onCancel}>Cancel form</button>
    </div>
  ),
}))
beforeEach(() => vi.clearAllMocks())

function mockMutations(
  create: { isPending?: boolean; error?: Error | null; mutateAsync?: ReturnType<typeof vi.fn> },
  update: { isPending?: boolean; error?: Error | null; mutateAsync?: ReturnType<typeof vi.fn> },
) {
  const createMock = create.mutateAsync ?? vi.fn()
  const updateMock = update.mutateAsync ?? vi.fn()
  vi.mocked(useCreateTodoMutation).mockReturnValue({
    isPending: false,
    error: null,
    ...create,
    mutateAsync: createMock,
  } as unknown as ReturnType<typeof useCreateTodoMutation>)
  vi.mocked(useUpdateTodoMutation).mockReturnValue({
    isPending: false,
    error: null,
    ...update,
    mutateAsync: updateMock,
  } as unknown as ReturnType<typeof useUpdateTodoMutation>)
  return { create: createMock, update: updateMock }
}

it('creates a new task and reports a successful save', async () => {
  const user = userEvent.setup()
  const create = vi.fn().mockResolvedValue(todoFixture)
  const update = vi.fn()
  vi.mocked(useCreateTodoMutation).mockReturnValue({
    isPending: false,
    error: null,
    mutateAsync: create,
  } as unknown as ReturnType<typeof useCreateTodoMutation>)
  vi.mocked(useUpdateTodoMutation).mockReturnValue({
    isPending: false,
    error: null,
    mutateAsync: update,
  } as unknown as ReturnType<typeof useUpdateTodoMutation>)
  const onSaved = vi.fn()
  render(
    <TodoEditor todo="new" busy={false} onClose={vi.fn()} onSaved={onSaved} />,
  )
  expect(screen.getByRole('dialog', { name: 'New task' })).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Submit form' }))
  await waitFor(() => expect(onSaved).toHaveBeenCalledWith('New task added.'))
  expect(create).toHaveBeenCalledWith(todoFixture)
  expect(update).not.toHaveBeenCalled()
})

it('updates an existing task and reports saved changes', async () => {
  const user = userEvent.setup()
  const { create, update } = mockMutations(
    { error: new Error('Old create error') },
    { mutateAsync: vi.fn().mockResolvedValue(todoFixture) },
  )
  const onSaved = vi.fn()
  render(
    <TodoEditor todo={todoFixture} busy={false} onClose={vi.fn()} onSaved={onSaved} />,
  )
  expect(screen.getByRole('dialog', { name: 'Edit task' })).toBeVisible()
  expect(screen.getByText(`Editing ${todoFixture.title}`)).toBeVisible()
  expect(screen.queryByText(/Form error/)).not.toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Submit form' }))
  await waitFor(() => expect(onSaved).toHaveBeenCalledWith('Changes saved.'))
  expect(update).toHaveBeenCalledWith({ id: todoFixture.id, input: todoFixture })
  expect(create).not.toHaveBeenCalled()
})

it('keeps the editor open and shows the server error when saving fails', async () => {
  const user = userEvent.setup()
  const { create } = mockMutations(
    {
      error: new Error('Title already taken.'),
      mutateAsync: vi.fn().mockRejectedValue(new Error('Title already taken.')),
    },
    {},
  )
  const onSaved = vi.fn()
  render(<TodoEditor todo="new" busy={false} onClose={vi.fn()} onSaved={onSaved} />)
  expect(screen.getByText('Empty form')).toBeVisible()
  expect(screen.getByText('Form error: Title already taken.')).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Submit form' }))
  await waitFor(() => expect(create).toHaveBeenCalledTimes(1))
  expect(onSaved).not.toHaveBeenCalled()
})

it.each([
  ['the save is pending', { isPending: true }, false],
  ['another task change is running', {}, true],
])('ignores submissions while %s', async (_, create, busy) => {
  const user = userEvent.setup()
  const mocks = mockMutations(create, {})
  const onSaved = vi.fn()
  render(<TodoEditor todo="new" busy={busy} onClose={vi.fn()} onSaved={onSaved} />)
  expect(screen.getByText('Form busy')).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Submit form' }))
  expect(mocks.create).not.toHaveBeenCalled()
  expect(onSaved).not.toHaveBeenCalled()
})

it('closes from the form cancel action', async () => {
  const user = userEvent.setup()
  mockMutations({}, {})
  const onClose = vi.fn()
  render(<TodoEditor todo="new" busy={false} onClose={onClose} onSaved={vi.fn()} />)
  expect(screen.getByText('Form idle')).toBeVisible()
  await user.click(screen.getByRole('button', { name: 'Cancel form' }))
  expect(onClose).toHaveBeenCalledTimes(1)
})
