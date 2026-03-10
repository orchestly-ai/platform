/**
 * LLMSettings Page - Unified LLM Routing Dashboard
 *
 * CONSOLIDATED: Combines health monitoring + strategy configuration
 *
 * Tabs:
 * 1. Health & Monitoring - Provider health cards, circuit breakers, status
 * 2. Strategy Configuration - Detailed routing strategy setup (org/workflow/agent)
 * 3. Analytics - Routing decisions, cost savings, latency metrics
 *
 * Verification:
 * - Navigate to /llm-settings
 * - Switch between tabs to see all functionality
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { Activity, RefreshCw, Settings2, Database, TrendingUp, Zap } from 'lucide-react'
import { ProviderHealthCard } from '@/components/llm/ProviderHealthCard'
import { RoutingStrategySelector } from '@/components/llm/RoutingStrategySelector'
import { RoutingAnalytics } from '@/components/llm/RoutingAnalytics'
import { ModelRouterSettings } from '@/components/settings/ModelRouterSettings'
import type { RoutingStrategy } from '@/types/llm'
import { useState } from 'react'

type LLMTab = 'health' | 'strategy' | 'analytics'

export function LLMSettingsPage() {
  const queryClient = useQueryClient()
  const [isResetting, setIsResetting] = useState(false)
  const [activeTab, setActiveTab] = useState<LLMTab>('health')

  const { data: providers, isLoading: providersLoading } = useQuery({
    queryKey: ['llmProviders'],
    queryFn: async () => {
      const result = await api.getLLMProviders()
      return result
    },
    refetchInterval: 30000, // Refresh every 30s
  })

  const handleResetProviders = async () => {
    if (!confirm('This will reset all LLM providers to defaults. Continue?')) return
    setIsResetting(true)
    try {
      await api.resetLLMProviders()
      queryClient.invalidateQueries({ queryKey: ['llmProviders'] })
    } catch (error) {
      console.error('Failed to reset providers:', error)
      alert('Failed to reset providers. Check console for details.')
    } finally {
      setIsResetting(false)
    }
  }

  const { data: currentStrategy, isLoading: strategyLoading } = useQuery({
    queryKey: ['routingStrategy'],
    queryFn: () => api.getRoutingStrategy(),
  })

  const { data: analytics, isLoading: analyticsLoading } = useQuery({
    queryKey: ['routingAnalytics'],
    queryFn: () => api.getRoutingAnalytics(),
    refetchInterval: 60000, // Refresh every minute
  })

  const saveStrategyMutation = useMutation({
    mutationFn: (strategy: RoutingStrategy) => api.setRoutingStrategy(strategy),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['routingStrategy'] })
    },
  })

  const isLoading = providersLoading || strategyLoading || analyticsLoading

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Activity className="h-12 w-12 mx-auto mb-3 animate-pulse" style={{ color: 'var(--accent)' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Loading LLM settings...</p>
        </div>
      </div>
    )
  }

  const healthyProviders = providers?.filter(p => p.status === 'healthy').length || 0
  const totalProviders = providers?.length || 0

  const tabs = [
    { id: 'health' as const, label: 'Health & Monitoring', icon: Activity },
    { id: 'strategy' as const, label: 'Strategy Configuration', icon: Zap },
    { id: 'analytics' as const, label: 'Analytics', icon: TrendingUp },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
            <Settings2 className="h-7 w-7" style={{ color: 'var(--accent)' }} />
            LLM Routing Dashboard
          </h1>
          <p style={{ color: 'var(--text-secondary)' }} className="mt-1">
            Monitor health, configure strategies, and analyze routing performance
          </p>
        </div>
        <button
          onClick={() => {
            queryClient.invalidateQueries({ queryKey: ['llmProviders'] })
            queryClient.invalidateQueries({ queryKey: ['routingAnalytics'] })
          }}
          className="flex items-center gap-2 px-4 py-2 text-sm rounded-lg transition-colors"
          style={{ color: 'var(--text-secondary)', background: 'transparent' }}
          onMouseEnter={e => { e.currentTarget.style.background = 'var(--bg-hover)'; e.currentTarget.style.color = 'var(--text-primary)' }}
          onMouseLeave={e => { e.currentTarget.style.background = 'transparent'; e.currentTarget.style.color = 'var(--text-secondary)' }}
        >
          <RefreshCw className="h-4 w-4" />
          Refresh
        </button>
      </div>

      {/* Tab Navigation */}
      <div style={{ borderBottom: '2px solid var(--border-color)' }}>
        <div style={{ display: 'flex', gap: '8px' }}>
          {tabs.map((tab) => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '12px 20px',
                  border: 'none',
                  background: 'transparent',
                  color: activeTab === tab.id ? 'var(--primary-color)' : 'var(--text-secondary)',
                  borderBottom: activeTab === tab.id ? '2px solid var(--primary-color)' : '2px solid transparent',
                  fontSize: '14px',
                  fontWeight: activeTab === tab.id ? 600 : 500,
                  cursor: 'pointer',
                  marginBottom: '-2px',
                }}
              >
                <Icon size={18} />
                {tab.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'health' && (
        <>
          {/* Provider Management */}
          <div className="rounded-lg p-3 flex items-center justify-between" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4" style={{ color: 'var(--accent)' }} />
              <span className="text-sm font-medium" style={{ color: 'var(--text-primary)' }}>
                LLM Provider Management
              </span>
            </div>
            <button
              onClick={handleResetProviders}
              disabled={isResetting}
              className="text-xs px-3 py-1 rounded disabled:opacity-50"
              style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-primary)' }}
            >
              {isResetting ? 'Resetting...' : 'Reset Providers'}
            </button>
          </div>

          {/* Provider Status Summary */}
          <div className="rounded-lg p-4" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold" style={{ color: 'var(--text-primary)' }}>Provider Status</h2>
                <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>
                  {healthyProviders} of {totalProviders} providers healthy
                </p>
              </div>
              <div className="flex items-center gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full" style={{ background: 'var(--green)' }} />
                  <span style={{ color: 'var(--text-secondary)' }}>Healthy</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full" style={{ background: 'var(--yellow)' }} />
                  <span style={{ color: 'var(--text-secondary)' }}>Degraded</span>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 rounded-full" style={{ background: 'var(--error)' }} />
                  <span style={{ color: 'var(--text-secondary)' }}>Offline</span>
                </div>
              </div>
            </div>
          </div>

          {/* Provider Cards */}
          <div>
            <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>LLM Providers</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {providers?.map((provider) => (
                <ProviderHealthCard key={provider.id} provider={provider} />
              ))}
            </div>
          </div>

          {/* Basic Routing Strategy Selector */}
          {currentStrategy && (
            <RoutingStrategySelector
              currentStrategy={currentStrategy}
              onSave={async (strategy) => {
                await saveStrategyMutation.mutateAsync(strategy)
              }}
              isLoading={saveStrategyMutation.isPending}
            />
          )}
        </>
      )}

      {/* Strategy Configuration Tab */}
      {activeTab === 'strategy' && (
        <div>
          <ModelRouterSettings />
        </div>
      )}

      {/* Analytics Tab */}
      {activeTab === 'analytics' && analytics && (
        <div>
          <h2 className="text-lg font-semibold mb-4" style={{ color: 'var(--text-primary)' }}>
            Routing Analytics
          </h2>
          <RoutingAnalytics analytics={analytics} />
        </div>
      )}
    </div>
  )
}

export default LLMSettingsPage
