/**
 * ProviderHealthCard - Displays LLM provider health status
 *
 * Shows:
 * - Provider name and status
 * - Success rate percentage
 * - Average latency
 * - Circuit breaker state
 * - Failure count
 */

import { AlertCircle, CheckCircle, Clock, XCircle } from 'lucide-react'
import type { LLMProvider, CircuitBreakerState, ProviderStatus } from '@/types/llm'

interface ProviderHealthCardProps {
  provider: LLMProvider
}

const statusConfig: Record<ProviderStatus, { color: string; icon: typeof CheckCircle; label: string }> = {
  healthy: { color: 'text-green-500', icon: CheckCircle, label: 'Healthy' },
  degraded: { color: 'text-yellow-500', icon: AlertCircle, label: 'Degraded' },
  offline: { color: 'text-red-500', icon: XCircle, label: 'Offline' },
}

const circuitBreakerConfig: Record<CircuitBreakerState, { color: string; bgColor: string }> = {
  CLOSED: { color: 'text-green-700', bgColor: 'bg-green-100' },
  HALF_OPEN: { color: 'text-yellow-700', bgColor: 'bg-yellow-100' },
  OPEN: { color: 'text-red-700', bgColor: 'bg-red-100' },
}

export function ProviderHealthCard({ provider }: ProviderHealthCardProps) {
  const status = statusConfig[provider.status]
  const StatusIcon = status.icon
  const cbConfig = circuitBreakerConfig[provider.circuitBreakerState]

  const successRateColor =
    provider.successRate >= 0.95
      ? 'text-green-600'
      : provider.successRate >= 0.9
      ? 'text-yellow-600'
      : 'text-red-600'

  const latencyColor =
    provider.avgLatencyMs < 1000
      ? 'text-green-600'
      : provider.avgLatencyMs < 2000
      ? 'text-yellow-600'
      : 'text-red-600'

  return (
    <div className="rounded-lg p-4 hover:shadow-md transition-shadow" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>{provider.name}</h3>
          <p className="text-xs mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
            {provider.models.length} model{provider.models.length !== 1 ? 's' : ''}
          </p>
        </div>
        <div className={`flex items-center gap-1 ${status.color}`}>
          <StatusIcon className="h-4 w-4" />
          <span className="text-xs font-medium">{status.label}</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 mb-3">
        <div>
          <p className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>Success Rate</p>
          <p className={`text-lg font-semibold ${successRateColor}`}>
            {(provider.successRate * 100).toFixed(1)}%
          </p>
        </div>
        <div>
          <p className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>Avg Latency</p>
          <p className={`text-lg font-semibold ${latencyColor}`}>
            {provider.avgLatencyMs > 0 ? `${provider.avgLatencyMs}ms` : '—'}
          </p>
        </div>
      </div>

      <div className="flex items-center justify-between pt-3" style={{ borderTop: '1px solid var(--border-primary)' }}>
        <div className="flex items-center gap-2">
          <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Circuit:</span>
          <span
            className={`text-xs font-medium px-2 py-0.5 rounded ${cbConfig.bgColor} ${cbConfig.color}`}
          >
            {provider.circuitBreakerState}
          </span>
        </div>
        {provider.failureCount > 0 && (
          <div className="flex items-center gap-1" style={{ color: 'var(--error)' }}>
            <AlertCircle className="h-3 w-3" />
            <span className="text-xs">{provider.failureCount} failures</span>
          </div>
        )}
      </div>

      {provider.lastFailure && (
        <div className="mt-2 flex items-center gap-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
          <Clock className="h-3 w-3" />
          <span>
            Last failure: {new Date(provider.lastFailure).toLocaleTimeString()}
          </span>
        </div>
      )}

      <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border-primary)' }}>
        <p className="text-xs mb-1" style={{ color: 'var(--text-tertiary)' }}>Available Models</p>
        <div className="flex flex-wrap gap-1">
          {provider.models.slice(0, 3).map((model) => (
            <span
              key={model}
              className="text-xs px-2 py-0.5 rounded"
              style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}
            >
              {model}
            </span>
          ))}
          {provider.models.length > 3 && (
            <span className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
              +{provider.models.length - 3} more
            </span>
          )}
        </div>
      </div>

      <div className="mt-3 text-xs" style={{ color: 'var(--text-tertiary)' }}>
        Cost: ${provider.costPer1kTokens.toFixed(3)}/1k tokens
      </div>
    </div>
  )
}

export default ProviderHealthCard
