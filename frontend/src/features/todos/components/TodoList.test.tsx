import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { todoFixture } from '../../../test/todoFixture'
import type { Todo } from '../types'
import { TodoList } from './TodoList'

vi.mock('../../../design-system', () => import('../../../design-system/mocks'))
vi.mock('./TodoEmptyState', () => ({
  TodoEmptyState: ({
    hasTodos,
    disabled,
    onCreate,
  }: {
    hasTodos: boolean
    disabled: boolean
    onCreate: () => void
  }) => (
    <div>
      <p>Empty task list</p>
      <button disabled={disabled} onClick={onCreate}>
        {hasTodos ? 'Empty: has tasks' : 'Empty: no tasks'}
      </button>
    </div>
  ),
}))
vi.mock('./TodoItem', () => ({
  TodoItem: ({
    todo,
    busy,
    onToggle,
    onEdit,
    onDelete,
  }: {
    todo: Todo
    busy: boolean
    onToggle: () => void
    onEdit: () => void
    onDelete: () => void
  }) => (
    <li>
      {todo.title}
      <button disabled={busy} onClick={onToggle}>{`Toggle ${todo.id}`}</button>
      <button onClick={onEdit}>{`Edit ${todo.id}`}</button>
      <button onClick={onDelete}>{`Delete ${todo.id}`}</button>
    </li>
  ),
}))

function makeProps() {
  return {
    todos: [] as Todo[],
    hasTodos: false,
    loading: false,
    failed: false,
    busy: false,
    onCreate: vi.fn(),
    onToggle: vi.fn(),
    onEdit: vi.fn(),
    onDelete: vi.fn(),
  }
}

it('shows loading feedback before showing an empty list', () => {
  const props = {
    todos: [],
    hasTodos: false,
    failed: false,
    busy: false,
    onCreate: vi.fn(),
    onToggle: vi.fn(),
    onEdit: vi.fn(),
    onDelete: vi.fn(),
  }
  const { rerender } = render(<TodoList {...props} loading />)
  expect(screen.getByRole('status')).toHaveTextContent('Loading your tasks…')
  expect(screen.queryByText('Empty task list')).not.toBeInTheDocument()
  rerender(<TodoList {...props} loading={false} />)
  expect(screen.queryByRole('status')).not.toBeInTheDocument()
  expect(screen.getByText('Empty task list')).toBeVisible()
})

it('explains that the list is unavailable when loading failed with no tasks', () => {
  render(<TodoList {...makeProps()} failed />)
  expect(
    screen.getByRole('heading', {
      name: 'The task list is temporarily unavailable',
    }),
  ).toBeVisible()
  expect(screen.getByText('Try again to load your tasks.')).toBeVisible()
  expect(screen.queryByText('Empty task list')).not.toBeInTheDocument()
})

it('keeps showing cached tasks when a refetch failed', () => {
  render(
    <TodoList {...makeProps()} todos={[todoFixture]} hasTodos failed />,
  )
  expect(screen.getByRole('listitem')).toHaveTextContent(todoFixture.title)
  expect(
    screen.queryByText('The task list is temporarily unavailable'),
  ).not.toBeInTheDocument()
})

it('renders each task and forwards its actions with the task', async () => {
  const user = userEvent.setup()
  const second = { ...todoFixture, id: 8, title: 'Review notes' }
  const props = makeProps()
  render(<TodoList {...props} todos={[todoFixture, second]} hasTodos />)
  expect(screen.getAllByRole('listitem')).toHaveLength(2)
  await user.click(screen.getByRole('button', { name: 'Toggle 8' }))
  await user.click(screen.getByRole('button', { name: 'Edit 7' }))
  await user.click(screen.getByRole('button', { name: 'Delete 8' }))
  expect(props.onToggle).toHaveBeenCalledExactlyOnceWith(second)
  expect(props.onEdit).toHaveBeenCalledExactlyOnceWith(todoFixture)
  expect(props.onDelete).toHaveBeenCalledExactlyOnceWith(second)
})

it('passes the busy state to each task', () => {
  render(<TodoList {...makeProps()} todos={[todoFixture]} hasTodos busy />)
  expect(screen.getByRole('button', { name: 'Toggle 7' })).toBeDisabled()
})

it('passes filter state, busy state and the create action to the empty state', async () => {
  const user = userEvent.setup()
  const props = makeProps()
  const { rerender } = render(<TodoList {...props} hasTodos />)
  expect(screen.getByRole('button', { name: 'Empty: has tasks' })).toBeEnabled()
  rerender(<TodoList {...props} busy />)
  expect(screen.getByRole('button', { name: 'Empty: no tasks' })).toBeDisabled()
  rerender(<TodoList {...props} />)
  await user.click(screen.getByRole('button', { name: 'Empty: no tasks' }))
  expect(props.onCreate).toHaveBeenCalledTimes(1)
})
