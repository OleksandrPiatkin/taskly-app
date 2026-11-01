import { renderHook } from '@testing-library/react'
import { beforeEach, expect, it, vi } from 'vitest'
import { createQueryWrapper } from '../../../test/queryClientWrapper'
import { todoFixture } from '../../../test/todoFixture'
import { todoKeys } from '../api/queryKeys'
import { todosApi } from '../api/todos'
import { useCreateTodoMutation } from './useCreateTodoMutation'

vi.mock('../api/todos', () => ({
  todosApi: { list: vi.fn(), create: vi.fn(), update: vi.fn(), remove: vi.fn() },
}))
beforeEach(() => vi.clearAllMocks())

const other = { ...todoFixture, id: 1, title: 'Older task' }

it('prepends the created task to the cached list', async () => {
  const { client, wrapper } = createQueryWrapper()
  client.setQueryData(todoKeys.list, [other])
  vi.mocked(todosApi.create).mockResolvedValue(todoFixture)
  const { result } = renderHook(() => useCreateTodoMutation(), { wrapper })
  await result.current.mutateAsync(todoFixture)
  expect(todosApi.create).toHaveBeenCalledWith(todoFixture)
  expect(client.getQueryData(todoKeys.list)).toEqual([todoFixture, other])
})

it('replaces a cached copy of the same task instead of duplicating it', async () => {
  const { client, wrapper } = createQueryWrapper()
  const stale = { ...todoFixture, title: 'Stale title' }
  client.setQueryData(todoKeys.list, [other, stale])
  vi.mocked(todosApi.create).mockResolvedValue(todoFixture)
  const { result } = renderHook(() => useCreateTodoMutation(), { wrapper })
  await result.current.mutateAsync(todoFixture)
  expect(client.getQueryData(todoKeys.list)).toEqual([todoFixture, other])
})

it('starts a list cache when none exists yet', async () => {
  const { client, wrapper } = createQueryWrapper()
  vi.mocked(todosApi.create).mockResolvedValue(todoFixture)
  const { result } = renderHook(() => useCreateTodoMutation(), { wrapper })
  await result.current.mutateAsync(todoFixture)
  expect(client.getQueryData(todoKeys.list)).toEqual([todoFixture])
})

it('leaves the cache untouched when creation fails', async () => {
  const { client, wrapper } = createQueryWrapper()
  client.setQueryData(todoKeys.list, [other])
  vi.mocked(todosApi.create).mockRejectedValue(new Error('Could not save.'))
  const { result } = renderHook(() => useCreateTodoMutation(), { wrapper })
  await expect(result.current.mutateAsync(todoFixture)).rejects.toThrow(
    'Could not save.',
  )
  expect(client.getQueryData(todoKeys.list)).toEqual([other])
})
