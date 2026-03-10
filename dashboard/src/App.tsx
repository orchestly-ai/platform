import { Routes, Route, Navigate } from 'react-router-dom'
import { DashboardLayout } from './components/DashboardLayout'
import { ProtectedRoute } from './components/ProtectedRoute'
import { LoginPage } from './pages/Login'
import ErrorBoundary from './components/ErrorBoundary'

// Consolidated pages - preferred from public/demo
import { OverviewPage } from './pages/Overview'
import { IntegrationsPage } from './pages/Integrations'
import { MarketplacePage } from './pages/Marketplace'
import { SettingsPage } from './pages/Settings'

// Pages from Orchestly dashboard
import { AgentsPage } from './pages/Agents'
import { TasksPage } from './pages/Tasks'
import { LLMSettingsPage } from './pages/LLMSettings'
import { AlertsPage } from './pages/Alerts'
import { CostManagementPage } from './pages/CostManagement'
import { RunsPage } from './pages/Runs'
import { HITLApprovalsPage } from './pages/HITLApprovals'
import { ABTestingPage } from './pages/ABTesting'
import { AuditLogsPage } from './pages/AuditLogs'
import WorkflowDesigner from './pages/WorkflowDesigner'
import { WorkflowsListPage } from './pages/WorkflowsList'
import { WebhooksPage } from './pages/Webhooks'
import { SchedulesPage } from './pages/Schedules'

// BYOX Pages (Bring Your Own X)
import { MemoryProvidersPage } from './pages/MemoryProviders'
import { RAGConnectorsPage } from './pages/RAGConnectors'
import { BYOCWorkersPage } from './pages/BYOCWorkers'
import { BYOKSettingsPage } from './pages/BYOKSettings'

// Prompt Registry
import { PromptRegistryPage } from './pages/PromptRegistry'

// Enterprise Pages
import { SSOConfigPage } from './pages/SSOConfig'
import { WhiteLabelPage } from './pages/WhiteLabel'
import { MulticloudPage } from './pages/Multicloud'
import { MCPPage } from './pages/MCP'

// Developer Pages
import { DevelopersPage } from './pages/Developers'

// Import consolidated styles
import './styles/pages.css'

function App() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />

      {/* Protected dashboard routes */}
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<OverviewPage />} />
        <Route path="agents" element={<AgentsPage />} />
        <Route path="tasks" element={<TasksPage />} />
        <Route path="runs" element={<RunsPage />} />
        {/* Redirects for backwards compatibility */}
        <Route path="executions" element={<Navigate to="/runs" replace />} />
        <Route path="debugger" element={<Navigate to="/runs" replace />} />
        <Route path="workflows" element={<WorkflowsListPage />} />
        <Route path="workflows/builder" element={<ErrorBoundary fallbackTitle="Workflow Designer Error" fallbackMessage="An error occurred in the workflow designer. Try reloading the page."><WorkflowDesigner /></ErrorBoundary>} />
        <Route path="workflows/gallery" element={<Navigate to="/marketplace?type=workflow_template" replace />} />
        <Route path="costs" element={<CostManagementPage />} />
        <Route path="llm-settings" element={<LLMSettingsPage />} />
        <Route path="approvals" element={<HITLApprovalsPage />} />
        <Route path="ab-testing" element={<ABTestingPage />} />
        <Route path="alerts" element={<AlertsPage />} />
        <Route path="audit" element={<AuditLogsPage />} />
        <Route path="marketplace" element={<MarketplacePage />} />
        <Route path="prompts" element={<PromptRegistryPage />} />
        <Route path="integrations" element={<IntegrationsPage />} />
        <Route path="webhooks" element={<WebhooksPage />} />
        <Route path="schedules" element={<SchedulesPage />} />
        {/* BYOX Routes */}
        <Route path="byok-settings" element={<BYOKSettingsPage />} />
        <Route path="memory-providers" element={<MemoryProvidersPage />} />
        <Route path="rag-connectors" element={<RAGConnectorsPage />} />
        <Route path="byoc-workers" element={<BYOCWorkersPage />} />
        {/* Enterprise Routes */}
        <Route path="sso-config" element={<SSOConfigPage />} />
        <Route path="white-label" element={<WhiteLabelPage />} />
        <Route path="multicloud" element={<MulticloudPage />} />
        <Route path="mcp" element={<MCPPage />} />
        <Route path="developers" element={<DevelopersPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
  )
}

export default App
