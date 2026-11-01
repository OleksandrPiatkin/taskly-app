import { afterEach, describe, expect, it, vi } from 'vitest'
import { formatDate, isOverdue, selectTodos, validateTodo } from './todos'
import type { Todo } from '../types'

const base: Todo = {
  id: 1,
  title: 'Sprint plan',
  description: '',
  priority: 'medium',
  completed: false,
  due_date: null,
  created_at: '2026-10-01T12:00:00Z',
  updated_at: '2026-10-01T12:00:00Z',
}

describe('selectTodos', () => {
  it('combines status with a case-insensitive search in the description', () => {
    const matching = { ...base, description: 'Discuss the API' }
    const todos = [
      matching,
      { ...matching, id: 2, completed: true },
      { ...base, id: 3 },
    ]
    expect(selectTodos(todos, 'active', ' api ', 'newest')).toEqual([matching])
  })

  it('sorts by priority without changing the source array', () => {
    const high: Todo = { ...base, id: 2, priority: 'high' }
    const todos = [base, high]
    expect(selectTodos(todos, 'all', '', 'priority')).toEqual([high, base])
    expect(todos).toEqual([base, high])
  })
})

afterEach(() => vi.useRealTimers())

const input = {
  title: 'Sprint plan',
  description: '',
  priority: 'medium' as const,
  due_date: null,
  completed: false,
}

it('accepts a valid task', () => {
  expect(validateTodo({ ...input, due_date: '2026-02-28' })).toEqual({})
})

it.each([
  ['an empty title', { title: '   ' }, { title: 'Enter a task title.' }],
  [
    'a title over 120 characters',
    { title: 'a'.repeat(121) },
    { title: 'The title must be at most 120 characters.' },
  ],
  [
    'a description over 2000 characters',
    { description: 'a'.repeat(2001) },
    { description: 'The description must be at most 2000 characters.' },
  ],
  ['a malformed date', { due_date: '2026-2-1' }, { due_date: 'Enter a valid date.' }],
  ['an unparseable date', { due_date: '2026-13-01' }, { due_date: 'Enter a valid date.' }],
  ['a non-existent day', { due_date: '2026-02-30' }, { due_date: 'Enter a valid date.' }],
])('rejects %s', (_, override, errors) => {
  expect(validateTodo({ ...input, ...override })).toEqual(errors)
})

it('measures title and description length after trimming', () => {
  expect(
    validateTodo({
      ...input,
      title: ` ${'a'.repeat(120)} `,
      description: ` ${'b'.repeat(2000)} `,
    }),
  ).toEqual({})
})

it('shows only completed tasks for the completed filter', () => {
  const done = { ...base, id: 2, completed: true }
  expect(selectTodos([base, done], 'completed', '', 'newest')).toEqual([done])
})

it('sorts by due date with undated tasks last and newer ids first on ties', () => {
  const soon = { ...base, id: 2, due_date: '2026-10-05' }
  const later = { ...base, id: 3, due_date: '2026-11-01' }
  const undated = { ...base, id: 4 }
  expect(
    selectTodos([undated, later, base, soon], 'all', '', 'due'),
  ).toEqual([soon, later, undated, base])
})

it('sorts newest first by creation time, then by id', () => {
  const older = { ...base, id: 5, created_at: '2026-09-01T12:00:00Z' }
  const sameTime = { ...base, id: 2 }
  expect(selectTodos([older, base, sameTime], 'all', '', 'newest')).toEqual([
    sameTime,
    base,
    older,
  ])
})

it('breaks priority ties by newer id first', () => {
  const newer = { ...base, id: 9 }
  const low = { ...base, id: 10, priority: 'low' as const }
  expect(selectTodos([base, low, newer], 'all', '', 'priority')).toEqual([
    newer,
    base,
    low,
  ])
})

it.each([
  ['an active task due before today', { due_date: '2026-10-14' }, true],
  ['an active task due today', { due_date: '2026-10-15' }, false],
  ['a completed task due before today', { due_date: '2026-10-14', completed: true }, false],
  ['a task without a due date', { due_date: null }, false],
])('treats %s as overdue: %s', (_, override, expected) => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 9, 15, 9, 0, 0))
  expect(isOverdue({ ...base, ...override })).toBe(expected)
})

it('formats a due date as day, short month and year', () => {
  expect(formatDate('2026-10-05')).toBe('5 Oct 2026')
})
