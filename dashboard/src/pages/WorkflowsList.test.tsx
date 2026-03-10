/**
 * WorkflowsList Page Tests
 *
 * Tests for the Workflows page that displays workflow list,
 * stats, filters, and creation buttons.
 *
 * Test Coverage:
 * - Page header and title (renamed from "Agents & Workflows" to "Workflows")
 * - Loading state
 * - Creation buttons: "Blank Canvas" and "Create Workflow"
 * - Stats section
 * - Status filter
 * - Workflow cards
 * - Empty/error states
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Mock react-router-dom useNavigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// Mock TemplateModal
vi.mock('../components/TemplateModal', () => ({
  TemplateModal: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div data-testid="template-modal">TemplateModal</div> : null,
}))

// Mock workflows data
const mockWorkflows = [
  {
    id: 'wf-1',
    name: 'Data Pipeline',
    status: 'active',
    created_at: '2024-01-10T10:00:00Z',
    updated_at: '2024-01-15T10:00:00Z',
  },
  {
    id: 'wf-2',
    name: 'Review Bot',
    status: 'template',
    created_at: '2024-01-08T10:00:00Z',
    updated_at: '2024-01-12T10:00:00Z',
  },
]

// Mock the API (uses default import)
vi.mock('../services/api', () => ({
  default: {
    getWorkflows: vi.fn(),
  },
}))

// Import after mocking
import { WorkflowsListPage } from './WorkflowsList'
import api from '../services/api'

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

describe('WorkflowsListPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedApi.getWorkflows.mockResolvedValue(mockWorkflows)
  })

  describe('Page Header', () => {
    it('renders title as "Workflows" (not "Agents & Workflows")', async () => {
      renderWithProviders(<WorkflowsListPage />)

      await waitFor(() => {
        expect(screen.getByText('Workflows')).toBeInTheDocument()
      })

      // Ensure old title is NOT present
      expect(screen.queryByText('Agents & Workflows')).not.toBeInTheDocument()
    })

    it('renders page description', async () => {
      renderWithProviders(<WorkflowsListPage />)

      await waitFor(() => {
        expect(
          screen.getByText('Manage and monitor your automation workflows')
        ).toBeInTheDocument()
      })
    })
  })

  describe('Loading State', () => {
    it('shows loading indicator while fetching data', () => {
      mockedApi.getWorkflows.mockImplementation(() => new Promise(() => {}))

      renderWithProviders(<WorkflowsListPage />)

      expect(screen.getByText('Loading workflows...')).toBeInTheDocument()
    })
  })

  describe('Creation Buttons', () => {
    it('renders "Blank Canvas" button (renamed from "Visual Builder")', async () => {
      renderWithProviders(<WorkflowsListPage />)

      await waitFor(() => {
        expect(screen.getByText('Blank Canvas')).toBeInTheDocument()
      })

      // Ensure old name is NOT present
      expect(screen.queryByText('Visual Builder')).not.toBeInTheDocument()
    })

    it('renders "Create Workflow" button', async () => {
      renderWithProviders(<WorkflowsListPage />)

      await waitFor(() => {
        expect(screen.getByText('Create Workflow')).toBeInTheDocument()
      })
    })

    it('does NOT render "Create Agent" button (moved to Agents page)', async () => {
      renderWithProviders(<WorkflowsListPage />)

      await waitFor(() => {
        expect(screen.getByText('Workflows')).toBeInTheDocument()
      })

      expect(screen.queryByText('Create Agent')).not.toBeInTheDocument()
    })

    it('opens template modal when Create Workflow is clicked', async () => {
      renderWithProviders(<WorkflowsListPage />)

      await waitFor(() => {
        expect(screen.getByText('Create Workflow')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Create Workflow'))

      await waitFor(() => {
        expect(screen.getByTestId('template-modal')).toBeInTheDocument()
      })
    })
  })

  describe('Filters', () => {
    it('renders status filter buttons', async () => {
      renderWithProviders(<WorkflowsListPage />)

      await waitFor(() => {
        // Status filter buttons show counts like "all (2)", "active (1)", etc.
        expect(screen.getByText(/all \(\d+\)/i)).toBeInTheDocument()
        expect(screen.getByText(/active \(\d+\)/i)).toBeInTheDocument()
        expect(screen.getByText(/paused \(\d+\)/i)).toBeInTheDocument()
        expect(screen.getByText(/draft \(\d+\)/i)).toBeInTheDocument()
      })
    })

    it('does NOT render type filter (Agent/Workflow) — removed', async () => {
      renderWithProviders(<WorkflowsListPage />)

      await waitFor(() => {
        expect(screen.getByText('Workflows')).toBeInTheDocument()
      })

      // No Agent/Workflow type filter should exist
      expect(screen.queryByText('Agent')).not.toBeInTheDocument()
    })

    it('renders search input', async () => {
      renderWithProviders(<WorkflowsListPage />)

      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search workflows...')).toBeInTheDocument()
      })
    })
  })

  describe('Stats Section', () => {
    it('renders stats cards', async () => {
      renderWithProviders(<WorkflowsListPage />)

      await waitFor(() => {
        expect(screen.getByText('Total Workflows')).toBeInTheDocument()
        expect(screen.getByText('Active')).toBeInTheDocument()
        expect(screen.getByText('Avg Success Rate')).toBeInTheDocument()
        expect(screen.getByText('Total Executions')).toBeInTheDocument()
      })
    })
  })

  describe('Workflow Cards', () => {
    it('displays workflow names from API', async () => {
      renderWithProviders(<WorkflowsListPage />)

      await waitFor(() => {
        expect(screen.getByText('Data Pipeline')).toBeInTheDocument()
        expect(screen.getByText('Review Bot')).toBeInTheDocument()
      })
    })

    it('shows Create New card', async () => {
      renderWithProviders(<WorkflowsListPage />)

      await waitFor(() => {
        expect(screen.getByText('Create New')).toBeInTheDocument()
        expect(screen.getByText('Get Started')).toBeInTheDocument()
      })
    })
  })

  describe('Error State', () => {
    it('shows error message when API fails', async () => {
      mockedApi.getWorkflows.mockRejectedValue(new Error('Network error'))

      renderWithProviders(<WorkflowsListPage />)

      await waitFor(() => {
        expect(screen.getByText('Failed to load workflows')).toBeInTheDocument()
        expect(screen.getByText('Network error')).toBeInTheDocument()
      })
    })
  })
})
