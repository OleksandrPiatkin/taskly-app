import { afterEach, expect, it, vi } from 'vitest'
import { request } from './http'

afterEach(() => vi.unstubAllGlobals())

function respond(status: number, body?: unknown) {
  return vi.fn().mockResolvedValue({
    ok: status < 400,
    status,
    json: async () => body,
  })
}

it('prefixes the API path, merges JSON headers and returns the parsed body', async () => {
  const fetchMock = respond(200, [{ id: 1 }])
  vi.stubGlobal('fetch', fetchMock)
  await expect(
    request('/todos', { method: 'POST', headers: { 'X-Trace': 'abc' } }),
  ).resolves.toEqual([{ id: 1 }])
  expect(fetchMock).toHaveBeenCalledWith('/api/todos', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Trace': 'abc' },
  })
})

it('lets caller headers override the default content type', async () => {
  const fetchMock = respond(200, {})
  vi.stubGlobal('fetch', fetchMock)
  await request('/todos', { headers: { 'Content-Type': 'text/plain' } })
  expect(fetchMock).toHaveBeenCalledWith('/api/todos', {
    headers: { 'Content-Type': 'text/plain' },
  })
})

it('returns undefined for 204 responses without reading the body', async () => {
  const json = vi.fn()
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({ ok: true, status: 204, json }),
  )
  await expect(request('/todos/1', { method: 'DELETE' })).resolves.toBeUndefined()
  expect(json).not.toHaveBeenCalled()
})

it('uses the server detail message for failed requests', async () => {
  vi.stubGlobal('fetch', respond(404, { detail: 'Task not found.' }))
  await expect(request('/todos/1')).rejects.toThrow('Task not found.')
})

it('shows a validation message for 422 responses regardless of the body', async () => {
  vi.stubGlobal('fetch', respond(422, { detail: [{ msg: 'too long' }] }))
  await expect(request('/todos')).rejects.toThrow(
    'Check the task details: title up to 120 characters, description up to 2000 characters, and a valid due date.',
  )
})

it.each([
  ['a non-string detail', { detail: [{ msg: 'bad' }] }],
  ['no detail', {}],
  ['an empty body', undefined],
])('falls back to a generic message for %s', async (_, body) => {
  vi.stubGlobal('fetch', respond(500, body))
  await expect(request('/todos')).rejects.toThrow(
    'The operation failed. Please try again.',
  )
})

it('falls back to a generic message when the error body is not JSON', async () => {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: () => Promise.reject(new SyntaxError('Unexpected token')),
    }),
  )
  await expect(request('/todos')).rejects.toThrow(
    'The operation failed. Please try again.',
  )
})

it('reports a connection problem when fetch rejects', async () => {
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
  await expect(request('/todos')).rejects.toThrow(
    'Cannot connect to the server. Please try again.',
  )
})

it('re-throws the original error when the request was aborted', async () => {
  const controller = new AbortController()
  controller.abort()
  const abortError = new DOMException('Aborted', 'AbortError')
  vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abortError))
  await expect(
    request('/todos', { signal: controller.signal }),
  ).rejects.toBe(abortError)
})
