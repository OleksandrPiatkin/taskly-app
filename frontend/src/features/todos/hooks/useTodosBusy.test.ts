import { useMutation } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { expect, it } from 'vitest'
import { createQueryWrapper } from '../../../test/queryClientWrapper'
import { todoKeys } from '../api/queryKeys'
import { useTodosBusy } from './useTodosBusy'

function useBusyWithMutation(mutationKey: readonly string[]) {
  const mutation = useMutation({
    mutationKey,
    mutationFn: () => new Promise<void>(() => {}),
  })
  return { busy: useTodosBusy(), mutation }
}

it('is not busy when no task mutation is running', () => {
  const { wrapper } = createQueryWrapper()
  const { result } = renderHook(() => useTodosBusy(), { wrapper })
  expect(result.current).toBe(false)
})

it('is busy while a task mutation is running', async () => {
  const { wrapper } = createQueryWrapper()
  const { result } = renderHook(() => useBusyWithMutation(todoKeys.update), {
    wrapper,
  })
  act(() => result.current.mutation.mutate())
  await waitFor(() => expect(result.current.busy).toBe(true))
})

it('ignores mutations outside the task key space', async () => {
  const { wrapper } = createQueryWrapper()
  const { result } = renderHook(() => useBusyWithMutation(['settings']), {
    wrapper,
  })
  act(() => result.current.mutation.mutate())
  await waitFor(() => expect(result.current.mutation.isPending).toBe(true))
  expect(result.current.busy).toBe(false)
})
