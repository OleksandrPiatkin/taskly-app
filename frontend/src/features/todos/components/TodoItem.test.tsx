import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { todoFixture } from '../../../test/todoFixture'
import { TodoItem } from './TodoItem'

vi.mock('../../../design-system', () => import('../../../design-system/mocks'))

it('shows an active task and forwards edit requests', async () => {
  const user = userEvent.setup()
  const onEdit = vi.fn()
  const onToggle = vi.fn()
  const onDelete = vi.fn()
  render(
    <TodoItem
      todo={todoFixture}
      busy={false}
      onEdit={onEdit}
      onToggle={onToggle}
      onDelete={onDelete}
    />,
  )
  expect(screen.getByRole('heading', { name: todoFixture.title })).toBeVisible()
  expect(screen.getByText('To do')).toBeVisible()
  expect(screen.getByText('Medium')).toBeVisible()
  expect(screen.getByRole('checkbox')).not.toBeChecked()
  await user.click(
    screen.getByRole('button', { name: `Edit: ${todoFixture.title}` }),
  )
  expect(onEdit).toHaveBeenCalledTimes(1)
  expect(onToggle).not.toHaveBeenCalled()
  expect(onDelete).not.toHaveBeenCalled()
})

it('shows the description and a completed status', async () => {
  const user = userEvent.setup()
  const onToggle = vi.fn()
  const done = { ...todoFixture, completed: true, description: 'Slides\nand demo', priority: 'high' as const }
  render(
    <TodoItem
      todo={done}
      busy={false}
      onEdit={vi.fn()}
      onToggle={onToggle}
      onDelete={vi.fn()}
    />,
  )
  expect(screen.getByText(/Slides\s+and demo/)).toBeVisible()
  expect(screen.getByText('Completed')).toBeVisible()
  expect(screen.getByText('High')).toBeVisible()
  expect(screen.getByText(`#${todoFixture.id}`)).toBeVisible()
  const checkbox = screen.getByRole('checkbox', {
    name: `Mark as active: ${todoFixture.title}`,
  })
  expect(checkbox).toBeChecked()
  await user.click(checkbox)
  expect(onToggle).toHaveBeenCalledTimes(1)
})

it('forwards delete requests and offers to complete an active task', async () => {
  const user = userEvent.setup()
  const onDelete = vi.fn()
  render(
    <TodoItem
      todo={todoFixture}
      busy={false}
      onEdit={vi.fn()}
      onToggle={vi.fn()}
      onDelete={onDelete}
    />,
  )
  expect(
    screen.getByRole('checkbox', { name: `Complete: ${todoFixture.title}` }),
  ).toBeVisible()
  await user.click(
    screen.getByRole('button', { name: `Delete: ${todoFixture.title}` }),
  )
  expect(onDelete).toHaveBeenCalledTimes(1)
})

it('disables all actions while busy', () => {
  render(
    <TodoItem
      todo={todoFixture}
      busy
      onEdit={vi.fn()}
      onToggle={vi.fn()}
      onDelete={vi.fn()}
    />,
  )
  expect(screen.getByRole('checkbox')).toBeDisabled()
  expect(
    screen.getByRole('button', { name: `Edit: ${todoFixture.title}` }),
  ).toBeDisabled()
  expect(
    screen.getByRole('button', { name: `Delete: ${todoFixture.title}` }),
  ).toBeDisabled()
})

it.each([
  ['marks an overdue active task', { due_date: '2026-10-10' }, '10 Oct 2026 · overdue'],
  ['shows a future due date without warning', { due_date: '2026-10-20' }, '20 Oct 2026'],
  ['does not mark a completed task as overdue', { due_date: '2026-10-10', completed: true }, '10 Oct 2026'],
])('%s', (_, override, label) => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 9, 15, 9, 0, 0))
  try {
    render(
      <TodoItem
        todo={{ ...todoFixture, ...override }}
        busy={false}
        onEdit={vi.fn()}
        onToggle={vi.fn()}
        onDelete={vi.fn()}
      />,
    )
    expect(screen.getByText(label, { exact: true })).toBeVisible()
  } finally {
    vi.useRealTimers()
  }
})
