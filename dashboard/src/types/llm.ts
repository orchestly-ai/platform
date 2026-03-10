/**
 * Types for LLM Settings, Routing, Cost Management, and Advanced Features
 */

// LLM Provider Types
export type ProviderStatus = 'healthy' | 'degraded' | 'offline'
export type CircuitBreakerState = 'CLOSED' | 'OPEN' | 'HALF_OPEN'
export type RoutingStrategy =
  | 'PRIMARY_ONLY'
  | 'PRIMARY_WITH_BACKUP'
  | 'BEST_AVAILABLE'
  | 'COST_OPTIMIZED'
  | 'LATENCY_OPTIMIZED'

export interface LLMProvider {
  id: string
  name: string
  models: string[]
  status: ProviderStatus
  circuitBreakerState: CircuitBreakerState
  successRate: number
  avgLatencyMs: number
  failureCount: number
  lastFailure: string | null
  costPer1kTokens: number
}

export interface RoutingAnalytics {
  totalRequests: number
  routingDecisions: {
    primary: number
    backup: number
    costOptimized: number
    latencyOptimized: number
  }
  costSavings: {
    total: number
    percentageSaved: number
  }
  latencyStats: {
    avgMs: number
    p50Ms: number
    p95Ms: number
    p99Ms: number
  }
  providerUsage: {
    provider: string
    requests: number
    percentage: number
  }[]
  timeSeriesData: {
    timestamp: string
    requests: number
    avgLatency: number
    errorRate: number
  }[]
}

// Cost Management Types
export interface CostSummary {
  today: number
  yesterday: number
  thisWeek: number
  thisMonth: number
  lastMonth: number
  byProvider: Record<string, number>
  byModel: Record<string, number>
  trend: { date: string; cost: number }[]
}

export interface BudgetAlert {
  id: string
  name: string
  threshold: number
  current: number
  period: 'daily' | 'weekly' | 'monthly'
  status: 'ok' | 'warning' | 'exceeded'
  alertThresholdWarning: number
  alertThresholdCritical: number
  autoDisableOnExceeded: boolean
}

export interface CostForecast {
  next7Days: number
  next30Days: number
  next90Days: number
  confidence: number
  trend: 'increasing' | 'stable' | 'decreasing'
  projectedOverage: string | null
}

// Time-Travel Debugger Types
export interface ExecutionStep {
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
}

export interface TimeTravelExecution {
  id: string
  workflowId: string
  workflowName: string
  status: 'running' | 'completed' | 'failed' | 'cancelled'
  startTime: string
  endTime?: string
  stateCount: number
  totalCost: number
  error?: string
  nodeExecutions?: ExecutionStep[]
  // Raw node_states from backend - contains full output with ab_testing metadata
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
}

export interface ExecutionState {
  id: string
  executionId: string
  stateIndex: number
  timestamp: string
  nodeId: string
  nodeName: string
  type: 'input' | 'output' | 'decision' | 'error'
  data: Record<string, unknown>
  metadata?: {
    latencyMs: number
    tokenCount: number
    cost: number
  }
}

export interface ExecutionDiff {
  field: string
  oldValue: unknown
  newValue: unknown
  changeType: 'added' | 'removed' | 'modified'
}

// Human-in-the-Loop Types
export type RiskLevel = 'low' | 'medium' | 'high' | 'critical'

export interface HITLApproval {
  id: string
  action: string
  riskLevel: RiskLevel
  requestedBy: string
  requestedAt: string
  context: Record<string, unknown>
  expiresAt: string
  decidedAt?: string
  decidedBy?: string
  decision?: 'approved' | 'rejected'
  comment?: string
}

export interface ApprovalPolicy {
  id: string
  name: string
  description: string
  triggerConditions: {
    riskLevel?: RiskLevel[]
    actionPatterns?: string[]
    autoApprove?: boolean
  }
  requiresComment: boolean
  escalationTimeoutMinutes: number
  notifyEmails: string[]
}

// A/B Testing Types
export interface ABExperiment {
  id: string
  name: string
  description?: string
  status: 'draft' | 'running' | 'paused' | 'completed'
  startDate: string
  endDate?: string
  variants: ABVariant[]
  significanceLevel: number
  winner: string | null
  metric?: string
  // Targeting info
  taskType?: string          // Raw task_type from backend (may be "workflow:{uuid}" or a category)
  targetWorkflowId?: string  // Extracted workflow ID (first one if multiple)
  targetWorkflowIds?: string[] // All workflow IDs if multiple are targeted
  targetWorkflowName?: string // Resolved workflow name for display (first one if multiple)
}

export interface ABVariant {
  name: string
  traffic: number
  conversions: number
  totalRequests: number
  conversionRate?: number
  avgLatency: number
  costPer1k: number
  config?: Record<string, unknown>
}

// Audit Log Types
export interface AuditLogEntry {
  id: string                  // Mapped from: event_id
  timestamp: string
  action: string
  user: string                // Mapped from: user_id or user_email
  resource?: string           // Mapped from: resource_type
  resourceId?: string         // Mapped from: resource_id
  details: Record<string, unknown>
  severity?: 'info' | 'warning' | 'error' | 'critical'
  ip: string                  // Mapped from: ip_address
  ipAddress?: string          // Alternative field name
  userAgent?: string          // Mapped from: user_agent
  before?: Record<string, unknown>
  after?: Record<string, unknown>
}

// Marketplace Types
export interface MarketplaceAgent {
  id: string
  name: string
  description: string
  category: string
  author: string
  version: string
  downloads: number
  rating: number
  ratingCount: number
  installed: boolean
  capabilities: string[]
  pricing: 'free' | 'premium'
  thumbnailUrl?: string
}

// Integration Types
export interface Integration {
  id: string
  name: string
  description: string
  category: string
  status: 'connected' | 'disconnected' | 'error'
  logoUrl?: string
  lastSync?: string
  config?: Record<string, unknown>
}
