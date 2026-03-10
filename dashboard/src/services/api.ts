/**
 * API Client for Orchestly Dashboard
 *
 * Connects to the real FastAPI backend with graceful fallback to mock data.
 * Backend runs at http://localhost:8000 by default.
 */

import type {
  SystemMetrics,
  Alert,
  AlertStats,
  AgentDetail,
  Task,
  TaskStatus,
  TaskPriority,
  TaskSubmission,
  TaskResponse,
  TaskFilters
} from '@/types'
import type {
  LLMProvider,
  RoutingStrategy,
  RoutingAnalytics,
  CostSummary,
  BudgetAlert,
  CostForecast,
  TimeTravelExecution,
  ExecutionStep,
  HITLApproval,
  ABExperiment,
  AuditLogEntry
} from '@/types/llm'
import type {
  PromptTemplate,
  PromptVersion,
  PromptUsageStats,
  CreateTemplateRequest,
  CreateVersionRequest,
  UpdateTemplateRequest,
  RenderPromptRequest,
  RenderPromptResponse
} from '@/types/prompt'

// API configuration
const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// API Key configuration - use environment variable, fallback to debug only in development
const API_KEY = import.meta.env.VITE_API_KEY || (import.meta.env.DEV ? 'debug' : '')

// Debug logging
const DEBUG = import.meta.env.DEV

function log(message: string, ...args: unknown[]) {
  if (DEBUG) {
    console.log(`[API] ${message}`, ...args)
  }
}

// Custom error class for better error handling
export class APIError extends Error {
  constructor(
    message: string,
    public status: number,
    public code?: string,
    public details?: unknown
  ) {
    super(message)
    this.name = 'APIError'
  }

  isAuthError(): boolean {
    return this.status === 401 || this.status === 403
  }

  isNotFound(): boolean {
    return this.status === 404
  }

  isServerError(): boolean {
    return this.status >= 500
  }

  isNetworkError(): boolean {
    return this.status === 0
  }
}

// Retry configuration
const RETRY_CONFIG = {
  maxRetries: 3,
  baseDelayMs: 1000,
  maxDelayMs: 10000,
}

// Sleep utility for retry delays
const sleep = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

