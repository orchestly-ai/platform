/**
 * Dashboard Page Tests
 *
 * Tests for the main Dashboard page that displays system metrics,
 * agent status, queue visualization, and cost information.
 *
 * Test Coverage:
 * - Loading state
 * - Error state
 * - Metrics cards rendering
 * - Agent status grid
 * - Queue visualization
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Default mock data
const mockMetrics = {
  timestamp: '2024-01-15T10:00:00Z',
  agents: {
    total: 5,
    active: 3,
    utilization: 0.6,
    details: [
      {
        agent_id: 'agent-1',
        name: 'Code Reviewer',
        status: 'active',
        capabilities: ['code_review', 'analysis'],
        active_tasks: 2,
        tasks_completed: 15,
        tasks_failed: 1,
        cost_today: 0.5,
        last_seen: '2024-01-15T10:00:00Z',
      },
      {
        agent_id: 'agent-2',
        name: 'Document Analyzer',
        status: 'idle',
        capabilities: ['document_analysis'],
        active_tasks: 0,
        tasks_completed: 8,
        tasks_failed: 0,
        cost_today: 0.25,
        last_seen: '2024-01-15T09:55:00Z',
      },
    ],
  },
  tasks: {
    completed: 100,
    failed: 5,
    success_rate: 0.95,
  },
  queues: {
    total_depth: 10,
    by_capability: {
      code_review: 5,
      analysis: 3,
      document_analysis: 2,
    },
    dead_letter_queue: 1,
  },
  costs: {
    today: 2.5,
    month: 45.75,
    by_model: {
      'gpt-4': 30.0,
      'gpt-3.5-turbo': 15.75,
    },
  },
}

const mockAlertStats = {
  active: {
    total: 0,
    critical: 0,
    warning: 0,
    info: 0,
  },
  last_24h: {
    total: 0,
    critical: 0,
    warning: 0,
    info: 0,
  },
}

// Mock the API
vi.mock('@/services/api', () => ({
  api: {
    getSystemMetrics: vi.fn(),
    getAlertStats: vi.fn(),
    getTaskSuccessTimeSeries: vi.fn(),
    getCostTimeSeries: vi.fn(),
  },
}))

// Mock chart components that depend on recharts (not supported in jsdom)
vi.mock('@/components/TaskSuccessChart', () => ({
  TaskSuccessChart: () => <div data-testid="task-success-chart">TaskSuccessChart</div>,
}))
vi.mock('@/components/CostChart', () => ({
  CostChart: () => <div data-testid="cost-chart">CostChart</div>,
}))

// Import after mocking
import { DashboardPage } from './Dashboard'
import { api } from '@/services/api'

const mockedApi = vi.mocked(api)

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

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Re-establish default mock return values
    mockedApi.getSystemMetrics.mockResolvedValue(mockMetrics)
    mockedApi.getAlertStats.mockResolvedValue(mockAlertStats)
    mockedApi.getTaskSuccessTimeSeries.mockResolvedValue([])
    mockedApi.getCostTimeSeries.mockResolvedValue([])
  })

  describe('Page Header', () => {
    it('renders page title correctly', async () => {
      renderWithProviders(<DashboardPage />)

      await waitFor(() => {
        expect(screen.getByText('Dashboard')).toBeInTheDocument()
      })
    })

    it('renders page description', async () => {
      renderWithProviders(<DashboardPage />)

      await waitFor(() => {
        expect(
          screen.getByText('Real-time system overview and monitoring')
        ).toBeInTheDocument()
      })
    })
  })

  describe('Loading State', () => {
    it('shows loading indicator while fetching data', () => {
      mockedApi.getSystemMetrics.mockImplementation(
        () => new Promise(() => {}) // Never resolves
      )

      renderWithProviders(<DashboardPage />)

      expect(screen.getByText('Loading dashboard...')).toBeInTheDocument()
    })
  })

  describe('Metrics Cards', () => {
    it('renders Active Agents card with correct value', async () => {
      renderWithProviders(<DashboardPage />)

      await waitFor(() => {
        expect(screen.getByText('Active Agents')).toBeInTheDocument()
        // '3' appears in multiple places (metric card + queue visualization)
        const threeElements = screen.getAllByText('3')
        expect(threeElements.length).toBeGreaterThanOrEqual(1)
        expect(screen.getByText('5 total')).toBeInTheDocument()
      })
    })

    it('renders Agent Utilization card with correct percentage', async () => {
      renderWithProviders(<DashboardPage />)

      await waitFor(() => {
        expect(screen.getByText('Agent Utilization')).toBeInTheDocument()
        expect(screen.getByText('60.0%')).toBeInTheDocument()
      })
    })

    it('renders Tasks Completed card with success rate', async () => {
      renderWithProviders(<DashboardPage />)

      await waitFor(() => {
        expect(screen.getByText('Tasks Completed')).toBeInTheDocument()
        expect(screen.getByText('100')).toBeInTheDocument()
        expect(screen.getByText('95.0% success rate')).toBeInTheDocument()
      })
    })

    it('renders Cost Today card with monthly total', async () => {
      renderWithProviders(<DashboardPage />)

      await waitFor(() => {
        // "Cost Today" appears in multiple places (card + cost breakdown)
        const costTodayElements = screen.getAllByText('Cost Today')
        expect(costTodayElements.length).toBeGreaterThanOrEqual(1)
        expect(screen.getByText('$2.5000')).toBeInTheDocument()
        expect(screen.getByText('$45.75 this month')).toBeInTheDocument()
      })
    })
  })

  describe('Agent Status Section', () => {
    it('renders Agent Status header', async () => {
      renderWithProviders(<DashboardPage />)

      await waitFor(() => {
        expect(screen.getByText('Agent Status')).toBeInTheDocument()
        expect(
          screen.getByText('Monitor all registered agents')
        ).toBeInTheDocument()
      })
    })
  })

  describe('Error State', () => {
    it('shows error message when metrics fail to load', async () => {
      mockedApi.getSystemMetrics.mockResolvedValue(null)

      renderWithProviders(<DashboardPage />)

      await waitFor(() => {
        expect(screen.getByText('Unable to load metrics')).toBeInTheDocument()
      })
    })
  })
})
