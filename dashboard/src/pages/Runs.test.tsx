/**
 * Runs Page Tests
 *
 * Tests for the Runs page with master/detail pattern:
 * - List view: table of all runs with search, filters, sorting
 * - Detail view: click a run to see time-travel debugger
 * - Back button returns to list
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Mock the API
vi.mock('@/services/api', () => ({
  api: {
    getExecutions: vi.fn().mockResolvedValue([
      {
        id: 'exec-1',
        workflowId: 'wf-1',
        workflowName: 'Test Workflow 1',
        status: 'completed',
        startTime: '2024-01-15T10:00:00Z',
        endTime: '2024-01-15T10:01:00Z',
        totalCost: 0.0123,
        nodeExecutions: [
          { id: 0, name: 'Start', timestamp: '2024-01-15T10:00:00Z', duration: '1s', status: 'completed', state: {} },
        ],
      },
      {
        id: 'exec-2',
        workflowId: 'wf-2',
        workflowName: 'Test Workflow 2',
        status: 'failed',
        startTime: '2024-01-15T11:00:00Z',
        endTime: '2024-01-15T11:00:30Z',
        totalCost: 0.005,
        error: 'Something went wrong',
        nodeExecutions: [],
      },
      {
        id: 'exec-3',
        workflowId: 'wf-3',
        workflowName: 'Running Workflow',
        status: 'running',
        startTime: '2024-01-15T12:00:00Z',
        totalCost: 0,
        nodeExecutions: [],
      },
    ]),
    getWorkflowById: vi.fn().mockResolvedValue(null),
  },
}))

// Import after mocking
import { RunsPage } from './Runs'

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
    },
  })

const renderWithProviders = (component: React.ReactNode) => {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>{component}</BrowserRouter>
    </QueryClientProvider>
  )
}

describe('RunsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('List View', () => {
    it('renders page title', async () => {
      renderWithProviders(<RunsPage />)

      await waitFor(() => {
        expect(screen.getByText('Runs')).toBeInTheDocument()
      })
    })

    it('renders inline stats', async () => {
      renderWithProviders(<RunsPage />)

      await waitFor(() => {
        expect(screen.getByText('total')).toBeInTheDocument()
      })
    })

    it('displays total execution count', async () => {
      renderWithProviders(<RunsPage />)

      await waitFor(() => {
        const threeElements = screen.getAllByText('3')
        expect(threeElements.length).toBeGreaterThan(0)
      })
    })

    it('renders execution table with workflow names', async () => {
      renderWithProviders(<RunsPage />)

      await waitFor(() => {
        expect(screen.getByText('Workflow')).toBeInTheDocument()
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument()
        expect(screen.getByText('Test Workflow 2')).toBeInTheDocument()
        expect(screen.getByText('Running Workflow')).toBeInTheDocument()
      })
    })

    it('rows are clickable', async () => {
      renderWithProviders(<RunsPage />)

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument()
      })

      // Click a row — should navigate to detail view
      fireEvent.click(screen.getByText('Test Workflow 1'))

      await waitFor(() => {
        expect(screen.getByText('All Runs')).toBeInTheDocument()
      })
    })
  })

  describe('Status Filtering', () => {
    it('renders all filter buttons', async () => {
      renderWithProviders(<RunsPage />)

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /all/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /completed/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /failed/i })).toBeInTheDocument()
        expect(screen.getByRole('button', { name: /running/i })).toBeInTheDocument()
      })
    })

    it('filters executions by completed status', async () => {
      renderWithProviders(<RunsPage />)

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /^completed$/i }))

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument()
        expect(screen.queryByText('Test Workflow 2')).not.toBeInTheDocument()
        expect(screen.queryByText('Running Workflow')).not.toBeInTheDocument()
      })
    })

    it('filters executions by failed status', async () => {
      renderWithProviders(<RunsPage />)

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByRole('button', { name: /^failed$/i }))

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 2')).toBeInTheDocument()
        expect(screen.queryByText('Test Workflow 1')).not.toBeInTheDocument()
      })
    })
  })

  describe('Search Functionality', () => {
    it('renders search input', async () => {
      renderWithProviders(<RunsPage />)

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/search/i)).toBeInTheDocument()
      })
    })

    it('filters executions by search query', async () => {
      renderWithProviders(<RunsPage />)

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument()
      })

      const searchInput = screen.getByPlaceholderText(/search/i)
      fireEvent.change(searchInput, { target: { value: 'Running' } })

      await waitFor(() => {
        expect(screen.getByText('Running Workflow')).toBeInTheDocument()
        expect(screen.queryByText('Test Workflow 1')).not.toBeInTheDocument()
        expect(screen.queryByText('Test Workflow 2')).not.toBeInTheDocument()
      })
    })
  })

  describe('Detail View', () => {
    it('shows detail view when clicking a run with steps', async () => {
      renderWithProviders(<RunsPage />)

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Test Workflow 1'))

      await waitFor(() => {
        // Should show back button and workflow name in header
        expect(screen.getByText('All Runs')).toBeInTheDocument()
        expect(screen.getByText('Time-Travel')).toBeInTheDocument()
      })
    })

    it('back button returns to list view', async () => {
      renderWithProviders(<RunsPage />)

      await waitFor(() => {
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument()
      })

      // Navigate to detail
      fireEvent.click(screen.getByText('Test Workflow 1'))

      await waitFor(() => {
        expect(screen.getByText('All Runs')).toBeInTheDocument()
      })

      // Click back
      fireEvent.click(screen.getByText('All Runs'))

      await waitFor(() => {
        // Should be back in list view
        expect(screen.getByText('Test Workflow 1')).toBeInTheDocument()
        expect(screen.getByText('Test Workflow 2')).toBeInTheDocument()
        expect(screen.getByText('Running Workflow')).toBeInTheDocument()
      })
    })
  })
})