// HTTP client helper with retry logic
async function fetchAPI<T>(
  endpoint: string,
  options: RequestInit = {},
  retries = 0
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`

  // Build headers
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers as Record<string, string>,
  }

  // Always include auth token when available
  const token = getAuthToken()
  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // Add API key as fallback if no token
  if (!token && API_KEY) {
    headers['X-API-Key'] = API_KEY
  }

  log(`Fetching${token ? ' (auth)' : ''}: ${url}`)

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    })

    if (!response.ok) {
      const errorText = await response.text()
      let errorDetails: unknown = errorText

      // Try to parse as JSON for structured errors
      try {
        errorDetails = JSON.parse(errorText)
      } catch {
        // Keep as text if not JSON
      }

      const error = new APIError(
        `API Error ${response.status}: ${typeof errorDetails === 'object' ? JSON.stringify(errorDetails) : errorText}`,
        response.status,
        typeof errorDetails === 'object' && errorDetails !== null && 'code' in errorDetails
          ? String((errorDetails as { code: unknown }).code)
          : undefined,
        errorDetails
      )

      // Retry on server errors or network issues
      if (error.isServerError() && retries < RETRY_CONFIG.maxRetries) {
        const delay = Math.min(
          RETRY_CONFIG.baseDelayMs * Math.pow(2, retries),
          RETRY_CONFIG.maxDelayMs
        )
        log(`Retrying request after ${delay}ms (attempt ${retries + 1}/${RETRY_CONFIG.maxRetries})`)
        await sleep(delay)
        return fetchAPI(endpoint, options, retries + 1)
      }

      throw error
    }

    // Handle 204 No Content responses (DELETE operations)
    if (response.status === 204) {
      return undefined as T
    }

    return response.json()
  } catch (error) {
    // Handle network errors
    if (error instanceof TypeError && error.message.includes('fetch')) {
      const networkError = new APIError(
        'Network error: Unable to connect to the server',
        0,
        'NETWORK_ERROR'
      )

      // Retry network errors
      if (retries < RETRY_CONFIG.maxRetries) {
        const delay = Math.min(
          RETRY_CONFIG.baseDelayMs * Math.pow(2, retries),
          RETRY_CONFIG.maxDelayMs
        )
        log(`Retrying after network error (attempt ${retries + 1}/${RETRY_CONFIG.maxRetries})`)
        await sleep(delay)
        return fetchAPI(endpoint, options, retries + 1)
      }

      throw networkError
    }

    throw error
  }
}

// ============================================================================
// Auth Token Management
// ============================================================================

let authToken: string | null = null

export function setAuthToken(token: string | null) {
  authToken = token
  if (token) {
    localStorage.setItem('auth_token', token)
  } else {
    localStorage.removeItem('auth_token')
  }
}

export function getAuthToken(): string | null {
  if (!authToken) {
    authToken = localStorage.getItem('auth_token')
  }
  return authToken
}

// Authenticated fetch helper with retry logic
async function fetchAuthAPI<T>(
  endpoint: string,
  options: RequestInit = {},
  retries = 0
): Promise<T> {
  const token = getAuthToken()
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...options.headers as Record<string, string>,
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  // Add API key as fallback if no token
  if (!token && API_KEY) {
    headers['X-API-Key'] = API_KEY
  }

  const url = `${API_BASE_URL}${endpoint}`
  log(`Fetching (auth): ${url}`)

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    })

    if (!response.ok) {
      if (response.status === 401) {
        // Clear invalid token
        setAuthToken(null)
      }

      const errorText = await response.text()
      let errorDetails: unknown = errorText

      try {
        errorDetails = JSON.parse(errorText)
      } catch {
        // Keep as text
      }

      const error = new APIError(
        `API Error ${response.status}: ${typeof errorDetails === 'object' ? JSON.stringify(errorDetails) : errorText}`,
        response.status,
        typeof errorDetails === 'object' && errorDetails !== null && 'code' in errorDetails
          ? String((errorDetails as { code: unknown }).code)
          : undefined,
        errorDetails
      )

      // Retry on server errors (but not auth errors)
      if (error.isServerError() && retries < RETRY_CONFIG.maxRetries) {
        const delay = Math.min(
          RETRY_CONFIG.baseDelayMs * Math.pow(2, retries),
          RETRY_CONFIG.maxDelayMs
        )
        log(`Retrying auth request after ${delay}ms (attempt ${retries + 1}/${RETRY_CONFIG.maxRetries})`)
        await sleep(delay)
        return fetchAuthAPI(endpoint, options, retries + 1)
      }

      throw error
    }

    // Handle 204 No Content responses
    if (response.status === 204) {
      return undefined as T
    }

    return response.json()
  } catch (error) {
    // Handle network errors
    if (error instanceof TypeError && error.message.includes('fetch')) {
      const networkError = new APIError(
        'Network error: Unable to connect to the server',
        0,
        'NETWORK_ERROR'
      )

      if (retries < RETRY_CONFIG.maxRetries) {
        const delay = Math.min(
          RETRY_CONFIG.baseDelayMs * Math.pow(2, retries),
          RETRY_CONFIG.maxDelayMs
        )
        log(`Retrying auth request after network error (attempt ${retries + 1}/${RETRY_CONFIG.maxRetries})`)
        await sleep(delay)
        return fetchAuthAPI(endpoint, options, retries + 1)
      }

      throw networkError
    }

    throw error
  }
}

// ============================================================================
// Auth Types
// ============================================================================

export interface User {
  id: string
  email: string
  name: string
  role: string
  organization_id: string
  preferences?: Record<string, unknown>
}

export interface LoginResponse {
  access_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface RegisterResponse {
  user: User
  access_token: string
  token_type: string
}

// ============================================================================
// API Client
// ============================================================================

export const api = {
  // -------------------------------------------------------------------------
  // Generic HTTP Methods (for flexibility)
  // -------------------------------------------------------------------------
  async get<T = unknown>(endpoint: string): Promise<{ data: T }> {
    const data = await fetchAPI<T>(endpoint)
    return { data }
  },

  async post<T = unknown>(endpoint: string, body?: unknown): Promise<{ data: T }> {
    const data = await fetchAPI<T>(endpoint, {
      method: 'POST',
      body: body ? JSON.stringify(body) : undefined,
    })
    return { data }
  },

  async delete<T = unknown>(endpoint: string): Promise<{ data: T }> {
    const data = await fetchAPI<T>(endpoint, {
      method: 'DELETE',
    })
    return { data }
  },

  // -------------------------------------------------------------------------
  // Authentication
  // -------------------------------------------------------------------------
  async login(email: string, password: string): Promise<LoginResponse> {
    const response = await fetchAPI<LoginResponse>('/api/v1/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    })

    // Store token
    setAuthToken(response.access_token)

    return response
  },

  async register(email: string, password: string, name: string): Promise<RegisterResponse> {
    const response = await fetchAPI<RegisterResponse>('/api/v1/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, name }),
    })

    // Store token
    setAuthToken(response.access_token)

    return response
  },

  async getCurrentUser(): Promise<User> {
    return fetchAuthAPI<User>('/api/v1/auth/me')
  },

  async updateCurrentUser(data: { name?: string; preferences?: Record<string, unknown> }): Promise<User> {
    return fetchAuthAPI<User>('/api/v1/auth/me', {
      method: 'PUT',
      body: JSON.stringify(data),
    })
  },

  async logout(): Promise<void> {
    try {
      await fetchAuthAPI('/api/v1/auth/logout', { method: 'POST' })
    } finally {
      setAuthToken(null)
    }
  },

  async refreshToken(): Promise<{ access_token: string }> {
    const response = await fetchAuthAPI<{ access_token: string }>('/api/v1/auth/refresh', {
      method: 'POST',
    })
    setAuthToken(response.access_token)
    return response
  },

  // -------------------------------------------------------------------------
  // System Metrics
  // -------------------------------------------------------------------------
  async getSystemMetrics(): Promise<SystemMetrics> {
    try {
      const data = await fetchAPI<{
        timestamp: string
        agents: { total: number; active: number }
        queues: { total_depth: number; capabilities: string[] }
      }>('/api/v1/metrics/system')

      // Get agent list for details
      const agentList = await fetchAPI<{ agents: Array<{
        agent_id: string
        name: string
        status: string
        capabilities: string[]
      }> }>('/api/v1/agents')

      return {
        timestamp: data.timestamp || new Date().toISOString(),
        agents: {
          total: data.agents?.total || 0,
          active: data.agents?.active || 0,
          utilization: data.agents?.total > 0 ? data.agents.active / data.agents.total : 0,
          details: agentList.agents.map(a => ({
            agent_id: a.agent_id,
            name: a.name,
            status: 'active' as const,
            capabilities: a.capabilities || [],
            active_tasks: 0,
            tasks_completed: 0,
            tasks_failed: 0,
            cost_today: 0,
            last_seen: new Date().toISOString(),
          })),
        },
        tasks: {
          completed: 0,
          failed: 0,
          success_rate: 1,
        },
        queues: {
          total_depth: data.queues?.total_depth || 0,
          by_capability: {},
          dead_letter_queue: 0,
        },
        costs: {
          today: 0,
          month: 0,
          by_model: {},
        },
      }
    } catch (error) {
      log('Error fetching system metrics:', error)
      throw new Error(`Failed to fetch system metrics: ${error}`)
    }
  },

  // -------------------------------------------------------------------------
  // Alerts
  // -------------------------------------------------------------------------
  async getAlerts(): Promise<Alert[]> {
    try {
      const data = await fetchAPI<{ alerts: Array<{ alert_id: string; severity: string; message: string; source: string; created_at: string; acknowledged?: boolean }> }>('/api/v1/alerts')
      return data.alerts.map(a => ({
        alert_id: a.alert_id || String(Math.random()),
        severity: a.severity as 'critical' | 'warning' | 'info',
        message: a.message,
        source: a.source,
        created_at: a.created_at,
        acknowledged: a.acknowledged || false,
      }))
    } catch (error) {
      log('Error fetching alerts:', error)
      throw new Error(`Failed to fetch alerts: ${error}`)
    }
  },

  async getAlertStats(): Promise<AlertStats> {
    try {
      return await fetchAPI<AlertStats>('/api/v1/alerts/stats')
    } catch (error) {
      log('Error fetching alert stats:', error)
      throw new Error(`Failed to fetch alert stats: ${error}`)
    }
  },

  // -------------------------------------------------------------------------
  // LLM Provider Management
  // -------------------------------------------------------------------------
  async getLLMProviders(): Promise<LLMProvider[]> {
    try {
      const providers = await fetchAPI<Array<{
        id?: number
        provider: string
        name: string
        is_active: boolean
        models?: string[]
        avg_latency_ms?: number
        success_rate?: number
      }>>('/api/v1/llm/providers')

      return providers.map(p => ({
        id: p.provider,
        name: p.name || p.provider,
        models: Array.isArray(p.models) ? p.models : [],
        status: p.is_active ? 'healthy' : 'offline',
        circuitBreakerState: 'CLOSED',
        successRate: p.success_rate || 1,
        avgLatencyMs: p.avg_latency_ms || 0,
        failureCount: 0,
        lastFailure: null,
        costPer1kTokens: 0,
      }))
    } catch (error) {
      log('Error fetching LLM providers:', error)
      throw new Error(`Failed to fetch LLM providers: ${error}`)
    }
  },

  /**
   * Reset LLM providers to clean defaults (removes duplicates)
   */
  async resetLLMProviders(): Promise<{ status: string; providers_created: string[] }> {
    return fetchAPI('/api/v1/llm/providers/reset', { method: 'POST' })
  },

  async getRoutingStrategy(): Promise<RoutingStrategy> {
    try {
      const response = await fetchAPI<{ strategy: RoutingStrategy }>('/api/v1/llm/routing-strategy')
      return response.strategy
    } catch (error) {
      log('Error fetching routing strategy:', error)
      // Return default if backend not available
      return 'BEST_AVAILABLE'
    }
  },

  async setRoutingStrategy(strategy: RoutingStrategy): Promise<{ success: boolean }> {
    try {
      log('Setting routing strategy to:', strategy)
      await fetchAPI('/api/v1/llm/routing-strategy', {
        method: 'POST',
        body: JSON.stringify({
          strategy: strategy,
          config: {}
        })
      })
      return { success: true }
    } catch (error) {
      log('Error setting routing strategy:', error)
      throw new Error(`Failed to set routing strategy: ${error}`)
    }
  },

  async getRoutingAnalytics(): Promise<RoutingAnalytics> {
    try {
      const analytics = await fetchAPI<{
        total_requests?: number
        total_cost?: number
        by_provider?: Record<string, number>
        by_model?: Record<string, number>
      }>('/api/v1/llm/analytics')

      // Transform backend analytics to expected format
      const providerUsage = Object.entries(analytics.by_provider || {}).map(([provider, count]) => ({
        provider,
        requests: count as number,
        percentage: analytics.total_requests ? ((count as number) / analytics.total_requests * 100) : 0,
      }))

      return {
        totalRequests: analytics.total_requests || 0,
        routingDecisions: {
          primary: analytics.total_requests || 0,
          backup: 0,
          costOptimized: 0,
          latencyOptimized: 0,
        },
        costSavings: {
          total: 0,
          percentageSaved: 0,
        },
        latencyStats: {
          avgMs: 1000,
          p50Ms: 800,
          p95Ms: 2000,
          p99Ms: 3000,
        },
        providerUsage,
        timeSeriesData: [],
      }
    } catch (error) {
      log('Error fetching routing analytics:', error)
      throw new Error(`Failed to fetch routing analytics: ${error}`)
    }
  },

  // Model Router Configuration
  async getRouterConfig(scope: 'organization' | 'workflow' | 'agent', scopeId?: string): Promise<any> {
    try {
      const params = new URLSearchParams()
      params.append('scope', scope)
      if (scopeId) params.append('scope_id', scopeId)

      const config = await fetchAPI(`/api/v1/routing/config?${params.toString()}`)
      return config
    } catch (error) {
      log('Error fetching router config:', error)
      // Return default config if backend not available
      return {
        scope,
        scopeId,
        strategyType: 'cost_optimized',
        minQualityScore: 0.7,
        maxLatency: 5000,
        modelPreferences: []
      }
    }
  },

  async saveRouterConfig(config: any): Promise<{ success: boolean }> {
    try {
      log('Saving router config:', config)
      await fetchAPI('/api/v1/routing/config', {
        method: 'POST',
        body: JSON.stringify(config)
      })
      return { success: true }
    } catch (error) {
      log('Error saving router config:', error)
      throw new Error(`Failed to save router config: ${error}`)
    }
  },

  async testRouting(config: any): Promise<any> {
    try {
      log('Testing routing with config:', config)
      const result = await fetchAPI('/api/v1/routing/test', {
        method: 'POST',
        body: JSON.stringify(config)
      })
      return result
    } catch (error) {
      log('Error testing routing:', error)
      // Return mock result if backend not available
      return {
        selectedModel: 'claude-3-haiku',
        estimatedCost: 0.25,
        estimatedLatency: 800,
        reason: 'cost_optimized'
      }
    }
  },

  // -------------------------------------------------------------------------
  // Cost Management
  // -------------------------------------------------------------------------
  async getCostSummary(): Promise<CostSummary> {
    try {
      const data = await fetchAPI<{
        total_cost: number
        provider_breakdown: Record<string, number>
        model_breakdown: Record<string, number>
      }>('/api/v1/cost/summary?organization_id=default')

      // Transform backend cost summary to frontend format
      // Note: Backend returns total_cost for the queried period
      // For more granular data, we would need additional API calls or parameters
      return {
        today: data.total_cost || 0,
        yesterday: 0, // TODO: Fetch from backend with specific date range
        thisWeek: 0, // TODO: Fetch from backend with specific date range
        thisMonth: data.total_cost || 0,
        lastMonth: 0, // TODO: Fetch from backend with specific date range
        byProvider: data.provider_breakdown || {},
        byModel: data.model_breakdown || {},
        trend: [], // TODO: Fetch time-series data from backend
      }
    } catch (error) {
      log('Error fetching cost summary:', error)
      throw new Error(`Failed to fetch cost summary: ${error}`)
    }
  },

  async getBudgetAlerts(): Promise<BudgetAlert[]> {
    try {
      const budgets = await fetchAPI<Array<{
        budget_id: string
        name: string
        amount: number
        period: string
        alert_threshold_warning: number
        alert_threshold_critical: number
        auto_disable_on_exceeded: boolean
      }>>('/api/v1/cost/budgets?organization_id=default')

      return budgets.map(b => ({
        id: b.budget_id,
        name: b.name,
        threshold: b.amount,
        current: 0,
        period: b.period as 'daily' | 'weekly' | 'monthly',
        status: 'ok' as const,
        alertThresholdWarning: b.alert_threshold_warning,
        alertThresholdCritical: b.alert_threshold_critical,
        autoDisableOnExceeded: b.auto_disable_on_exceeded,
      }))
    } catch (error) {
      log('Error fetching budget alerts:', error)
      throw new Error(`Failed to fetch budget alerts: ${error}`)
    }
  },

  async getCostForecast(): Promise<CostForecast> {
    try {
      const forecast = await fetchAPI<{
        predicted_cost: number
        confidence_lower: number
        confidence_upper: number
        trend: string
      }>('/api/v1/cost/forecast?organization_id=default&forecast_days=30')

      return {
        next7Days: forecast.predicted_cost * 0.23,
        next30Days: forecast.predicted_cost,
        next90Days: forecast.predicted_cost * 3,
        confidence: 0.85,
        trend: forecast.trend as 'increasing' | 'decreasing' | 'stable',
        projectedOverage: null,
      }
    } catch (error) {
      log('Error fetching cost forecast:', error)
      throw new Error(`Failed to fetch cost forecast: ${error}`)
    }
  },

  async createBudget(budget: {
    name: string
    period: 'daily' | 'weekly' | 'monthly'
    amount: number
    alertThresholdWarning?: number
    alertThresholdCritical?: number
    autoDisableOnExceeded?: boolean
  }): Promise<BudgetAlert> {
    try {
      const response = await fetchAPI<{
        budget_id: string
        name: string
        period: string
        amount: number
        alert_threshold_warning: number
        alert_threshold_critical: number
        auto_disable_on_exceeded: boolean
      }>('/api/v1/cost/budgets', {
        method: 'POST',
        body: JSON.stringify({
          organization_id: 'default',
          name: budget.name,
          period: budget.period,
          amount: budget.amount,
          alert_threshold_info: 50,
          alert_threshold_warning: budget.alertThresholdWarning ?? 75,
          alert_threshold_critical: budget.alertThresholdCritical ?? 90,
          auto_disable_on_exceeded: budget.autoDisableOnExceeded ?? false,
        }),
      })

      return {
        id: response.budget_id,
        name: response.name,
        threshold: response.amount,
        current: 0,
        period: response.period as 'daily' | 'weekly' | 'monthly',
        status: 'ok',
        alertThresholdWarning: response.alert_threshold_warning,
        alertThresholdCritical: response.alert_threshold_critical,
        autoDisableOnExceeded: response.auto_disable_on_exceeded,
      }
    } catch (error) {
      log('Error creating budget:', error)
      throw new Error(`Failed to create budget: ${error}`)
    }
  },

  async updateBudget(budgetId: string, budget: {
    name?: string
    period?: 'daily' | 'weekly' | 'monthly'
    amount?: number
    alertThresholdWarning?: number
    alertThresholdCritical?: number
    autoDisableOnExceeded?: boolean
  }): Promise<void> {
    try {
      await fetchAPI(`/api/v1/cost/budgets/${budgetId}`, {
        method: 'PATCH',
        body: JSON.stringify({
          name: budget.name,
          period: budget.period,
          amount: budget.amount,
          alert_threshold_warning: budget.alertThresholdWarning,
          alert_threshold_critical: budget.alertThresholdCritical,
          auto_disable_on_exceeded: budget.autoDisableOnExceeded,
        }),
      })
    } catch (error) {
      log('Error updating budget:', error)
      throw new Error(`Failed to update budget: ${error}`)
    }
  },

  async deleteBudget(budgetId: string): Promise<void> {
    try {
      await fetchAPI(`/api/v1/cost/budgets/${budgetId}`, {
        method: 'DELETE',
      })
    } catch (error) {
      log('Error deleting budget:', error)
      throw new Error(`Failed to delete budget: ${error}`)
    }
  },

  // -------------------------------------------------------------------------
  // Time-Travel Debugger
  // -------------------------------------------------------------------------
  async getExecutions(): Promise<TimeTravelExecution[]> {
    try {
      const executions = await fetchAPI<Array<{
        execution_id: string
        workflow_id: string
        workflow_name?: string
        status: string
        started_at: string
        completed_at?: string
        total_cost?: number
        error?: string
        node_states?: Record<string, {
          status?: string
          output?: {
            ab_testing?: {
              assignment_id: number
              experiment_id: number
              variant_name: string
            }
            [key: string]: unknown
          }
          duration?: number
          cost?: number
        }>
        node_executions?: Array<{
          id: number
          name: string
          timestamp: string
          duration: string
          status: 'completed' | 'failed' | 'pending' | 'running'
          state: {
            input?: string
            output?: string
            model?: string
            tokens?: number
            cost?: number
            confidence?: number
            error?: string
          }
        }>
      }>>('/api/workflows/executions')

      // Sort executions by start time (latest first)
      executions.sort((a, b) => new Date(b.started_at).getTime() - new Date(a.started_at).getTime())

      return executions.map(e => {
        const nodeStates = e.node_states || {}

        // Build consolidated node steps from node_executions
        // Real executions have multiple entries per node (Starting/Executing/Completed)
        // We consolidate to one entry per node showing the final state
        const rawNE = e.node_executions || []

        // Detect format: real WebSocket executions have 'name' like "Completed X", seeded have 'node_id'
        const isWebSocketFormat = rawNE.length > 0 && rawNE[0] && ('name' in rawNE[0]) && typeof (rawNE[0] as Record<string, unknown>).name === 'string' && !(rawNE[0] as Record<string, unknown>).node_id

        let consolidatedSteps: ExecutionStep[]

        if (isWebSocketFormat) {
          // Real executions: consolidate per node, skip "Starting workflow" and "Workflow completed" bookends
          const nodeMap = new Map<string, Record<string, unknown>>()

          for (const ne of rawNE) {
            const rec = ne as Record<string, unknown>
            const name = rec.name as string || ''

            // Skip bookend entries
            if (name.startsWith('Starting workflow') || name.startsWith('Workflow execution')) continue

            // Extract node label from "Executing X" or "Completed X"
            let nodeLabel = name
            if (name.startsWith('Executing ')) nodeLabel = name.replace('Executing ', '')
            else if (name.startsWith('Completed ')) nodeLabel = name.replace('Completed ', '')

            // Merge: later entries (Completed) override earlier ones (Executing)
            const existing = nodeMap.get(nodeLabel)
            const state = rec.state as Record<string, unknown> | undefined
            if (!existing || name.startsWith('Completed')) {
              nodeMap.set(nodeLabel, {
                name: nodeLabel,
                timestamp: rec.timestamp as string || '',
                duration: rec.duration as string || '-',
                status: rec.status as string || 'completed',
                output: state?.output as string | undefined,
                input: state?.input as string | undefined,
                model: state?.model as string | undefined,
                cost: state?.cost as number | undefined,
                error: state?.error as string | undefined,
              })
            }
          }

          consolidatedSteps = Array.from(nodeMap.entries()).map(([label, data], idx) => {
            // Match node_states by index order to get structured output
            const stateKeys = Object.keys(nodeStates)
            const nodeId = stateKeys[idx] || label

            // Merge output from node_states (structured data)
            const nodeState = nodeStates[nodeId]
            let outputStr = data.output as string | undefined

            if (nodeState?.output) {
              outputStr = JSON.stringify(nodeState.output)
            }

            return {
              id: idx,
              name: label,
              timestamp: data.timestamp as string,
              duration: data.duration as string,
              status: (data.status as string) as ExecutionStep['status'],
              state: {
                input: data.input as string | undefined,
                output: outputStr,
                model: data.model as string | undefined,
                cost: nodeState?.cost ?? (data.cost as number | undefined),
                error: data.error as string | undefined,
              },
            }
          })
        } else {
          // Seeded executions: one entry per node with node_id
          consolidatedSteps = rawNE.map((ne: Record<string, unknown>, idx: number) => {
            const nodeId = (ne.node_id as string) || `step-${idx}`
            const nodeState = nodeStates[nodeId]
            let outputStr: string | undefined
            if (nodeState?.output) {
              outputStr = JSON.stringify(nodeState.output)
            }

            return {
              id: idx,
              name: (ne.node_id as string) || `Step ${idx + 1}`,
              timestamp: (ne.started_at as string) || e.started_at || '',
              duration: ne.duration_seconds != null ? `${Number(ne.duration_seconds).toFixed(1)}s` : '0s',
              status: ((ne.status as string) || 'completed') as ExecutionStep['status'],
              state: {
                input: ne.input as string | undefined,
                output: outputStr || ne.output as string | undefined,
                error: ne.error as string | undefined,
              },
            }
          })
        }

        return {
          id: e.execution_id,
          workflowId: e.workflow_id,
          workflowName: e.workflow_name || 'Workflow',
          status: e.status as 'completed' | 'failed' | 'running',
          startTime: e.started_at,
          endTime: e.completed_at,
          stateCount: consolidatedSteps.length,
          totalCost: e.total_cost || 0,
          error: e.error,
          nodeExecutions: consolidatedSteps,
          node_states: nodeStates,
        }
      })
    } catch (error) {
      log('Error fetching executions:', error)
      throw new Error(`Failed to fetch executions: ${error}`)
    }
  },

  // -------------------------------------------------------------------------
  // Human-in-the-Loop
  // -------------------------------------------------------------------------
  async getPendingApprovals(): Promise<HITLApproval[]> {
    try {
      const approvals = await fetchAPI<Array<{
        id: number
        title: string
        description: string
        priority: string
        requester_user_id: string
        created_at: string
        expires_at: string
        context?: Record<string, unknown>
      }>>('/api/v1/hitl/approvals/pending/me')

      return approvals.map(a => ({
        id: String(a.id),
        action: a.title || a.description,
        riskLevel: a.priority === 'critical' ? 'critical' : a.priority === 'high' ? 'high' : 'medium',
        requestedBy: a.requester_user_id,
        requestedAt: a.created_at,
        context: a.context || {},
        expiresAt: a.expires_at,
      }))
    } catch (error) {
      log('Error fetching pending approvals:', error)
      throw new Error(`Failed to fetch pending approvals: ${error}`)
    }
  },

  async approveAction(id: string, comment?: string): Promise<{ success: boolean }> {
    try {
      await fetchAPI(`/api/v1/hitl/approvals/${id}/decide`, {
        method: 'POST',
        body: JSON.stringify({
          decision: 'approved',
          comment,
        }),
      })
      return { success: true }
    } catch (error) {
      log('Error approving action:', error)
      throw new Error(`Failed to approve action: ${error}`)
    }
  },

  async rejectAction(id: string, reason: string): Promise<{ success: boolean }> {
    try {
      await fetchAPI(`/api/v1/hitl/approvals/${id}/decide`, {
        method: 'POST',
        body: JSON.stringify({
          decision: 'rejected',
          comment: reason,
        }),
      })
      return { success: true }
    } catch (error) {
      log('Error rejecting action:', error)
      throw new Error(`Failed to reject action: ${error}`)
    }
  },

  // -------------------------------------------------------------------------
  // A/B Testing
  // -------------------------------------------------------------------------
  async createExperiment(experiment: {
    name: string
    description?: string
    task_type?: string
    variants: Array<{ name: string; traffic_percentage: number; model_name?: string; config?: Record<string, unknown> }>
  }): Promise<{ id: string }> {
    try {
      // Generate a unique slug from name + timestamp
      const slug = experiment.name
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-|-$/g, '') + '-' + Date.now().toString(36)

      const result = await fetchAPI<{ id: number }>('/api/v1/experiments', {
        method: 'POST',
        body: JSON.stringify({
          name: experiment.name,
          slug: slug,
          description: experiment.description || '',
          task_type: experiment.task_type || null,
          variants: experiment.variants.map((v, i) => ({
            name: v.name,
            variant_key: `variant_${i}`,
            variant_type: i === 0 ? 'control' : 'treatment',
            traffic_percentage: v.traffic_percentage,
            model_name: v.model_name || null,
            config: v.config || {},
          })),
        }),
      })
      return { id: String(result.id) }
    } catch (error) {
      log('Error creating experiment:', error)
      throw error
    }
  },

  async startExperiment(experimentId: string): Promise<{ success: boolean }> {
    try {
      await fetchAPI(`/api/v1/experiments/${experimentId}/start`, {
        method: 'POST',
      })
      return { success: true }
    } catch (error) {
      log('Error starting experiment:', error)
      throw new Error(`Failed to start experiment: ${error}`)
    }
  },

  async pauseExperiment(experimentId: string): Promise<{ success: boolean }> {
    try {
      await fetchAPI(`/api/v1/experiments/${experimentId}/pause`, {
        method: 'POST',
      })
      return { success: true }
    } catch (error) {
      log('Error pausing experiment:', error)
      throw new Error(`Failed to pause experiment: ${error}`)
    }
  },

  async completeExperiment(experimentId: string, promoteWinner?: boolean): Promise<{ success: boolean }> {
    try {
      await fetchAPI(`/api/v1/experiments/${experimentId}/complete?promote_winner=${promoteWinner || false}`, {
        method: 'POST',
      })
      return { success: true }
    } catch (error) {
      log('Error completing experiment:', error)
      throw new Error(`Failed to complete experiment: ${error}`)
    }
  },

  async getExperiments(): Promise<ABExperiment[]> {
    try {
      const experiments = await fetchAPI<Array<{
        id: number
        name: string
        status: string
        created_at: string
        completed_at?: string
        winner_variant_id?: number | null
        is_statistically_significant?: boolean
        p_value?: number | null
        confidence_level?: number
        task_type?: string
        variants?: Array<{
          id: number
          name: string
          traffic_percentage: number
          success_count: number
          sample_count: number
          avg_latency_ms?: number
          avg_cost?: number
          is_winner?: boolean
        }>
      }>>('/api/v1/experiments')

      return experiments.map(e => {
        // Derive significance from backend's real statistical test results.
        // p_value is from a chi-square test; confidence = 1 - p_value.
        // When p_value is null (no data / not enough samples), show 0%.
        let significanceLevel = 0
        if (e.is_statistically_significant) {
          significanceLevel = e.p_value != null ? Math.min(1 - e.p_value, 1) : 0.95
        } else if (e.p_value != null) {
          significanceLevel = Math.max(1 - e.p_value, 0)
        }
        // else: no data yet, stays at 0

        // Extract workflow ID(s) from task_type
        // Supports: "workflow:{uuid}" (single) or "workflows:{uuid1},{uuid2},..." (multiple)
        let targetWorkflowId: string | undefined
        let targetWorkflowIds: string[] | undefined
        if (e.task_type?.startsWith('workflows:')) {
          // Multiple workflows
          const idsStr = e.task_type.substring('workflows:'.length)
          targetWorkflowIds = idsStr.split(',').map(id => id.trim())
          targetWorkflowId = targetWorkflowIds[0] // First one for display
        } else if (e.task_type?.startsWith('workflow:')) {
          // Single workflow
          targetWorkflowId = e.task_type.substring('workflow:'.length)
          targetWorkflowIds = [targetWorkflowId]
        }

        return {
          id: String(e.id),
          name: e.name,
          status: e.status as 'running' | 'completed' | 'draft' | 'paused',
          startDate: e.created_at,
          endDate: e.completed_at,
          variants: (e.variants || []).map(v => ({
            name: v.name,
            traffic: v.traffic_percentage,
            conversions: v.success_count,
            totalRequests: v.sample_count,
            avgLatency: Math.round(v.avg_latency_ms ?? 0),
            costPer1k: v.avg_cost != null && v.avg_cost > 0
              ? parseFloat((v.avg_cost * 1000).toFixed(2))
              : 0,
          })),
          significanceLevel,
          winner: e.winner_variant_id
            ? ((e.variants || []).find(v => v.id === e.winner_variant_id)?.name
              ?? (e.variants || []).find(v => v.is_winner)?.name
              ?? null)
            : null,
          // Targeting info
          taskType: e.task_type,
          targetWorkflowId,
          targetWorkflowIds,
        }
      })
    } catch (error) {
      log('Error fetching experiments:', error)
      throw new Error(`Failed to fetch experiments: ${error}`)
    }
  },

  // -------------------------------------------------------------------------
  // Audit Logs
  // -------------------------------------------------------------------------
  async getAuditLogs(filters?: { action?: string; user?: string; limit?: number }): Promise<AuditLogEntry[]> {
    try {
      const params = new URLSearchParams()
      if (filters?.action) params.append('action', filters.action)
      if (filters?.user) params.append('user_id', filters.user)
      if (filters?.limit) params.append('limit', String(filters.limit))

      const data = await fetchAPI<{
        events: Array<{
          event_id: string
          timestamp: string
          action: string
          user_email?: string
          user_id?: string
          resource_type?: string
          resource_id?: string
          changes?: Record<string, unknown>
          details?: Record<string, unknown>
          severity?: 'info' | 'warning' | 'error' | 'critical'
          ip_address?: string
          user_agent?: string
        }>
      }>(`/api/v1/audit/events?${params.toString()}`)

      return data.events.map(e => ({
        id: e.event_id,
        timestamp: e.timestamp,
        action: e.action,
        user: e.user_email || e.user_id || 'system',
        resource: e.resource_type,
        resourceId: e.resource_id,
        details: e.details || e.changes || {},
        severity: e.severity,
        ip: e.ip_address || '',
        ipAddress: e.ip_address,
        userAgent: e.user_agent,
      }))
    } catch (error) {
      log('Error fetching audit logs:', error)
      throw new Error(`Failed to fetch audit logs: ${error}`)
    }
  },

  // -------------------------------------------------------------------------
  // Settings Management
  // -------------------------------------------------------------------------
  async getSettings(): Promise<Record<string, unknown>> {
    try {
      return await fetchAuthAPI<Record<string, unknown>>('/api/v1/settings')
    } catch (error) {
      log('Error fetching settings:', error)
      throw new Error(`Failed to fetch settings: ${error}`)
    }
  },

  async updateSettings(settings: Record<string, unknown>): Promise<{ success: boolean }> {
    try {
      await fetchAuthAPI('/api/v1/settings', {
        method: 'PUT',
        body: JSON.stringify(settings),
      })
      return { success: true }
    } catch (error) {
      log('Error updating settings:', error)
      throw new Error(`Failed to update settings: ${error}`)
    }
  },

  async getOrgPlan(): Promise<{
    id: string
    name: string
    slug: string
    plan: string
    max_users: number
    max_agents: number
    enabled_features: string[]
    settings: Record<string, unknown> | null
  }> {
    try {
      return await fetchAuthAPI('/api/v1/settings/organization')
    } catch (error) {
      log('Error fetching org plan:', error)
      throw new Error(`Failed to fetch organization plan: ${error}`)
    }
  },

  // API Keys Management
  async getApiKeys(): Promise<Array<{
    id: number
    name: string
    key_prefix: string
    permissions?: string[]
    created_at: string
    expires_at?: string
    last_used_at?: string
    is_active: boolean
  }>> {
    try {
      return await fetchAuthAPI('/api/v1/settings/api-keys')
    } catch (error) {
      log('Error fetching API keys:', error)
      throw new Error(`Failed to fetch API keys: ${error}`)
    }
  },

  async createApiKey(name: string): Promise<{
    id: number
    name: string
    key: string
    key_prefix: string
    created_at: string
    is_active: boolean
  }> {
    try {
      return await fetchAuthAPI('/api/v1/settings/api-keys', {
        method: 'POST',
        body: JSON.stringify({ name }),
      })
    } catch (error) {
      log('Error creating API key:', error)
      throw new Error(`Failed to create API key: ${error}`)
    }
  },

  async revokeApiKey(keyId: number): Promise<{ success: boolean }> {
    try {
      await fetchAuthAPI(`/api/v1/settings/api-keys/${keyId}`, {
        method: 'DELETE',
      })
      return { success: true }
    } catch (error) {
      log('Error revoking API key:', error)
      throw new Error(`Failed to revoke API key: ${error}`)
    }
  },

  // Team Members Management
  async getTeamMembers(): Promise<Array<{
    id: number
    name?: string
    email: string
    role: string
    status: string
    joined_at?: string
    last_seen_at?: string
  }>> {
    try {
      return await fetchAuthAPI('/api/v1/settings/team')
    } catch (error) {
      log('Error fetching team members:', error)
      throw new Error(`Failed to fetch team members: ${error}`)
    }
  },

  async inviteTeamMember(email: string, name?: string, role?: string): Promise<{
    id: number
    email: string
    name?: string
    role: string
    status: string
  }> {
    try {
      return await fetchAuthAPI('/api/v1/settings/team', {
        method: 'POST',
        body: JSON.stringify({
          email,
          name: name || null,
          role: role || 'member',
        }),
      })
    } catch (error) {
      log('Error inviting team member:', error)
      throw new Error(`Failed to invite team member: ${error}`)
    }
  },

  async removeTeamMember(memberId: number): Promise<{ success: boolean }> {
    try {
      await fetchAuthAPI(`/api/v1/settings/team/${memberId}`, {
        method: 'DELETE',
      })
      return { success: true }
    } catch (error) {
      log('Error removing team member:', error)
      throw new Error(`Failed to remove team member: ${error}`)
    }
  },

  // -------------------------------------------------------------------------
  // Task Metrics (for charts)
  // -------------------------------------------------------------------------
  async getTaskSuccessTimeSeries(): Promise<{ timestamp: string; success: number; failed: number }[]> {
    try {
      // TODO: implement backend endpoint
      return []
    } catch (error) {
      log('Error fetching task success time series:', error)
      throw new Error(`Failed to fetch task success time series: ${error}`)
    }
  },

  async getCostTimeSeries(): Promise<{ timestamp: string; cost: number }[]> {
    try {
      // TODO: implement backend endpoint
      return []
    } catch (error) {
      log('Error fetching cost time series:', error)
      throw new Error(`Failed to fetch cost time series: ${error}`)
    }
  },

  // -------------------------------------------------------------------------
  // Agent Management (Dedicated Methods)
  // -------------------------------------------------------------------------
  async getAgents(status?: string): Promise<AgentDetail[]> {
    try {
      const params = status ? `?status=${status}` : ''
      const data = await fetchAPI<{
        agents: Array<{
          agent_id: string
          name: string
          capabilities: string[]
          framework?: string
          version?: string
        }>
      }>(`/api/v1/agents${params}`)

      // Transform backend response to frontend AgentDetail type
      return data.agents.map(agent => ({
        agent_id: agent.agent_id,
        name: agent.name,
        status: 'active' as const,
        capabilities: agent.capabilities,
        active_tasks: 0,
        tasks_completed: 0,
        tasks_failed: 0,
        cost_today: 0,
        last_seen: new Date().toISOString(),
      }))
    } catch (error) {
      log('Error fetching agents:', error)
      throw new Error(`Failed to fetch agents: ${error}`)
    }
  },

  async getAgentById(agentId: string): Promise<AgentDetail> {
    try {
      const agent = await fetchAPI<{
        agent_id: string
        name: string
        status: string
        capabilities: string[]
        tasks_completed?: number
        tasks_failed?: number
        avg_task_duration_ms?: number
        last_heartbeat?: string
      }>(`/api/v1/agents/${agentId}`)

      return {
        agent_id: agent.agent_id,
        name: agent.name,
        status: agent.status as 'active' | 'idle' | 'error',
        capabilities: agent.capabilities,
        active_tasks: 0,
        tasks_completed: agent.tasks_completed || 0,
        tasks_failed: agent.tasks_failed || 0,
        cost_today: 0,
        last_seen: agent.last_heartbeat || new Date().toISOString(),
      }
    } catch (error) {
      log('Error fetching agent by ID:', error)
      throw new Error(`Failed to fetch agent: ${error}`)
    }
  },

  async registerAgent(config: {
    name: string
    capabilities: string[]
    metadata?: Record<string, unknown>
  }): Promise<{ agent_id: string; api_key: string; status: string }> {
    try {
      return await fetchAPI('/api/v1/agents', {
        method: 'POST',
        body: JSON.stringify(config),
      })
    } catch (error) {
      log('Error registering agent:', error)
      throw new Error(`Failed to register agent: ${error}`)
    }
  },

  async deregisterAgent(agentId: string): Promise<void> {
    try {
      await fetchAPI(`/api/v1/agents/${agentId}`, {
        method: 'DELETE',
      })
    } catch (error) {
      log('Error deregistering agent:', error)
      throw new Error(`Failed to deregister agent: ${error}`)
    }
  },

  // -------------------------------------------------------------------------
  // Task Management (Dedicated Methods)
  // -------------------------------------------------------------------------
  async getTasks(filters?: TaskFilters): Promise<Task[]> {
    try {
      const params = new URLSearchParams()
      if (filters?.status) params.append('status', filters.status)
      if (filters?.capability) params.append('capability', filters.capability)
      const qs = params.toString()
      const url = `/api/v1/tasks${qs ? `?${qs}` : ''}`

      const response = await fetchAPI<{
        tasks: Array<{
          task_id: string
          capability: string
          status: string
          priority?: string
          created_at?: string
          started_at?: string
          completed_at?: string
          assigned_agent_id?: string
          retry_count?: number
          cost?: number
          input_data?: Record<string, any>
          output?: Record<string, any>
          error?: string
        }>
        total: number
      }>(url)

      return response.tasks.map(t => ({
        task_id: t.task_id,
        capability: t.capability,
        status: t.status as TaskStatus,
        priority: t.priority as TaskPriority | undefined,
        assigned_agent_id: t.assigned_agent_id,
        input: t.input_data || {},
        output: t.output,
        error: t.error,
        created_at: t.created_at || '',
        started_at: t.started_at,
        completed_at: t.completed_at,
        retry_count: t.retry_count,
        cost: t.cost,
      }))
    } catch (error) {
      log('Error fetching tasks:', error)
      throw new Error(`Failed to fetch tasks: ${error}`)
    }
  },

  async getTaskById(taskId: string): Promise<Task> {
    try {
      const task = await fetchAPI<{
        task_id: string
        capability: string
        status: string
        assigned_agent_id?: string
        created_at: string
        started_at?: string
        completed_at?: string
        retry_count?: number
        cost?: number
        output?: Record<string, any>
        error?: string
      }>(`/api/v1/tasks/${taskId}`)

      return {
        task_id: task.task_id,
        capability: task.capability,
        status: task.status as TaskStatus,
        assigned_agent_id: task.assigned_agent_id,
        input: {},
        output: task.output,
        error: task.error,
        created_at: task.created_at,
        started_at: task.started_at,
        completed_at: task.completed_at,
        retry_count: task.retry_count,
        cost: task.cost,
      }
    } catch (error) {
      log('Error fetching task by ID:', error)
      throw new Error(`Failed to fetch task: ${error}`)
    }
  },

  async submitTask(task: TaskSubmission): Promise<TaskResponse> {
    try {
      const response = await fetchAPI<TaskResponse>('/api/v1/tasks', {
        method: 'POST',
        body: JSON.stringify(task),
      })
      return response
    } catch (error) {
      log('Error submitting task:', error)
      throw new Error(`Failed to submit task: ${error}`)
    }
  },

  async cancelTask(_taskId: string): Promise<void> {
    try {
      // Note: Backend doesn't have a cancel task endpoint yet
      log('Warning: Backend does not have a cancel task endpoint yet.')
      throw new Error('Cancel task not implemented in backend')
    } catch (error) {
      log('Error cancelling task:', error)
      throw new Error(`Failed to cancel task: ${error}`)
    }
  },

  // -------------------------------------------------------------------------
  // Marketplace
  // -------------------------------------------------------------------------
  async searchAgents(query?: string, category?: string, itemType?: string): Promise<Array<{
    id: number
    name: string
    tagline: string
    description: string
    category: string
    item_type: string
    author: string
    version: string
    install_count: number
    avg_rating: number
    rating_count: number
    pricing: string
    verified: boolean
    agent_config?: Record<string, unknown> | null
  }>> {
    try {
      const params = new URLSearchParams()
      if (query) params.append('query', query)
      if (category) params.append('category', category)
      if (itemType) params.append('item_type', itemType)

      const data = await fetchAuthAPI<{
        agents: Array<{
          id: number
          name: string
          tagline: string
          description: string
          category: string
          item_type: string
          author: string
          version: string
          install_count: number
          avg_rating: number
          rating_count: number
          pricing: string
          verified: boolean
          agent_config?: Record<string, unknown> | null
        }>
      }>(`/api/v1/marketplace/agents?${params.toString()}`)
      return data.agents
    } catch (error) {
      log('Error searching agents:', error)
      throw new Error(`Failed to search agents: ${error}`)
    }
  },

  async getFeaturedAgents(limit = 10): Promise<Array<{
    id: number
    name: string
    tagline: string
    description: string
    category: string
    author: string
    version: string
    install_count: number
    avg_rating: number
    rating_count: number
    pricing: string
    verified: boolean
  }>> {
    try {
      return await fetchAPI(`/api/v1/marketplace/featured?limit=${limit}`)
    } catch (error) {
      log('Error fetching featured agents:', error)
      throw new Error(`Failed to fetch featured agents: ${error}`)
    }
  },

  async installAgent(agentId: number, config?: Record<string, unknown>): Promise<{
    installation_id: number
    agent_id: number
    status: string
  }> {
    try {
      return await fetchAuthAPI('/api/v1/marketplace/install', {
        method: 'POST',
        body: JSON.stringify({
          agent_id: agentId,
          config_overrides: config || {},
        }),
      })
    } catch (error) {
      log('Error installing agent:', error)
      throw new Error(`Failed to install agent: ${error}`)
    }
  },

  async uninstallAgent(installationId: number): Promise<void> {
    try {
      await fetchAuthAPI(`/api/v1/marketplace/installations/${installationId}`, {
        method: 'DELETE',
      })
    } catch (error) {
      log('Error uninstalling agent:', error)
      throw new Error(`Failed to uninstall agent: ${error}`)
    }
  },

  async getInstalledAgents(): Promise<Array<{
    id: number
    agent_id: number
    version: string
    status: string
    installed_agent_id: number | null
    error_message: string | null
    installed_at: string
    auto_update: boolean
  }>> {
    try {
      return await fetchAuthAPI('/api/v1/marketplace/installations')
    } catch (error) {
      log('Error fetching installed agents:', error)
      throw new Error(`Failed to fetch installed agents: ${error}`)
    }
  },

  async getInstalledAgentsWithDetails(): Promise<{
    installed_agents: Array<{
      installation_id: number
      agent_id: number
      name: string
      slug: string
      tagline: string
      description: string
      category: string
      author: string
      version: string
      agent_config: Record<string, unknown>
      status: string
      installed_at: string | null
      last_used_at: string | null
      usage_count: number
      config_overrides: Record<string, unknown>
    }>
    total: number
  }> {
    try {
      return await fetchAuthAPI('/api/v1/marketplace/installations/details')
    } catch (error) {
      log('Error fetching installed agents with details:', error)
      // Return empty list on error
      return { installed_agents: [], total: 0 }
    }
  },

  async publishAgent(agent: {
    name: string
    slug: string
    tagline: string
    description: string
    category: string
    pricing: string
    price_usd?: number
    tags: string[]
    agent_config: Record<string, unknown>
    version: string
  }): Promise<{
    id: number
    name: string
    slug: string
    tagline: string
    description: string
    category: string
    pricing: string
    version: string
  }> {
    try {
      return await fetchAuthAPI('/api/v1/marketplace/agents', {
        method: 'POST',
        body: JSON.stringify(agent),
      })
    } catch (error) {
      log('Error publishing agent:', error)
      throw new Error(`Failed to publish agent: ${error}`)
    }
  },

  async deleteMarketplaceAgent(agentId: number): Promise<void> {
    try {
      await fetchAuthAPI(`/api/v1/marketplace/agents/${agentId}`, {
        method: 'DELETE',
      })
    } catch (error) {
      log('Error deleting marketplace agent:', error)
      throw new Error(`Failed to delete agent: ${error}`)
    }
  },

  async publishWorkflowAsTemplate(data: {
    workflow_id: string
    name: string
    tagline: string
    description: string
    category?: string
    tags?: string[]
  }): Promise<{ id: number; name: string; slug: string }> {
    try {
      return await fetchAuthAPI('/api/v1/marketplace/publish-workflow', {
        method: 'POST',
        body: JSON.stringify(data),
      })
    } catch (error) {
      log('Error publishing workflow as template:', error)
      throw new Error(`Failed to publish workflow template: ${error}`)
    }
  },

  async useWorkflowTemplate(agentId: number): Promise<{ workflow_id: string }> {
    try {
      return await fetchAuthAPI('/api/v1/marketplace/use-template', {
        method: 'POST',
        body: JSON.stringify({ marketplace_agent_id: agentId }),
      })
    } catch (error) {
      log('Error using workflow template:', error)
      throw new Error(`Failed to use workflow template: ${error}`)
    }
  },

  // -------------------------------------------------------------------------
  // Integrations
  // -------------------------------------------------------------------------
  async browseIntegrations(filters?: {
    category?: string
    search?: string
    verified?: boolean
  }): Promise<{
    integrations: Array<{
      id: string
      name: string
      description: string
      category: string
      status: 'active' | 'inactive'
      verified: boolean
      install_count: number
      avg_rating: number
    }>
    total_count: number
  }> {
    try {
      const response = await fetchAPI<{
        integrations: Array<{
          integration_id: string
          name: string
          description: string
          category: string
          status?: string
          is_verified: boolean
          total_installations: number
          average_rating: number
        }>
        total_count: number
      }>('/api/v1/integrations/browse', {
        method: 'POST',
        body: JSON.stringify({
          category: filters?.category,
          search_query: filters?.search,
          is_verified: filters?.verified,
          limit: 50,
          offset: 0,
        }),
      })

      // Transform backend response to frontend format
      return {
        integrations: response.integrations.map(integration => ({
          id: integration.integration_id,  // Map integration_id to id
          name: integration.name,
          description: integration.description,
          category: integration.category,
          status: (integration.status || 'active') as 'active' | 'inactive',
          verified: integration.is_verified,
          install_count: integration.total_installations,
          avg_rating: integration.average_rating || 0,
        })),
        total_count: response.total_count,
      }
    } catch (error) {
      log('Error browsing integrations:', error)
      throw new Error(`Failed to browse integrations: ${error}`)
    }
  },

  async getIntegrationDetail(integrationId: string): Promise<{
    id: string
    name: string
    description: string
    category: string
    status: string
    verified: boolean
    install_count: number
    avg_rating: number
    configuration_schema: Record<string, unknown>
    supported_actions: Array<{
      name: string
      description: string
      parameters: Record<string, unknown>
    }>
  }> {
    try {
      const response = await fetchAPI<{
        integration_id: string
        name: string
        description: string
        category: string
        status?: string
        is_verified: boolean
        total_installations: number
        average_rating: number
        configuration_schema: Record<string, unknown>
        supported_actions: Array<{
          name: string
          description: string
          parameters: Record<string, unknown>
        }>
      }>(`/api/v1/integrations/${integrationId}`)

      // Transform backend response to frontend format
      return {
        id: response.integration_id,  // Map integration_id to id
        name: response.name,
        description: response.description,
        category: response.category,
        status: response.status || 'active',
        verified: response.is_verified,
        install_count: response.total_installations,
        avg_rating: response.average_rating || 0,
        configuration_schema: response.configuration_schema,
        supported_actions: response.supported_actions,
      }
    } catch (error) {
      log('Error fetching integration detail:', error)
      throw new Error(`Failed to fetch integration detail: ${error}`)
    }
  },

  async installIntegration(
    integrationId: string,
    organizationId: string,
    userId: string,
    config?: Record<string, unknown>
  ): Promise<{
    installation_id: string
    integration_id: string
    status: string
  }> {
    try {
      return await fetchAPI(`/api/v1/integrations/${integrationId}/install?user_id=${userId}`, {
        method: 'POST',
        body: JSON.stringify({
          organization_id: organizationId,
          configuration: config || {},
        }),
      })
    } catch (error) {
      log('Error installing integration:', error)
      throw new Error(`Failed to install integration: ${error}`)
    }
  },

  async uninstallIntegration(integrationId: string, organizationId: string): Promise<void> {
    try {
      // Use the connections endpoint which expects slug (e.g., "groq", "discord")
      const url = organizationId
        ? `/api/connections/${integrationId}?organization_id=${organizationId}`
        : `/api/connections/${integrationId}`
      await fetchAPI(url, {
        method: 'DELETE',
      })
    } catch (error) {
      log('Error uninstalling integration:', error)
      throw new Error(`Failed to uninstall integration: ${error}`)
    }
  },

  async testIntegration(
    integrationId: string,
    _installationId: string,
    actionName: string,
    params: Record<string, unknown>
  ): Promise<{
    success: boolean
    output_result?: unknown
    error_message?: string
  }> {
    try {
      // Use the connections execute endpoint which accepts string integration IDs
      const result = await fetchAPI<{
        success: boolean
        data?: unknown
        error?: string
        duration_ms?: number
      }>(`/api/connections/${integrationId}/execute`, {
        method: 'POST',
        body: JSON.stringify({
          action_name: actionName,
          parameters: params,
        }),
      })
      return {
        success: result.success,
        output_result: result.data,
        error_message: result.error,
      }
    } catch (error) {
      log('Error testing integration:', error)
      throw new Error(`Failed to test integration: ${error}`)
    }
  },

  async getInstalledIntegrations(organizationId: string): Promise<Array<{
    installation_id: string
    integration_id: string
    status: string
    installed_at: string
  }>> {
    try {
      return await fetchAPI(`/api/v1/integrations/installations/${organizationId}`)
    } catch (error) {
      log('Error fetching installed integrations:', error)
      throw new Error(`Failed to fetch installed integrations: ${error}`)
    }
  },

  async configureIntegration(
    installationId: string,
    configuration: Record<string, unknown>,
    authCredentials: Record<string, unknown>
  ): Promise<{
    installation_id: string
    status: string
    message: string
  }> {
    try {
      return await fetchAPI(`/api/v1/integrations/installations/${installationId}/configure`, {
        method: 'POST',
        body: JSON.stringify({
          configuration,
          auth_credentials: authCredentials,
        }),
      })
    } catch (error) {
      log('Error configuring integration:', error)
      throw new Error(`Failed to configure integration: ${error}`)
    }
  },

  /**
   * Start OAuth flow for an integration
   * Returns an authorization URL to redirect the user to
   */
  async startOAuthFlow(
    integrationSlug: string,
    organizationId: string
  ): Promise<{
    authorization_url: string
    state: string
  }> {
    try {
      return await fetchAPI(`/api/v1/integrations/${integrationSlug}/oauth/start`, {
        method: 'POST',
        body: JSON.stringify({
          organization_id: organizationId,
        }),
      })
    } catch (error) {
      log('Error starting OAuth flow:', error)
      throw new Error(`Failed to start OAuth flow: ${error}`)
    }
  },

  /**
   * Handle OAuth callback after user authorizes
   * Exchanges the code for tokens and creates/updates installation
   */
  async handleOAuthCallback(
    integrationSlug: string,
    code: string,
    state: string,
    organizationId: string
  ): Promise<{
    success: boolean
    installation_id?: string
    message: string
  }> {
    try {
      return await fetchAPI(`/api/v1/integrations/${integrationSlug}/oauth/callback`, {
        method: 'POST',
        body: JSON.stringify({
          code,
          state,
          organization_id: organizationId,
        }),
      })
    } catch (error) {
      log('Error handling OAuth callback:', error)
      throw new Error(`Failed to handle OAuth callback: ${error}`)
    }
  },

  /**
   * Get available actions for an installed integration
   */
  async getIntegrationActions(installationId: string): Promise<{
    actions: Array<{
      name: string
      display_name: string
      description: string
      input_schema: Record<string, unknown>
    }>
    count: number
  }> {
    try {
      return await fetchAPI(`/api/v1/integrations/installations/${installationId}/actions`)
    } catch (error) {
      log('Error fetching integration actions:', error)
      throw new Error(`Failed to fetch integration actions: ${error}`)
    }
  },

  /**
   * Execute an integration action (real API call)
   */
  async executeIntegrationAction(
    integrationId: string,
    installationId: string,
    actionName: string,
    parameters: Record<string, unknown>
  ): Promise<{
    success: boolean
    output_result?: unknown
    error_message?: string
    duration_ms?: number
  }> {
    try {
      return await fetchAPI(`/api/v1/integrations/${integrationId}/execute`, {
        method: 'POST',
        body: JSON.stringify({
          installation_id: installationId,
          action_name: actionName,
          input_parameters: parameters,
        }),
      })
    } catch (error) {
      log('Error executing integration action:', error)
      throw new Error(`Failed to execute integration action: ${error}`)
    }
  },

  // -------------------------------------------------------------------------
  // Workflow Management
  // -------------------------------------------------------------------------
  async getWorkflows(): Promise<Array<{ id: string; name: string; status: string }>> {
    try {
      // Backend returns workflows with 'id' field, not 'workflow_id'
      const data = await fetchAPI<{ workflows: Array<{ id: string; name: string; isTemplate?: boolean }> }>('/api/workflows')
      return data.workflows.map(w => ({
        id: w.id,
        name: w.name,
        status: w.isTemplate ? 'template' : 'active',
      }))
    } catch (error) {
      log('Error fetching workflows:', error)
      throw new Error(`Failed to fetch workflows: ${error}`)
    }
  },

  async getWorkflowById(workflowId: string): Promise<{ id: string; name: string; status: string; nodes: unknown[]; edges: unknown[] } | null> {
    try {
      // Backend returns nodes and edges at top level
      const workflow = await fetchAPI<{
        id: string
        name: string
        nodes: unknown[]
        edges: unknown[]
        isTemplate?: boolean
      }>(`/api/workflows/${workflowId}`)

      return {
        id: workflow.id,
        name: workflow.name,
        status: workflow.isTemplate ? 'template' : 'draft',
        nodes: workflow.nodes || [],
        edges: workflow.edges || [],
      }
    } catch (error) {
      log('Error fetching workflow by ID:', error)
      throw new Error(`Failed to fetch workflow by ID: ${error}`)
    }
  },

  async createWorkflow(workflow: { name: string; nodes: unknown[]; edges: unknown[] }): Promise<{ id: string }> {
    try {
      // Backend expects nodes and edges at top level, not nested in definition
      const result = await fetchAPI<{ id: string }>('/api/workflows', {
        method: 'POST',
        body: JSON.stringify({
          name: workflow.name,
          nodes: workflow.nodes,
          edges: workflow.edges,
        }),
      })
      return { id: result.id }
    } catch (error) {
      log('Error creating workflow:', error)
      throw error
    }
  },

  async updateWorkflow(workflowId: string, workflow: { name: string; nodes: unknown[]; edges: unknown[] }): Promise<{ id: string }> {
    try {
      const result = await fetchAPI<{ id: string }>(`/api/workflows/${workflowId}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: workflow.name,
          nodes: workflow.nodes,
          edges: workflow.edges,
        }),
      })
      return { id: result.id }
    } catch (error) {
      log('Error updating workflow:', error)
      throw error
    }
  },

  async executeWorkflow(workflowId: string, input?: Record<string, unknown>): Promise<{ executionId: string }> {
    try {
      const result = await fetchAPI<{ execution_id: string }>(`/api/workflows/${workflowId}/execute`, {
        method: 'POST',
        body: JSON.stringify({ input }),
      })
      return { executionId: result.execution_id }
    } catch (error) {
      log('Error executing workflow:', error)
      throw error
    }
  },

  // -------------------------------------------------------------------------
  // OAuth Settings Management
  // -------------------------------------------------------------------------

  /**
   * List all OAuth configurations for the organization
   * Returns both custom org configs and platform defaults
   */
  async getOAuthConfigs(organizationId: string): Promise<Array<{
    provider: string
    client_id: string
    client_id_masked: string
    has_client_secret: boolean
    custom_scopes?: string[]
    enabled: boolean
    is_custom: boolean
    created_at?: string
    updated_at?: string
  }>> {
    try {
      const response = await fetchAuthAPI<{
        configs: Array<{
          provider: string
          client_id: string
          client_id_masked: string
          has_client_secret: boolean
          custom_scopes?: string[]
          enabled: boolean
          is_custom: boolean
          created_at?: string
          updated_at?: string
        }>
      }>(`/api/settings/oauth?organization_id=${organizationId}`)
      return response.configs
    } catch (error) {
      log('Error fetching OAuth configs:', error)
      throw new Error(`Failed to fetch OAuth configs: ${error}`)
    }
  },

  /**
   * Get OAuth config for a specific provider
   */
  async getOAuthConfig(provider: string, organizationId: string): Promise<{
    provider: string
    client_id: string
    client_id_masked: string
    has_client_secret: boolean
    custom_scopes?: string[]
    enabled: boolean
    is_custom: boolean
    created_at?: string
    updated_at?: string
  }> {
    try {
      return await fetchAuthAPI(`/api/settings/oauth/${provider}?organization_id=${organizationId}`)
    } catch (error) {
      log('Error fetching OAuth config:', error)
      throw new Error(`Failed to fetch OAuth config: ${error}`)
    }
  },

  /**
   * Save custom OAuth configuration for a provider
   */
  async saveOAuthConfig(
    provider: string,
    organizationId: string,
    config: {
      client_id: string
      client_secret: string
      custom_scopes?: string[]
      enabled: boolean
    }
  ): Promise<{
    provider: string
    message: string
    is_custom: boolean
  }> {
    try {
      return await fetchAuthAPI(`/api/settings/oauth/${provider}?organization_id=${organizationId}`, {
        method: 'POST',
        body: JSON.stringify(config),
      })
    } catch (error) {
      log('Error saving OAuth config:', error)
      throw new Error(`Failed to save OAuth config: ${error}`)
    }
  },

  /**
   * Delete custom OAuth configuration (falls back to platform default)
   */
  async deleteOAuthConfig(provider: string, organizationId: string): Promise<{
    success: boolean
    message: string
  }> {
    try {
      return await fetchAuthAPI(`/api/settings/oauth/${provider}?organization_id=${organizationId}`, {
        method: 'DELETE',
      })
    } catch (error) {
      log('Error deleting OAuth config:', error)
      throw new Error(`Failed to delete OAuth config: ${error}`)
    }
  },

  /**
   * Get the redirect URI for configuring OAuth app
   */
  async getOAuthRedirectUri(provider: string, baseUrl?: string): Promise<{
    provider: string
    redirect_uri: string
    instructions: string
  }> {
    try {
      const params = baseUrl ? `?base_url=${encodeURIComponent(baseUrl)}` : ''
      return await fetchAuthAPI(`/api/settings/oauth/${provider}/redirect-uri${params}`)
    } catch (error) {
      log('Error fetching OAuth redirect URI:', error)
      throw new Error(`Failed to fetch OAuth redirect URI: ${error}`)
    }
  },

  // -------------------------------------------------------------------------
  // Webhook Management
  // -------------------------------------------------------------------------

  /**
   * List webhook events with optional filtering
   */
  async getWebhookEvents(filters?: {
    provider?: string
    status?: string
    limit?: number
  }): Promise<{
    events: Array<{
      event_id: string
      provider: string
      event_type: string
      payload: Record<string, unknown>
      status: string
      received_at: string
      processed_at?: string
      error_message?: string
      retry_count: number
    }>
    total: number
  }> {
    try {
      const params = new URLSearchParams()
      if (filters?.provider) params.append('provider', filters.provider)
      if (filters?.status) params.append('status', filters.status)
      if (filters?.limit) params.append('limit', String(filters.limit))

      return await fetchAPI(`/api/webhooks/events?${params.toString()}`)
    } catch (error) {
      log('Error fetching webhook events:', error)
      throw new Error(`Failed to fetch webhook events: ${error}`)
    }
  },

  /**
   * Get a specific webhook event
   */
  async getWebhookEvent(eventId: string): Promise<{
    event_id: string
    provider: string
    event_type: string
    payload: Record<string, unknown>
    status: string
    received_at: string
    processed_at?: string
    error_message?: string
    retry_count: number
  }> {
    try {
      return await fetchAPI(`/api/webhooks/events/${eventId}`)
    } catch (error) {
      log('Error fetching webhook event:', error)
      throw new Error(`Failed to fetch webhook event: ${error}`)
    }
  },

  /**
   * Retry a failed webhook event
   */
  async retryWebhookEvent(eventId: string): Promise<{
    success: boolean
    event_id: string
    status: string
  }> {
    try {
      return await fetchAPI(`/api/webhooks/events/${eventId}/retry`, {
        method: 'POST',
      })
    } catch (error) {
      log('Error retrying webhook event:', error)
      throw new Error(`Failed to retry webhook event: ${error}`)
    }
  },

  /**
   * List webhook configurations
   */
  async getWebhookConfigs(): Promise<Array<{
    provider: string
    enabled: boolean
    has_secret: boolean
    signature_header: string
    event_types: string[]
  }>> {
    try {
      return await fetchAPI('/api/webhooks/config')
    } catch (error) {
      log('Error fetching webhook configs:', error)
      throw new Error(`Failed to fetch webhook configs: ${error}`)
    }
  },

  /**
   * Configure webhook for a provider
   */
  async configureWebhook(
    provider: string,
    config: {
      secret_key?: string
      enabled: boolean
      event_types?: string[]
    }
  ): Promise<{
    provider: string
    enabled: boolean
    has_secret: boolean
    signature_header: string
    event_types: string[]
  }> {
    try {
      return await fetchAPI(`/api/webhooks/config/${provider}`, {
        method: 'POST',
        body: JSON.stringify(config),
      })
    } catch (error) {
      log('Error configuring webhook:', error)
      throw new Error(`Failed to configure webhook: ${error}`)
    }
  },

  /**
   * List webhook handlers
   */
  async getWebhookHandlers(): Promise<{
    handlers: Array<{
      event_type: string
      handler_type: string
      handler_config: Record<string, unknown>
      enabled: boolean
    }>
    total: number
  }> {
    try {
      return await fetchAPI('/api/webhooks/handlers')
    } catch (error) {
      log('Error fetching webhook handlers:', error)
      throw new Error(`Failed to fetch webhook handlers: ${error}`)
    }
  },

  /**
   * Register a webhook handler
   */
  async registerWebhookHandler(handler: {
    event_type: string
    handler_type: string
    handler_config: Record<string, unknown>
    enabled: boolean
  }): Promise<{
    success: boolean
    message: string
    event_type: string
    handler_type: string
  }> {
    try {
      return await fetchAPI('/api/webhooks/handlers', {
        method: 'POST',
        body: JSON.stringify(handler),
      })
    } catch (error) {
      log('Error registering webhook handler:', error)
      throw new Error(`Failed to register webhook handler: ${error}`)
    }
  },

  /**
   * Unregister a webhook handler
   */
  async unregisterWebhookHandler(eventType: string, handlerType?: string): Promise<{
    success: boolean
    message: string
  }> {
    try {
      const params = handlerType ? `?handler_type=${handlerType}` : ''
      return await fetchAPI(`/api/webhooks/handlers/${encodeURIComponent(eventType)}${params}`, {
        method: 'DELETE',
      })
    } catch (error) {
      log('Error unregister webhook handler:', error)
      throw new Error(`Failed to unregister webhook handler: ${error}`)
    }
  },

  // ============================================================================
  // Prompt Registry API
  // ============================================================================

  /**
   * List all prompt templates
   */
  async listPromptTemplates(params?: {
    category?: string
    is_active?: boolean
    limit?: number
    offset?: number
  }): Promise<PromptTemplate[]> {
    try {
      const queryParams = new URLSearchParams()
      if (params?.category) queryParams.append('category', params.category)
      if (params?.is_active !== undefined) queryParams.append('is_active', String(params.is_active))
      if (params?.limit) queryParams.append('limit', String(params.limit))
      if (params?.offset) queryParams.append('offset', String(params.offset))

      const query = queryParams.toString()
      return await fetchAPI(`/api/prompts${query ? `?${query}` : ''}`)
    } catch (error) {
      log('Error listing prompt templates:', error)
      throw new Error(`Failed to list prompt templates: ${error}`)
    }
  },

  /**
   * Get a specific prompt template by slug
   */
  async getPromptTemplate(slug: string): Promise<PromptTemplate> {
    try {
      return await fetchAPI(`/api/prompts/${slug}`)
    } catch (error) {
      log('Error getting prompt template:', error)
      throw new Error(`Failed to get prompt template: ${error}`)
    }
  },

  /**
   * Create a new prompt template
   */
  async createPromptTemplate(data: CreateTemplateRequest): Promise<PromptTemplate> {
    try {
      return await fetchAPI('/api/prompts', {
        method: 'POST',
        body: JSON.stringify(data),
      })
    } catch (error) {
      log('Error creating prompt template:', error)
      throw new Error(`Failed to create prompt template: ${error}`)
    }
  },

  /**
   * Update a prompt template
   */
  async updatePromptTemplate(slug: string, data: UpdateTemplateRequest): Promise<PromptTemplate> {
    try {
      return await fetchAPI(`/api/prompts/${slug}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      })
    } catch (error) {
      log('Error updating prompt template:', error)
      throw new Error(`Failed to update prompt template: ${error}`)
    }
  },

  /**
   * Delete a prompt template
   */
  async deletePromptTemplate(slug: string): Promise<void> {
    try {
      await fetchAPI(`/api/prompts/${slug}`, {
        method: 'DELETE',
      })
    } catch (error) {
      log('Error deleting prompt template:', error)
      throw new Error(`Failed to delete prompt template: ${error}`)
    }
  },

  /**
   * List all versions for a template
   */
  async listPromptVersions(slug: string): Promise<PromptVersion[]> {
    try {
      return await fetchAPI(`/api/prompts/${slug}/versions`)
    } catch (error) {
      log('Error listing prompt versions:', error)
      throw new Error(`Failed to list prompt versions: ${error}`)
    }
  },

  /**
   * Get a specific version
   */
  async getPromptVersion(slug: string, version: string): Promise<PromptVersion> {
    try {
      return await fetchAPI(`/api/prompts/${slug}/versions/${version}`)
    } catch (error) {
      log('Error getting prompt version:', error)
      throw new Error(`Failed to get prompt version: ${error}`)
    }
  },

  /**
   * Create a new version for a template
   */
  async createPromptVersion(slug: string, data: CreateVersionRequest): Promise<PromptVersion> {
    try {
      return await fetchAPI(`/api/prompts/${slug}/versions`, {
        method: 'POST',
        body: JSON.stringify(data),
      })
    } catch (error) {
      log('Error creating prompt version:', error)
      throw new Error(`Failed to create prompt version: ${error}`)
    }
  },

  /**
   * Publish a version (sets as default)
   */
  async publishPromptVersion(slug: string, version: string): Promise<PromptVersion> {
    try {
      return await fetchAPI(`/api/prompts/${slug}/versions/${version}/publish`, {
        method: 'PUT',
      })
    } catch (error) {
      log('Error publishing prompt version:', error)
      throw new Error(`Failed to publish prompt version: ${error}`)
    }
  },

  /**
   * Render a prompt with variables
   */
  async renderPrompt(slug: string, data: RenderPromptRequest): Promise<RenderPromptResponse> {
    try {
      return await fetchAPI(`/api/prompts/${slug}/render`, {
        method: 'POST',
        body: JSON.stringify(data),
      })
    } catch (error) {
      log('Error rendering prompt:', error)
      throw new Error(`Failed to render prompt: ${error}`)
    }
  },

  /**
   * Get usage statistics for a version
   */
  async getPromptUsageStats(slug: string, version: string, days = 30): Promise<PromptUsageStats[]> {
    try {
      return await fetchAPI(`/api/prompts/${slug}/versions/${version}/stats?days=${days}`)
    } catch (error) {
      log('Error getting prompt usage stats:', error)
      throw new Error(`Failed to get prompt usage stats: ${error}`)
    }
  },
  // -------------------------------------------------------------------------
  // HIPAA Compliance
  // -------------------------------------------------------------------------
  async getHIPAAStatus(): Promise<{
    hipaa_compliant: boolean
    role: string
    safeguards: Record<string, unknown>
    compliance_controls: Array<{ control: string; status: string; description: string }>
    baa_requirements: Record<string, unknown>
    generated_at: string
  }> {
    try {
      return await fetchAPI('/api/v1/hipaa/status')
    } catch (error) {
      log('Error fetching HIPAA status:', error)
      throw new Error(`Failed to fetch HIPAA status: ${error}`)
    }
  },

  async getPHIAuditSummary(days = 30): Promise<{
    period_days: number
    total_phi_events: number
    by_action: Record<string, number>
    by_resource: Record<string, number>
    by_user: Record<string, number>
    recent_events: Array<Record<string, unknown>>
    generated_at: string
  }> {
    try {
      return await fetchAPI(`/api/v1/hipaa/phi-audit?days=${days}`)
    } catch (error) {
      log('Error fetching PHI audit summary:', error)
      throw new Error(`Failed to fetch PHI audit summary: ${error}`)
    }
  },
}

export default api
