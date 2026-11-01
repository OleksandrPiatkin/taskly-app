import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { todoFixture } from '../../../test/todoFixture'
import { TodoForm } from './TodoForm'

vi.mock('../../../design-system', () => import('../../../design-system/mocks'))

describe('TodoForm', () => {
  it('rejects a whitespace-only title without submitting', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(
      <TodoForm
        onSubmit={onSubmit}
        onCancel={vi.fn()}
        busy={false}
        error={null}
      />,
    )
    await user.type(screen.getByLabelText(/Task title/), '   ')
    await user.click(screen.getByRole('button', { name: 'Save task' }))
    expect(screen.getByText('Enter a task title.')).toBeVisible()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('submits trimmed values and the selected priority', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined)
    const user = userEvent.setup()
    render(
      <TodoForm
        onSubmit={onSubmit}
        onCancel={vi.fn()}
        busy={false}
        error={null}
      />,
    )
    await user.type(screen.getByLabelText(/Task title/), '  Prepare a demo  ')
    await user.selectOptions(screen.getByLabelText('Priority'), 'high')
    await user.click(screen.getByRole('button', { name: 'Save task' }))
    expect(onSubmit).toHaveBeenCalledWith({
      title: 'Prepare a demo',
      description: '',
      priority: 'high',
      due_date: null,
      completed: false,
    })
  })
})

it('prefills an existing task and submits edited description and due date', async () => {
  const onSubmit = vi.fn().mockResolvedValue(undefined)
  const user = userEvent.setup()
  render(
    <TodoForm
      initial={{ ...todoFixture, due_date: '2026-10-20' }}
      onSubmit={onSubmit}
      onCancel={vi.fn()}
      busy={false}
      error={null}
    />,
  )
  expect(screen.getByLabelText(/Task title/)).toHaveValue(todoFixture.title)
  await user.type(screen.getByLabelText('Description (optional)'), '  Bring slides  ')
  await user.clear(screen.getByLabelText('Due date (optional)'))
  await user.type(screen.getByLabelText('Due date (optional)'), '2026-11-03')
  await user.click(screen.getByRole('button', { name: 'Save task' }))
  expect(onSubmit).toHaveBeenCalledWith(
    expect.objectContaining({
      title: todoFixture.title,
      description: 'Bring slides',
      due_date: '2026-11-03',
    }),
  )
})

it('submits no due date after the date is cleared', async () => {
  const onSubmit = vi.fn().mockResolvedValue(undefined)
  const user = userEvent.setup()
  render(
    <TodoForm
      initial={{ ...todoFixture, due_date: '2026-10-20' }}
      onSubmit={onSubmit}
      onCancel={vi.fn()}
      busy={false}
      error={null}
    />,
  )
  await user.clear(screen.getByLabelText('Due date (optional)'))
  await user.click(screen.getByRole('button', { name: 'Save task' }))
  expect(onSubmit).toHaveBeenCalledWith(
    expect.objectContaining({ due_date: null }),
  )
})

it('shows a description length error without submitting', async () => {
  const onSubmit = vi.fn()
  render(
    <TodoForm
      initial={{ ...todoFixture, description: 'a'.repeat(2001) }}
      onSubmit={onSubmit}
      onCancel={vi.fn()}
      busy={false}
      error={null}
    />,
  )
  await userEvent.setup().click(screen.getByRole('button', { name: 'Save task' }))
  expect(
    screen.getByText('The description must be at most 2000 characters.'),
  ).toBeVisible()
  expect(onSubmit).not.toHaveBeenCalled()
})

it('shows the server error and disables the form while saving', () => {
  render(
    <TodoForm onSubmit={vi.fn()} onCancel={vi.fn()} busy error="Server said no." />,
  )
  expect(screen.getByTestId('alert')).toHaveTextContent('Server said no.')
  expect(screen.getByRole('button', { name: 'Saving…' })).toBeDisabled()
  expect(screen.getByRole('button', { name: 'Cancel' })).toBeDisabled()
  expect(screen.getByLabelText(/Task title/)).toBeDisabled()
})

it('cancels without submitting', async () => {
  const onSubmit = vi.fn()
  const onCancel = vi.fn()
  render(
    <TodoForm onSubmit={onSubmit} onCancel={onCancel} busy={false} error={null} />,
  )
  expect(screen.queryByTestId('alert')).not.toBeInTheDocument()
  await userEvent.setup().click(screen.getByRole('button', { name: 'Cancel' }))
  expect(onCancel).toHaveBeenCalledTimes(1)
  expect(onSubmit).not.toHaveBeenCalled()
})
