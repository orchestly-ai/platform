/**
 * Model Router Settings - Strategy Configuration UI
 *
 * Allows configuring routing strategies at different scopes:
 * - Organization level (default)
 * - Workflow level (override)
 * - Agent level (override)
 */

import { useState, useEffect } from 'react';
import {
  Settings2,
  ChevronDown,
  Info,
  Zap,
  DollarSign,
  Target,
  TrendingUp,
  Clock,
  CheckCircle,
  Loader2,
  Save,
  TestTube,
  AlertTriangle,
} from 'lucide-react';
import { api } from '@/services/api';

// Strategy types
type StrategyType =
  | 'cost_optimized'
  | 'latency_optimized'
  | 'quality_first'
  | 'weighted_roundrobin'
  | 'custom';

type ScopeType = 'organization' | 'workflow' | 'agent';

interface ModelPreference {
  id: string;
  name: string;
  cost: number;
  quality: number;
  enabled: boolean;
  weight?: number;
}

interface StrategyConfig {
  scope: ScopeType;
  scopeId?: string; // workflow ID or agent ID
  strategyType: StrategyType;
  minQualityScore?: number;
  maxLatency?: number;
  maxCostPerRequest?: number;
  fallbackStrategy?: StrategyType;
  modelPreferences: ModelPreference[];
  customConfig?: string; // JSON for custom strategy
}

