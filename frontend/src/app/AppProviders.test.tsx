import { QueryClient, useQueryClient } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { expect, it, vi } from 'vitest'
import { queryClient } from '../lib/queryClient'
import { AppProviders } from './AppProviders'

vi.mock('../design-system', () => import('../design-system/mocks'))

function ClientProbe({ expected }: { expected: QueryClient }) {
  const client = useQueryClient()
  return <p>{client === expected ? 'Expected client' : 'Other client'}</p>
}

it('renders children with the query client passed in', () => {
  const client = new QueryClient()
  render(
    <AppProviders client={client}>
      <ClientProbe expected={client} />
    </AppProviders>,
  )
  expect(screen.getByText('Expected client')).toBeInTheDocument()
})

it('falls back to the application query client by default', () => {
  render(
    <AppProviders>
      <ClientProbe expected={queryClient} />
    </AppProviders>,
  )
  expect(screen.getByText('Expected client')).toBeInTheDocument()
})
