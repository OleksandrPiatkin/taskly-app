import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { createQueryWrapper } from '../../../test/queryClientWrapper'
import { todoFixture } from '../../../test/todoFixture'
import { todoKeys } from '../api/queryKeys'
import { todosApi } from '../api/todos'
import { useTodosQuery } from './useTodosQuery'

vi.mock('../api/todos', () => ({
  todosApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() },
}))
beforeEach(() => vi.clearAllMocks())

it('loads tasks into the list cache and passes the abort signal', async () => {
  const { client, wrapper } = createQueryWrapper()
  vi.mocked(todosApi.list).mockResolvedValue([todoFixture])
  const { result } = renderHook(() => useTodosQuery(), { wrapper })
  await waitFor(() => expect(result.current.isSuccess).toBe(true))
  expect(result.current.data).toEqual([todoFixture])
  expect(client.getQueryData(todoKeys.list)).toEqual([todoFixture])
  expect(todosApi.list).toHaveBeenCalledTimes(1)
  expect(vi.mocked(todosApi.list).mock.calls[0][0]).toBeInstanceOf(AbortSignal)
})

it('exposes the request error when loading fails', async () => {
  const { wrapper } = createQueryWrapper()
  vi.mocked(todosApi.list).mockRejectedValue(new Error('Server down.'))
  const { result } = renderHook(() => useTodosQuery(), { wrapper })
  await waitFor(() => expect(result.current.isError).toBe(true))
  expect(result.current.error?.message).toBe('Server down.')
})
