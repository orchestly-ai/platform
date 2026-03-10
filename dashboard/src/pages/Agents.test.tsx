/**
 * Agents Page Tests
 *
 * Tests for the Agents page that displays runtime workers and
 * installed marketplace agents.
 *
 * Test Coverage:
 * - Loading state
 * - Page header and Create Agent button
 * - Runtime workers display
 * - Installed marketplace agents
 * - Empty state rendering
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
vi.mock('@/components/TemplateModal', () => ({
  TemplateModal: ({ isOpen }: { isOpen: boolean }) =>
    isOpen ? <div data-testid="template-modal">TemplateModal</div> : null,
}))

// Default mock data
const mockAgents = [
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
]

const mockInstalledAgents = {
  installed_agents: [
    {
      installation_id: 1,
      agent_id: 101,
      name: 'Data Processor',
      slug: 'data-processor',
      tagline: 'Process and transform data efficiently',
      description: 'A powerful agent for data processing tasks',
      category: 'productivity',
      author: 'AgentCorp',
      version: '1.2.0',
      agent_config: { model: 'gpt-4' },
      status: 'installed',
      installed_at: '2024-01-10T10:00:00Z',
      last_used_at: '2024-01-15T08:00:00Z',
      usage_count: 25,
      config_overrides: {},
    },
  ],
  total: 1,
}

// Mock the API
vi.mock('@/services/api', () => ({
  api: {
    getAgents: vi.fn(),
    getInstalledAgentsWithDetails: vi.fn(),
    uninstallAgent: vi.fn(),
  },
}))

// Import after mocking
import { AgentsPage } from './Agents'
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

describe('AgentsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockedApi.getAgents.mockResolvedValue(mockAgents)
    mockedApi.getInstalledAgentsWithDetails.mockResolvedValue(mockInstalledAgents)
    mockedApi.uninstallAgent.mockResolvedValue(undefined)
  })

  describe('Page Header', () => {
    it('renders page title correctly', async () => {
      renderWithProviders(<AgentsPage />)

      await waitFor(() => {
        expect(screen.getByText('Agents')).toBeInTheDocument()
      })
    })

    it('renders page description', async () => {
      renderWithProviders(<AgentsPage />)

      await waitFor(() => {
        expect(
          screen.getByText('Create, install, and monitor your AI agents')
        ).toBeInTheDocument()
      })
    })

    it('renders Create Agent button', async () => {
      renderWithProviders(<AgentsPage />)

      await waitFor(() => {
        expect(screen.getByText('Create Agent')).toBeInTheDocument()
      })
    })

    it('opens template modal when Create Agent is clicked', async () => {
      renderWithProviders(<AgentsPage />)

      await waitFor(() => {
        expect(screen.getByText('Create Agent')).toBeInTheDocument()
      })

      fireEvent.click(screen.getByText('Create Agent'))

      await waitFor(() => {
        expect(screen.getByTestId('template-modal')).toBeInTheDocument()
      })
    })
  })

  describe('Loading State', () => {
    it('shows loading indicator while fetching data', () => {
      mockedApi.getAgents.mockImplementation(() => new Promise(() => {}))

      renderWithProviders(<AgentsPage />)

      expect(screen.getByText('Loading agents...')).toBeInTheDocument()
    })
  })

  describe('Runtime Workers Section', () => {
    it('renders Runtime Workers header', async () => {
      renderWithProviders(<AgentsPage />)

      await waitFor(() => {
        expect(screen.getByText('Runtime Workers')).toBeInTheDocument()
      })
    })

    it('displays runtime agents from API', async () => {
      renderWithProviders(<AgentsPage />)

      await waitFor(() => {
        expect(screen.getByText('Code Reviewer')).toBeInTheDocument()
        expect(screen.getByText('Document Analyzer')).toBeInTheDocument()
      })
    })
  })

  describe('Installed Marketplace Agents Section', () => {
    it('renders Installed Agents header', async () => {
      renderWithProviders(<AgentsPage />)

      await waitFor(() => {
        expect(screen.getByText('Installed Agents')).toBeInTheDocument()
      })
    })

    it('displays installed marketplace agents', async () => {
      renderWithProviders(<AgentsPage />)

      await waitFor(() => {
        expect(screen.getByText('Data Processor')).toBeInTheDocument()
      })
    })

    it('displays agent version and author', async () => {
      renderWithProviders(<AgentsPage />)

      await waitFor(() => {
        expect(screen.getByText(/v1\.2\.0/)).toBeInTheDocument()
        expect(screen.getByText(/AgentCorp/)).toBeInTheDocument()
      })
    })

    it('displays usage count', async () => {
      renderWithProviders(<AgentsPage />)

      await waitFor(() => {
        expect(screen.getByText(/25 times/)).toBeInTheDocument()
      })
    })

    it('displays Use in Workflow button', async () => {
      renderWithProviders(<AgentsPage />)

      await waitFor(() => {
        expect(screen.getByText('Use in Workflow')).toBeInTheDocument()
      })
    })
  })

  describe('Empty State', () => {
    it('shows empty state when no runtime workers', async () => {
      mockedApi.getAgents.mockResolvedValue([])

      renderWithProviders(<AgentsPage />)

      await waitFor(() => {
        expect(screen.getByText('No agents registered')).toBeInTheDocument()
      })
    })

    it('shows empty state when no installed agents', async () => {
      mockedApi.getInstalledAgentsWithDetails.mockResolvedValue({
        installed_agents: [],
        total: 0,
      })

      renderWithProviders(<AgentsPage />)

      await waitFor(() => {
        expect(screen.getByText('No agents installed')).toBeInTheDocument()
      })
    })

    it('shows Browse Marketplace button in empty installed agents state', async () => {
      mockedApi.getInstalledAgentsWithDetails.mockResolvedValue({
        installed_agents: [],
        total: 0,
      })

      renderWithProviders(<AgentsPage />)

      await waitFor(() => {
        expect(screen.getByText('Browse Marketplace')).toBeInTheDocument()
      })
    })
  })
})
