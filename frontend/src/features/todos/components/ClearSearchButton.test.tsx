import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'
import { ClearSearchButton } from './ClearSearchButton'

vi.mock('../../../design-system', () => import('../../../design-system/mocks'))

it('calls onClear when the search has text', async () => {
  const user = userEvent.setup()
  const onClear = vi.fn()
  render(<ClearSearchButton search="milk" onClear={onClear} />)
  const button = screen.getByRole('button', { name: 'Clear search' })
  expect(button).toBeEnabled()
  await user.click(button)
  expect(onClear).toHaveBeenCalledTimes(1)
})

it.each(['', '   '])('is disabled for blank search %j', async (search) => {
  const user = userEvent.setup()
  const onClear = vi.fn()
  render(<ClearSearchButton search={search} onClear={onClear} />)
  const button = screen.getByRole('button', { name: 'Clear search' })
  expect(button).toBeDisabled()
  await user.click(button)
  expect(onClear).not.toHaveBeenCalled()
})
