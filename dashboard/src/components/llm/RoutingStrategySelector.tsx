/**
 * RoutingStrategySelector - Select and configure LLM routing strategy
 *
 * Strategies:
 * - PRIMARY_ONLY: Use only the primary provider
 * - PRIMARY_WITH_BACKUP: Try primary, fallback to backup on failure
 * - BEST_AVAILABLE: Route to the healthiest provider
 * - COST_OPTIMIZED: Choose the cheapest provider that meets requirements
 * - LATENCY_OPTIMIZED: Choose the fastest provider
 */

import { useState } from 'react'
import { Check, Loader2, Zap, DollarSign, Shield, Server, RefreshCw } from 'lucide-react'
import type { RoutingStrategy } from '@/types/llm'

interface RoutingStrategySelectorProps {
  currentStrategy: RoutingStrategy
  onSave: (strategy: RoutingStrategy) => Promise<void>
  isLoading?: boolean
}

interface StrategyOption {
  value: RoutingStrategy
  label: string
  description: string
  icon: typeof Server
  color: string
}

const strategies: StrategyOption[] = [
  {
    value: 'PRIMARY_ONLY',
    label: 'Primary Only',
    description: 'Always use the primary provider. No fallback.',
    icon: Server,
    color: 'blue',
  },
  {
    value: 'PRIMARY_WITH_BACKUP',
    label: 'Primary with Backup',
    description: 'Use primary provider, automatically failover to backup on errors.',
    icon: Shield,
    color: 'indigo',
  },
  {
    value: 'BEST_AVAILABLE',
    label: 'Best Available',
    description: 'Dynamically route to the healthiest provider based on success rates.',
    icon: RefreshCw,
    color: 'green',
  },
  {
    value: 'COST_OPTIMIZED',
    label: 'Cost Optimized',
    description: 'Route to the cheapest provider that meets quality thresholds.',
    icon: DollarSign,
    color: 'purple',
  },
  {
    value: 'LATENCY_OPTIMIZED',
    label: 'Latency Optimized',
    description: 'Route to the fastest responding provider for minimal delay.',
    icon: Zap,
    color: 'yellow',
  },
]

const colorClasses: Record<string, { bg: string; border: string; text: string; icon: string }> = {
  blue: { bg: 'bg-blue-50', border: 'border-blue-500', text: 'text-blue-400', icon: 'text-blue-400' },
  indigo: { bg: 'bg-indigo-50', border: 'border-indigo-500', text: 'text-indigo-400', icon: 'text-indigo-400' },
  green: { bg: 'bg-green-50', border: 'border-green-500', text: 'text-green-400', icon: 'text-green-400' },
  purple: { bg: 'bg-purple-50', border: 'border-purple-500', text: 'text-purple-400', icon: 'text-purple-400' },
  yellow: { bg: 'bg-yellow-50', border: 'border-yellow-500', text: 'text-yellow-400', icon: 'text-yellow-400' },
}

export function RoutingStrategySelector({
  currentStrategy,
  onSave,
  isLoading = false,
}: RoutingStrategySelectorProps) {
  const [selected, setSelected] = useState<RoutingStrategy>(currentStrategy)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  const hasChanges = selected !== currentStrategy

  const handleSave = async () => {
    if (!hasChanges || saving) return

    setSaving(true)
    try {
      await onSave(selected)
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="rounded-lg p-6" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Routing Strategy</h3>
          <p className="text-sm mt-1" style={{ color: 'var(--text-tertiary)' }}>
            Choose how requests are distributed across LLM providers
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={!hasChanges || saving || isLoading}
          className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-all"
          style={{
            background: hasChanges && !saving ? 'var(--accent)' : saved ? 'var(--green)' : 'var(--bg-tertiary)',
            color: hasChanges && !saving ? 'var(--bg-primary)' : saved ? 'var(--bg-primary)' : 'var(--text-tertiary)',
            cursor: hasChanges && !saving ? 'pointer' : saved ? 'default' : 'not-allowed',
          }}
        >
          {saving ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Saving...
            </>
          ) : saved ? (
            <>
              <Check className="h-4 w-4" />
              Saved!
            </>
          ) : (
            'Save Changes'
          )}
        </button>
      </div>

      <div className="space-y-3">
        {strategies.map((strategy) => {
          const isSelected = selected === strategy.value
          const colors = colorClasses[strategy.color]
          const Icon = strategy.icon

          return (
            <button
              key={strategy.value}
              onClick={() => setSelected(strategy.value)}
              disabled={isLoading}
              className={`w-full text-left p-4 rounded-lg border-2 transition-all ${
                isSelected
                  ? `${colors.border}`
                  : ''
              }`}
              style={isSelected ? { background: 'var(--bg-tertiary)' } : { borderColor: 'var(--border-primary)', background: 'transparent' }}
            >
              <div className="flex items-start gap-3">
                <div
                  className="p-2 rounded-lg"
                  style={{ background: 'var(--bg-tertiary)' }}
                >
                  <Icon
                    className={`h-5 w-5 ${isSelected ? colors.icon : ''}`}
                    style={isSelected ? {} : { color: 'var(--text-tertiary)' }}
                  />
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span
                      className={`font-medium ${isSelected ? colors.text : ''}`}
                      style={isSelected ? {} : { color: 'var(--text-primary)' }}
                    >
                      {strategy.label}
                    </span>
                    {isSelected && (
                      <Check className={`h-4 w-4 ${colors.icon}`} />
                    )}
                  </div>
                  <p className="text-sm mt-0.5" style={{ color: 'var(--text-tertiary)' }}>
                    {strategy.description}
                  </p>
                </div>
              </div>
            </button>
          )
        })}
      </div>

      {currentStrategy !== selected && (
        <div className="mt-4 p-3 rounded-lg" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
          <p className="text-sm" style={{ color: 'var(--accent)' }}>
            <span className="font-medium">Pending change:</span> From{' '}
            <span className="font-mono px-1 rounded" style={{ background: 'var(--bg-secondary)' }}>
              {currentStrategy}
            </span>{' '}
            to{' '}
            <span className="font-mono px-1 rounded" style={{ background: 'var(--bg-secondary)' }}>{selected}</span>
          </p>
        </div>
      )}
    </div>
  )
}

export default RoutingStrategySelector
