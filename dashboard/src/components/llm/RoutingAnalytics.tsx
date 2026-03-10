/**
 * RoutingAnalytics - Display routing decisions and performance metrics
 *
 * Shows:
 * - Cost savings from smart routing
 * - Latency statistics
 * - Provider usage distribution
 * - Request routing breakdown
 */

import { TrendingUp, Clock, DollarSign, BarChart3 } from 'lucide-react'
import type { RoutingAnalytics as RoutingAnalyticsType } from '@/types/llm'

interface RoutingAnalyticsProps {
  analytics: RoutingAnalyticsType
}

export function RoutingAnalytics({ analytics }: RoutingAnalyticsProps) {
  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="rounded-lg p-4" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
          <div className="flex items-center gap-2 mb-2" style={{ color: 'var(--text-secondary)' }}>
            <BarChart3 className="h-4 w-4" />
            <span className="text-sm">Total Requests</span>
          </div>
          <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            {analytics.totalRequests.toLocaleString()}
          </p>
        </div>

        <div className="rounded-lg p-4" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
          <div className="flex items-center gap-2 mb-2" style={{ color: 'var(--green)' }}>
            <DollarSign className="h-4 w-4" />
            <span className="text-sm">Cost Saved</span>
          </div>
          <p className="text-2xl font-bold" style={{ color: 'var(--green)' }}>
            ${analytics.costSavings.total.toFixed(2)}
          </p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
            {analytics.costSavings.percentageSaved.toFixed(1)}% reduction
          </p>
        </div>

        <div className="rounded-lg p-4" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
          <div className="flex items-center gap-2 mb-2" style={{ color: 'var(--accent)' }}>
            <Clock className="h-4 w-4" />
            <span className="text-sm">Avg Latency</span>
          </div>
          <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            {analytics.latencyStats.avgMs}ms
          </p>
          <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
            P95: {analytics.latencyStats.p95Ms}ms
          </p>
        </div>

        <div className="rounded-lg p-4" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
          <div className="flex items-center gap-2 mb-2" style={{ color: 'var(--info)' }}>
            <TrendingUp className="h-4 w-4" />
            <span className="text-sm">P99 Latency</span>
          </div>
          <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
            {analytics.latencyStats.p99Ms}ms
          </p>
        </div>
      </div>

      {/* Routing Decisions Breakdown */}
      <div className="rounded-lg p-6" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
        <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
          Routing Decisions
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Primary', value: analytics.routingDecisions.primary, color: 'var(--accent)' },
            { label: 'Backup', value: analytics.routingDecisions.backup, color: 'var(--yellow)' },
            { label: 'Cost Optimized', value: analytics.routingDecisions.costOptimized, color: 'var(--green)' },
            { label: 'Latency Optimized', value: analytics.routingDecisions.latencyOptimized, color: 'var(--info)' },
          ].map((item) => {
            const percentage = ((item.value / analytics.totalRequests) * 100).toFixed(1)
            return (
              <div key={item.label} className="text-center">
                <p className="text-2xl font-bold" style={{ color: item.color }}>
                  {item.value.toLocaleString()}
                </p>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{item.label}</p>
                <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{percentage}%</p>
              </div>
            )
          })}
        </div>
      </div>

      {/* Provider Usage */}
      <div className="rounded-lg p-6" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
        <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
          Provider Usage Distribution
        </h3>
        <div className="space-y-3">
          {analytics.providerUsage.map((provider) => (
            <div key={provider.provider}>
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium" style={{ color: 'var(--text-secondary)' }}>
                  {provider.provider}
                </span>
                <span className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
                  {provider.requests.toLocaleString()} ({provider.percentage.toFixed(1)}%)
                </span>
              </div>
              <div className="w-full rounded-full h-2" style={{ background: 'var(--bg-tertiary)' }}>
                <div
                  className="h-2 rounded-full transition-all duration-500"
                  style={{ width: `${provider.percentage}%`, background: 'var(--accent)' }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Latency Distribution */}
      <div className="rounded-lg p-6" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
        <h3 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
          Latency Percentiles
        </h3>
        <div className="flex items-end gap-4 h-32">
          {[
            { label: 'P50', value: analytics.latencyStats.p50Ms, color: 'var(--green)' },
            { label: 'Avg', value: analytics.latencyStats.avgMs, color: 'var(--accent)' },
            { label: 'P95', value: analytics.latencyStats.p95Ms, color: 'var(--yellow)' },
            { label: 'P99', value: analytics.latencyStats.p99Ms, color: 'var(--error)' },
          ].map((stat) => {
            const maxLatency = analytics.latencyStats.p99Ms
            const heightPercent = (stat.value / maxLatency) * 100
            return (
              <div key={stat.label} className="flex-1 flex flex-col items-center">
                <div
                  className="w-full rounded-t transition-all duration-500"
                  style={{ height: `${heightPercent}%`, minHeight: '8px', background: stat.color }}
                />
                <div className="mt-2 text-center">
                  <p className="text-xs font-medium" style={{ color: 'var(--text-secondary)' }}>{stat.label}</p>
                  <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{stat.value}ms</p>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export default RoutingAnalytics
