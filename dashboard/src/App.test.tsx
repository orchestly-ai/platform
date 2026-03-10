/**
 * App Routing Tests
 *
 * Tests for application routing including the new unified Runs page
 * and backwards compatibility redirects.
 *
 * Test Coverage:
 * - /runs route renders RunsPage
 * - /executions redirects to /runs
 * - /debugger redirects to /runs
 * - Navigation links work correctly
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// Mock all page components
vi.mock('./pages/Runs', () => ({
  RunsPage: () => <div data-testid="runs-page">Runs Page</div>,
}))

vi.mock('./pages/Overview', () => ({
  OverviewPage: () => <div data-testid="overview-page">Overview Page</div>,
}))

vi.mock('./components/DashboardLayout', () => ({
  DashboardLayout: () => {
    // DashboardLayout uses Outlet, so we need to render it
    const { Outlet } = require('react-router-dom')
    return (
      <div data-testid="dashboard-layout">
        <Outlet />
      </div>
    )
  },
}))

vi.mock('./components/ProtectedRoute', () => ({
  ProtectedRoute: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

// Mock other page imports to avoid errors
vi.mock('./pages/Login', () => ({ LoginPage: () => <div>Login</div> }))
vi.mock('./pages/Integrations', () => ({ IntegrationsPage: () => <div>Integrations</div> }))
vi.mock('./pages/Marketplace', () => ({ MarketplacePage: () => <div>Marketplace</div> }))
vi.mock('./pages/Settings', () => ({ SettingsPage: () => <div>Settings</div> }))
vi.mock('./pages/Agents', () => ({ AgentsPage: () => <div>Agents</div> }))
vi.mock('./pages/Tasks', () => ({ TasksPage: () => <div>Tasks</div> }))
vi.mock('./pages/LLMSettings', () => ({ LLMSettingsPage: () => <div>LLM Settings</div> }))
vi.mock('./pages/Alerts', () => ({ AlertsPage: () => <div>Alerts</div> }))
vi.mock('./pages/CostManagement', () => ({ CostManagementPage: () => <div>Costs</div> }))
vi.mock('./pages/HITLApprovals', () => ({ HITLApprovalsPage: () => <div>Approvals</div> }))
vi.mock('./pages/ABTesting', () => ({ ABTestingPage: () => <div>AB Testing</div> }))
vi.mock('./pages/AuditLogs', () => ({ AuditLogsPage: () => <div>Audit</div> }))
vi.mock('./pages/WorkflowDesigner', () => ({ default: () => <div>Designer</div> }))
vi.mock('./pages/WorkflowGallery', () => ({ default: () => <div>Gallery</div> }))
vi.mock('./pages/WorkflowsList', () => ({ WorkflowsListPage: () => <div>Workflows</div> }))
vi.mock('./pages/Webhooks', () => ({ WebhooksPage: () => <div>Webhooks</div> }))
vi.mock('./pages/Schedules', () => ({ SchedulesPage: () => <div>Schedules</div> }))
vi.mock('./pages/MemoryProviders', () => ({ MemoryProvidersPage: () => <div>Memory</div> }))
vi.mock('./pages/RAGConnectors', () => ({ RAGConnectorsPage: () => <div>RAG</div> }))
vi.mock('./pages/BYOCWorkers', () => ({ BYOCWorkersPage: () => <div>Workers</div> }))
vi.mock('./pages/PromptRegistry', () => ({ PromptRegistryPage: () => <div>Prompts</div> }))
vi.mock('./components/ErrorBoundary', () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

import App from './App'

const createTestQueryClient = () =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false },
    },
  })

const renderWithRouter = (initialRoute: string) => {
  const queryClient = createTestQueryClient()
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialRoute]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

describe('App Routing', () => {
  describe('Runs Page Route', () => {
    it('renders RunsPage at /runs', async () => {
      renderWithRouter('/runs')

      await waitFor(() => {
        expect(screen.getByTestId('runs-page')).toBeInTheDocument()
      })
    })
  })

  describe('Backwards Compatibility Redirects', () => {
    it('redirects /executions to /runs', async () => {
      renderWithRouter('/executions')

      await waitFor(() => {
        expect(screen.getByTestId('runs-page')).toBeInTheDocument()
      })
    })

    it('redirects /debugger to /runs', async () => {
      renderWithRouter('/debugger')

      await waitFor(() => {
        expect(screen.getByTestId('runs-page')).toBeInTheDocument()
      })
    })
  })

  describe('Dashboard Route', () => {
    it('renders OverviewPage at /dashboard', async () => {
      renderWithRouter('/dashboard')

      await waitFor(() => {
        expect(screen.getByTestId('overview-page')).toBeInTheDocument()
      })
    })

    it('redirects / to /dashboard', async () => {
      renderWithRouter('/')

      await waitFor(() => {
        expect(screen.getByTestId('overview-page')).toBeInTheDocument()
      })
    })
  })
})

describe('Navigation Structure', () => {
  it('wraps routes in DashboardLayout', async () => {
    renderWithRouter('/runs')

    await waitFor(() => {
      expect(screen.getByTestId('dashboard-layout')).toBeInTheDocument()
    })
  })
})