// Available models with metadata
const AVAILABLE_MODELS: ModelPreference[] = [
  { id: 'gpt-4o-mini', name: 'GPT-4o Mini', cost: 0.15, quality: 0.75, enabled: true },
  { id: 'claude-3-haiku', name: 'Claude 3 Haiku', cost: 0.25, quality: 0.78, enabled: true },
  { id: 'gpt-4o', name: 'GPT-4o', cost: 2.50, quality: 0.95, enabled: false },
  { id: 'claude-3-sonnet', name: 'Claude 3 Sonnet', cost: 3.00, quality: 0.92, enabled: true },
  { id: 'claude-3-opus', name: 'Claude 3 Opus', cost: 15.00, quality: 0.98, enabled: false },
  { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', cost: 10.00, quality: 0.94, enabled: false },
];

// Workflow options (mock data - would come from API)
const WORKFLOWS = [
  { id: 'customer-support', name: 'Customer Support' },
  { id: 'data-analysis', name: 'Data Analysis' },
  { id: 'content-generation', name: 'Content Generation' },
];

export function ModelRouterSettings() {
  const [config, setConfig] = useState<StrategyConfig>({
    scope: 'organization',
    strategyType: 'cost_optimized',
    minQualityScore: 0.7,
    maxLatency: 5000,
    maxCostPerRequest: 1.0,
    fallbackStrategy: 'latency_optimized',
    modelPreferences: AVAILABLE_MODELS,
  });

  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Load configuration on mount
  useEffect(() => {
    loadConfiguration();
  }, [config.scope, config.scopeId]);

  // Auto-hide toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  const loadConfiguration = async () => {
    setLoading(true);
    try {
      const data = await api.getRouterConfig(config.scope, config.scopeId);
      if (data && data.strategyType) {
        setConfig({
          ...config,
          ...data,
          modelPreferences: data.modelPreferences?.length > 0 ? data.modelPreferences : AVAILABLE_MODELS,
        });
      }
    } catch (error) {
      console.error('Error loading configuration:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleSaveConfiguration = async () => {
    setSaving(true);
    try {
      await api.saveRouterConfig(config);
      setToast({ message: 'Configuration saved successfully', type: 'success' });
    } catch (error) {
      console.error('Error saving configuration:', error);
      setToast({ message: 'Failed to save configuration', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleTestRouting = async () => {
    setTesting(true);
    try {
      const result = await api.testRouting(config);
      setToast({
        message: `Test complete: Would route to ${result.selectedModel} (cost: $${result.estimatedCost.toFixed(2)}/1K, latency: ${result.estimatedLatency}ms)`,
        type: 'success'
      });
    } catch (error) {
      console.error('Error testing routing:', error);
      setToast({ message: 'Failed to test routing', type: 'error' });
    } finally {
      setTesting(false);
    }
  };

  const updateModelPreference = (modelId: string, enabled: boolean) => {
    setConfig({
      ...config,
      modelPreferences: config.modelPreferences.map(m =>
        m.id === modelId ? { ...m, enabled } : m
      ),
    });
  };

  const updateModelWeight = (modelId: string, weight: number) => {
    setConfig({
      ...config,
      modelPreferences: config.modelPreferences.map(m =>
        m.id === modelId ? { ...m, weight } : m
      ),
    });
  };

  const getStrategyIcon = (strategy: StrategyType) => {
    switch (strategy) {
      case 'cost_optimized': return DollarSign;
      case 'latency_optimized': return Clock;
      case 'quality_first': return Target;
      case 'weighted_roundrobin': return TrendingUp;
      case 'custom': return Settings2;
    }
  };

  const renderStrategyForm = () => {
    const { strategyType } = config;

    switch (strategyType) {
      case 'cost_optimized':
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                Min Quality Score
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={(config.minQualityScore || 0.7) * 100}
                  onChange={(e) => setConfig({ ...config, minQualityScore: parseInt(e.target.value) / 100 })}
                  style={{ flex: 1 }}
                />
                <span style={{ fontSize: '14px', fontWeight: 600, minWidth: '50px' }}>
                  {Math.round((config.minQualityScore || 0.7) * 100)}%
                </span>
              </div>
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                Max Latency (ms)
              </label>
              <input
                type="number"
                value={config.maxLatency || 5000}
                onChange={(e) => setConfig({ ...config, maxLatency: parseInt(e.target.value) })}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  fontSize: '14px'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                Fallback Strategy
              </label>
              <select
                value={config.fallbackStrategy || 'latency_optimized'}
                onChange={(e) => setConfig({ ...config, fallbackStrategy: e.target.value as StrategyType })}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  fontSize: '14px'
                }}
              >
                <option value="latency_optimized">Latency Optimized</option>
                <option value="quality_first">Quality First</option>
                <option value="weighted_roundrobin">Weighted Round-Robin</option>
              </select>
            </div>
          </div>
        );

      case 'latency_optimized':
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                Max P95 Latency (ms)
              </label>
              <input
                type="number"
                value={config.maxLatency || 2000}
                onChange={(e) => setConfig({ ...config, maxLatency: parseInt(e.target.value) })}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  fontSize: '14px'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                Fallback if all models slow
              </label>
              <select
                value={config.fallbackStrategy || 'cost_optimized'}
                onChange={(e) => setConfig({ ...config, fallbackStrategy: e.target.value as StrategyType })}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  fontSize: '14px'
                }}
              >
                <option value="cost_optimized">Cost Optimized</option>
                <option value="quality_first">Quality First</option>
                <option value="weighted_roundrobin">Weighted Round-Robin</option>
              </select>
            </div>
          </div>
        );

      case 'quality_first':
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                Max Cost per 1K Tokens ($)
              </label>
              <input
                type="number"
                step="0.01"
                value={config.maxCostPerRequest || 5.0}
                onChange={(e) => setConfig({ ...config, maxCostPerRequest: parseFloat(e.target.value) })}
                style={{
                  width: '100%',
                  padding: '10px 14px',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  fontSize: '14px'
                }}
              />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                Min Quality Score
              </label>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <input
                  type="range"
                  min="0"
                  max="100"
                  value={(config.minQualityScore || 0.9) * 100}
                  onChange={(e) => setConfig({ ...config, minQualityScore: parseInt(e.target.value) / 100 })}
                  style={{ flex: 1 }}
                />
                <span style={{ fontSize: '14px', fontWeight: 600, minWidth: '50px' }}>
                  {Math.round((config.minQualityScore || 0.9) * 100)}%
                </span>
              </div>
            </div>
          </div>
        );

      case 'weighted_roundrobin':
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
            <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-secondary)' }}>
              Distribute requests across models based on weight. Higher weights receive more traffic.
            </p>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {config.modelPreferences.filter(m => m.enabled).map((model) => (
                <div key={model.id} style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <span style={{ fontSize: '14px', fontWeight: 500, minWidth: '150px' }}>
                    {model.name}
                  </span>
                  <input
                    type="range"
                    min="1"
                    max="10"
                    value={model.weight || 5}
                    onChange={(e) => updateModelWeight(model.id, parseInt(e.target.value))}
                    style={{ flex: 1 }}
                  />
                  <span style={{ fontSize: '14px', fontWeight: 600, minWidth: '30px' }}>
                    {model.weight || 5}
                  </span>
                </div>
              ))}
            </div>
          </div>
        );

      case 'custom':
        return (
          <div>
            <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
              Custom Configuration (JSON)
            </label>
            <textarea
              value={config.customConfig || '{\n  "strategy": "custom",\n  "rules": []\n}'}
              onChange={(e) => setConfig({ ...config, customConfig: e.target.value })}
              rows={10}
              style={{
                width: '100%',
                padding: '12px',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                fontSize: '13px',
                fontFamily: 'monospace',
                resize: 'vertical'
              }}
            />
          </div>
        );
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
      {/* Toast Notification */}
      {toast && (
        <div style={{
          position: 'fixed',
          bottom: '24px',
          right: '24px',
          padding: '12px 20px',
          borderRadius: '8px',
          background: toast.type === 'success' ? '#10b981' : '#ef4444',
          color: 'white',
          display: 'flex',
          alignItems: 'center',
          gap: '8px',
          zIndex: 1001,
          boxShadow: '0 4px 12px rgba(0,0,0,0.15)',
        }}>
          {toast.type === 'success' ? <CheckCircle size={18} /> : <AlertTriangle size={18} />}
          {toast.message}
        </div>
      )}

      {/* Header */}
      <div>
        <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Settings2 size={20} />
          Model Router Configuration
        </h2>
        <p style={{ color: 'var(--text-secondary)', margin: '8px 0 0', fontSize: '14px' }}>
          Configure routing strategies at different scopes to optimize cost, latency, and quality
        </p>
      </div>

      {/* Scope Hierarchy Visualization */}
      <div className="chart-card" style={{ padding: '16px', background: 'rgba(99, 102, 241, 0.05)' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
          <Info size={16} style={{ color: 'var(--primary-color)' }} />
          <strong style={{ fontSize: '14px', color: 'var(--primary-color)' }}>Scope Hierarchy</strong>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '13px' }}>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontWeight: 500, marginBottom: '4px' }}>Organization Default</div>
            <div style={{ padding: '6px 12px', background: 'var(--bg-primary)', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
              Cost Optimized
            </div>
            <div style={{ marginTop: '4px', color: 'var(--text-muted)', fontSize: '12px' }}>
              Used if no override
            </div>
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '20px' }}>→</div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontWeight: 500, marginBottom: '4px' }}>Workflow Override</div>
            <div style={{ padding: '6px 12px', background: 'var(--bg-primary)', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
              Latency
            </div>
            <div style={{ marginTop: '4px', color: 'var(--text-muted)', fontSize: '12px' }}>
              Used for this workflow
            </div>
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '20px' }}>→</div>
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontWeight: 500, marginBottom: '4px' }}>Agent Override</div>
            <div style={{ padding: '6px 12px', background: 'var(--bg-primary)', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
              Quality
            </div>
            <div style={{ marginTop: '4px', color: 'var(--text-muted)', fontSize: '12px' }}>
              Used for this agent
            </div>
          </div>
        </div>
      </div>

      {/* Main Configuration Card */}
      <div className="chart-card">
        {/* Scope Selector */}
        <div style={{ marginBottom: '24px' }}>
          <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '12px' }}>
            Configuration Scope
          </label>
          <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
            <select
              value={config.scope}
              onChange={(e) => setConfig({ ...config, scope: e.target.value as ScopeType, scopeId: undefined })}
              style={{
                padding: '10px 14px',
                border: '1px solid var(--border-color)',
                borderRadius: '8px',
                fontSize: '14px',
                minWidth: '150px'
              }}
            >
              <option value="organization">Organization</option>
              <option value="workflow">Workflow</option>
              <option value="agent">Agent</option>
            </select>

            {config.scope === 'workflow' && (
              <select
                value={config.scopeId || ''}
                onChange={(e) => setConfig({ ...config, scopeId: e.target.value })}
                style={{
                  flex: 1,
                  padding: '10px 14px',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  fontSize: '14px'
                }}
              >
                <option value="">Select workflow...</option>
                {WORKFLOWS.map(wf => (
                  <option key={wf.id} value={wf.id}>{wf.name}</option>
                ))}
              </select>
            )}

            {config.scope === 'agent' && (
              <input
                type="text"
                placeholder="Agent ID or name..."
                value={config.scopeId || ''}
                onChange={(e) => setConfig({ ...config, scopeId: e.target.value })}
                style={{
                  flex: 1,
                  padding: '10px 14px',
                  border: '1px solid var(--border-color)',
                  borderRadius: '8px',
                  fontSize: '14px'
                }}
              />
            )}
          </div>
        </div>

        {/* Strategy Type Selector */}
        <div style={{ marginBottom: '24px' }}>
          <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '12px' }}>
            Routing Strategy
          </label>
          <select
            value={config.strategyType}
            onChange={(e) => setConfig({ ...config, strategyType: e.target.value as StrategyType })}
            style={{
              width: '100%',
              padding: '10px 14px',
              border: '1px solid var(--border-color)',
              borderRadius: '8px',
              fontSize: '14px'
            }}
          >
            <option value="cost_optimized">Cost Optimized - Minimize costs while meeting quality/latency thresholds</option>
            <option value="latency_optimized">Latency Optimized - Minimize response time</option>
            <option value="quality_first">Quality First - Maximize quality within cost limits</option>
            <option value="weighted_roundrobin">Weighted Round-Robin - Distribute load based on weights</option>
            <option value="custom">Custom - Advanced JSON configuration</option>
          </select>
        </div>

        {/* Strategy Configuration Form */}
        <div style={{
          padding: '20px',
          background: 'var(--bg-secondary)',
          borderRadius: '8px',
          marginBottom: '24px'
        }}>
          {renderStrategyForm()}
        </div>

        {/* Model Preferences */}
        <div>
          <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '12px' }}>
            Model Preferences
          </label>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
            {config.modelPreferences.map((model) => (
              <div
                key={model.id}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '16px',
                  padding: '16px',
                  background: 'var(--bg-secondary)',
                  borderRadius: '8px',
                  border: model.enabled ? '1px solid var(--primary-color)' : '1px solid var(--border-color)'
                }}
              >
                <input
                  type="checkbox"
                  checked={model.enabled}
                  onChange={(e) => updateModelPreference(model.id, e.target.checked)}
                  style={{ width: '18px', height: '18px', cursor: 'pointer' }}
                />
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  <div style={{ fontWeight: 500, fontSize: '14px' }}>{model.name}</div>
                  <div style={{ display: 'flex', gap: '16px', fontSize: '12px', color: 'var(--text-secondary)' }}>
                    <span>Cost: ${model.cost.toFixed(2)}/1K</span>
                    <span>Quality: {(model.quality * 100).toFixed(0)}%</span>
                  </div>
                </div>
                <div style={{
                  width: '100px',
                  height: '6px',
                  background: 'var(--border-color)',
                  borderRadius: '3px',
                  position: 'relative',
                  overflow: 'hidden'
                }}>
                  <div style={{
                    position: 'absolute',
                    left: 0,
                    top: 0,
                    bottom: 0,
                    width: `${model.quality * 100}%`,
                    background: 'linear-gradient(90deg, #10b981, var(--primary-color))',
                    borderRadius: '3px'
                  }} />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Action Buttons */}
      <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
        <button
          className="btn-secondary"
          onClick={handleTestRouting}
          disabled={testing}
          style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          {testing ? <Loader2 size={18} className="animate-spin" /> : <TestTube size={18} />}
          Test Routing
        </button>
        <button
          className="btn-primary"
          onClick={handleSaveConfiguration}
          disabled={saving}
          style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          {saving ? <Loader2 size={18} className="animate-spin" /> : <Save size={18} />}
          Save Configuration
        </button>
      </div>
    </div>
  );
}

export default ModelRouterSettings;
