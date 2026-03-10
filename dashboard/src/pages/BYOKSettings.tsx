/**
 * BYOK Settings Page (Bring Your Own Keys)
 *
 * Configure LLM provider API keys for customer-managed billing.
 * Supports OpenAI, Anthropic, Google AI, Azure OpenAI, AWS Bedrock,
 * Cohere, Mistral, and Groq.
 */

import { useState, useEffect } from 'react';
import {
  Key,
  Plus,
  Trash2,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Eye,
  EyeOff,
  X,
  Zap,
  Loader2,
  DollarSign,
  RefreshCw,
  Shield,
  ExternalLink,
  Calendar,
  Clock,
} from 'lucide-react';

// Types
interface BYOKKeyMetadata {
  provider: string;
  is_valid: boolean | null;
  last_validated_at: string | null;
  validation_error: string | null;
  expires_at: string | null;
  reminder_days_before: number;
  created_at: string;
  updated_at: string;
  key_name: string | null;
  key_prefix: string | null;
  needs_renewal: boolean;
  days_until_expiry: number | null;
}

interface CustomerConfig {
  customer_id: string;
  billing_model: string;
  managed_providers: string[];
  markup_percentage: number;
  prepaid_balance_usd: number | null;
  daily_limit_usd: number | null;
  monthly_limit_usd: number | null;
  allowed_models: string[];
  blocked_models: string[];
  has_byok_keys: Record<string, boolean>;
  byok_key_metadata: Record<string, BYOKKeyMetadata>;
  created_at: string;
  updated_at: string;
}

interface ProviderPricing {
  [model: string]: {
    input_per_1m_tokens: number;
    output_per_1m_tokens: number;
  };
}

interface PricingResponse {
  pricing: Record<string, ProviderPricing>;
  currency: string;
  unit: string;
}

const PROVIDER_INFO: Record<string, { name: string; icon: string; color: string; docsUrl: string }> = {
  openai: {
    name: 'OpenAI',
    icon: '🤖',
    color: 'bg-green-500',
    docsUrl: 'https://platform.openai.com/api-keys',
  },
  anthropic: {
    name: 'Anthropic',
    icon: '🧠',
    color: 'bg-orange-500',
    docsUrl: 'https://console.anthropic.com/settings/keys',
  },
  google: {
    name: 'Google AI',
    icon: '🔵',
    color: 'bg-blue-500',
    docsUrl: 'https://aistudio.google.com/app/apikey',
  },
  azure_openai: {
    name: 'Azure OpenAI',
    icon: '☁️',
    color: 'bg-sky-500',
    docsUrl: 'https://portal.azure.com/#view/Microsoft_Azure_ProjectOxford/CognitiveServicesHub/~/OpenAI',
  },
  aws_bedrock: {
    name: 'AWS Bedrock',
    icon: '📦',
    color: 'bg-amber-500',
    docsUrl: 'https://console.aws.amazon.com/bedrock',
  },
  cohere: {
    name: 'Cohere',
    icon: '🔷',
    color: 'bg-purple-500',
    docsUrl: 'https://dashboard.cohere.com/api-keys',
  },
  mistral: {
    name: 'Mistral',
    icon: '🌪️',
    color: 'bg-indigo-500',
    docsUrl: 'https://console.mistral.ai/api-keys/',
  },
  groq: {
    name: 'Groq',
    icon: '⚡',
    color: 'bg-red-500',
    docsUrl: 'https://console.groq.com/keys',
  },
};

const API_BASE = 'http://localhost:8000';
// In development mode, the API key verification returns 'debug' as the organization_id
// In production, this would come from auth context
const DEFAULT_CUSTOMER_ID = 'debug';

export function BYOKSettingsPage() {
  const [config, setConfig] = useState<CustomerConfig | null>(null);
  const [pricing, setPricing] = useState<PricingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [validatingProvider, setValidatingProvider] = useState<string | null>(null);
  const [validationResults, setValidationResults] = useState<Record<string, { valid: boolean; error?: string }>>({});

  // Modal states
  const [showAddKeyModal, setShowAddKeyModal] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string | null>(null);
  const [apiKey, setApiKey] = useState('');
  const [keyName, setKeyName] = useState('');
  const [expiresAt, setExpiresAt] = useState('');
  const [showKey, setShowKey] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  useEffect(() => {
    fetchConfig();
    fetchPricing();
  }, []);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/llm-billing/customers/${DEFAULT_CUSTOMER_ID}`);
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
      } else if (response.status === 404) {
        // Customer doesn't exist yet, create one
        await createCustomer();
      }
    } catch (error) {
      console.error('Error fetching config:', error);
      setToast({ message: 'Failed to fetch configuration', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const createCustomer = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/llm-billing/customers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          customer_id: DEFAULT_CUSTOMER_ID,
          billing_model: 'byok',
          markup_percentage: 0,
        }),
      });
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
        setToast({ message: 'BYOK configuration initialized', type: 'success' });
      }
    } catch (error) {
      console.error('Error creating customer:', error);
      setToast({ message: 'Failed to initialize configuration', type: 'error' });
    }
  };

  const fetchPricing = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/llm-billing/pricing`);
      if (response.ok) {
        const data = await response.json();
        setPricing(data);
      }
    } catch (error) {
      console.error('Error fetching pricing:', error);
    }
  };

  const saveApiKey = async () => {
    if (!selectedProvider || !apiKey.trim()) return;

    setSaving(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/llm-billing/customers/${DEFAULT_CUSTOMER_ID}/byok-keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: selectedProvider,
          api_key: apiKey.trim(),
          key_name: keyName.trim() || null,
          expires_at: expiresAt || null,
        }),
      });

      if (response.ok) {
        setToast({ message: `${PROVIDER_INFO[selectedProvider]?.name || selectedProvider} API key saved`, type: 'success' });
        closeModal();
        fetchConfig();
      } else {
        const error = await response.json();
        setToast({ message: error.detail || 'Failed to save API key', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to save API key', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const deleteApiKey = async (provider: string) => {
    if (!confirm(`Are you sure you want to delete the ${PROVIDER_INFO[provider]?.name || provider} API key?`)) return;

    try {
      const response = await fetch(`${API_BASE}/api/v1/llm-billing/customers/${DEFAULT_CUSTOMER_ID}/byok-keys/${provider}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        setToast({ message: 'API key deleted', type: 'success' });
        fetchConfig();
        // Clear validation result
        setValidationResults(prev => {
          const updated = { ...prev };
          delete updated[provider];
          return updated;
        });
      } else {
        setToast({ message: 'Failed to delete API key', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to delete API key', type: 'error' });
    }
  };

  const validateApiKey = async (provider: string) => {
    setValidatingProvider(provider);
    try {
      const response = await fetch(`${API_BASE}/api/v1/llm-billing/customers/${DEFAULT_CUSTOMER_ID}/byok-keys/${provider}/validate`, {
        method: 'POST',
      });

      if (response.ok) {
        const result = await response.json();
        if (result.is_valid) {
          setToast({ message: `${PROVIDER_INFO[provider]?.name || provider} key is valid`, type: 'success' });
        } else {
          setToast({ message: result.error || 'Key validation failed', type: 'error' });
        }
        // Refresh config to get updated metadata with validation status
        await fetchConfig();
      }
    } catch (error) {
      setToast({ message: 'Failed to validate API key', type: 'error' });
    } finally {
      setValidatingProvider(null);
    }
  };

  const openAddKeyModal = (provider: string) => {
    setSelectedProvider(provider);
    setApiKey('');
    setShowKey(false);
    // Pre-fill metadata if editing existing key
    const metadata = config?.byok_key_metadata?.[provider];
    if (metadata) {
      setKeyName(metadata.key_name || '');
      setExpiresAt(metadata.expires_at ? metadata.expires_at.split('T')[0] : '');
    } else {
      setKeyName('');
      setExpiresAt('');
    }
    setShowAddKeyModal(true);
  };

  const closeModal = () => {
    setShowAddKeyModal(false);
    setSelectedProvider(null);
    setApiKey('');
    setKeyName('');
    setExpiresAt('');
    setShowKey(false);
  };

  const getConfiguredProviders = () => {
    if (!config) return [];
    return Object.entries(config.has_byok_keys)
      .filter(([_, hasKey]) => hasKey)
      .map(([provider]) => provider);
  };

  const getAvailableProviders = () => {
    if (!config) return Object.keys(PROVIDER_INFO);
    return Object.keys(PROVIDER_INFO).filter(
      provider => !config.has_byok_keys[provider]
    );
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-600" />
          <p className="mt-2 text-gray-500">Loading BYOK settings...</p>
        </div>
      </div>
    );
  }

  const configuredProviders = getConfiguredProviders();
  const availableProviders = getAvailableProviders();

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Key className="w-8 h-8 text-blue-600" />
              BYOK Settings
              <span className="text-sm font-normal text-blue-600 bg-blue-100 px-2 py-1 rounded">Bring Your Own Keys</span>
            </h1>
            <p className="text-gray-600 mt-1">
              Configure your own LLM provider API keys for direct billing
            </p>
          </div>
          <button
            onClick={fetchConfig}
            className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>
      </div>

      {/* Info Banner */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
        <div className="flex gap-3">
          <Shield className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
          <div>
            <h3 className="font-medium text-blue-900">Your Keys, Your Control</h3>
            <p className="text-sm text-blue-700 mt-1">
              With BYOK, you use your own LLM provider API keys. Billing goes directly to your provider accounts.
              We only route requests and collect usage metrics - no markup on LLM costs.
            </p>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Configured Providers</p>
              <p className="text-2xl font-bold">{configuredProviders.length}</p>
            </div>
            <Key className="w-8 h-8 text-blue-500" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Available Providers</p>
              <p className="text-2xl font-bold">{availableProviders.length}</p>
            </div>
            <Plus className="w-8 h-8 text-gray-400" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Billing Model</p>
              <p className="text-2xl font-bold capitalize">{config?.billing_model || 'BYOK'}</p>
            </div>
            <DollarSign className="w-8 h-8 text-green-500" />
          </div>
        </div>
      </div>

      {/* Configured Keys Section */}
      <div className="bg-white rounded-lg shadow mb-6">
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="text-lg font-semibold">Configured API Keys</h2>
          {availableProviders.length > 0 && (
            <div className="relative group">
              <button
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                <Plus className="w-4 h-4" />
                Add Provider
              </button>
              <div className="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg border opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-10">
                {availableProviders.map(provider => {
                  const info = PROVIDER_INFO[provider];
                  return (
                    <button
                      key={provider}
                      onClick={() => openAddKeyModal(provider)}
                      className="w-full flex items-center gap-3 px-4 py-3 hover:bg-gray-50 first:rounded-t-lg last:rounded-b-lg"
                    >
                      <span className="text-xl">{info?.icon || '🔑'}</span>
                      <span className="font-medium">{info?.name || provider}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          )}
        </div>

        {configuredProviders.length === 0 ? (
          <div className="p-8 text-center">
            <Key className="w-12 h-12 mx-auto text-gray-400" />
            <p className="mt-2 text-gray-500">No API keys configured</p>
            <p className="text-sm text-gray-400">Add your LLM provider API keys to get started</p>
          </div>
        ) : (
          <div className="divide-y">
            {configuredProviders.map(provider => {
              const info = PROVIDER_INFO[provider] || { name: provider, icon: '🔑', color: 'bg-gray-500' };
              // Use persisted metadata instead of React state
              const metadata = config?.byok_key_metadata?.[provider];
              const isValid = metadata?.is_valid;
              const hasExpiration = metadata?.expires_at;
              const needsRenewal = metadata?.needs_renewal;
              const daysUntilExpiry = metadata?.days_until_expiry;

              return (
                <div key={provider} className="p-4 hover:bg-gray-50">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className={`w-12 h-12 rounded-lg ${info.color} flex items-center justify-center text-2xl text-white`}>
                        {info.icon}
                      </div>
                      <div>
                        <div className="flex items-center gap-2 flex-wrap">
                          <h3 className="font-semibold">{metadata?.key_name || info.name}</h3>
                          {isValid === true && (
                            <span className="flex items-center gap-1 text-xs text-green-600 bg-green-100 px-2 py-0.5 rounded">
                              <CheckCircle className="w-3 h-3" /> Verified
                            </span>
                          )}
                          {isValid === false && (
                            <span className="flex items-center gap-1 text-xs text-red-600 bg-red-100 px-2 py-0.5 rounded">
                              <XCircle className="w-3 h-3" /> Invalid
                            </span>
                          )}
                          {needsRenewal && (
                            <span className="flex items-center gap-1 text-xs text-amber-600 bg-amber-100 px-2 py-0.5 rounded">
                              <AlertTriangle className="w-3 h-3" /> Expires in {daysUntilExpiry} days
                            </span>
                          )}
                        </div>
                        <div className="text-sm text-gray-500 flex items-center gap-3">
                          {metadata?.key_prefix && (
                            <span className="font-mono text-xs bg-gray-100 px-1 rounded">{metadata.key_prefix}</span>
                          )}
                          {metadata?.last_validated_at && (
                            <span className="flex items-center gap-1">
                              <Clock className="w-3 h-3" />
                              Validated {new Date(metadata.last_validated_at).toLocaleDateString()}
                            </span>
                          )}
                          {hasExpiration && !needsRenewal && (
                            <span className="flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              Expires {new Date(metadata.expires_at!).toLocaleDateString()}
                            </span>
                          )}
                          {!metadata?.last_validated_at && (
                            <span>Not validated yet</span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => validateApiKey(provider)}
                        disabled={validatingProvider === provider}
                        className="flex items-center gap-2 px-3 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg disabled:opacity-50"
                        title="Validate Key"
                      >
                        {validatingProvider === provider ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <Zap className="w-4 h-4" />
                        )}
                        Validate
                      </button>
                      <button
                        onClick={() => openAddKeyModal(provider)}
                        className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded"
                        title="Update Key"
                      >
                        <Key className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => deleteApiKey(provider)}
                        className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded"
                        title="Delete Key"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Available Providers Section */}
      {availableProviders.length > 0 && (
        <div className="bg-white rounded-lg shadow">
          <div className="p-4 border-b">
            <h2 className="text-lg font-semibold">Available Providers</h2>
            <p className="text-sm text-gray-500">Click to add your API key</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 p-4">
            {availableProviders.map(provider => {
              const info = PROVIDER_INFO[provider] || { name: provider, icon: '🔑', color: 'bg-gray-500', docsUrl: '#' };
              return (
                <button
                  key={provider}
                  onClick={() => openAddKeyModal(provider)}
                  className="p-4 border-2 border-dashed border-gray-200 rounded-lg hover:border-blue-300 hover:bg-blue-50 transition-colors text-left"
                >
                  <div className="flex items-center gap-3 mb-2">
                    <div className={`w-10 h-10 rounded-lg ${info.color} flex items-center justify-center text-xl`}>
                      {info.icon}
                    </div>
                    <span className="font-medium">{info.name}</span>
                  </div>
                  <p className="text-xs text-gray-500">Click to configure</p>
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Pricing Info */}
      {pricing && (
        <div className="mt-6 bg-white rounded-lg shadow">
          <div className="p-4 border-b">
            <h2 className="text-lg font-semibold">LLM Pricing Reference</h2>
            <p className="text-sm text-gray-500">Pricing per 1 million tokens ({pricing.currency})</p>
          </div>
          <div className="p-4 overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 px-3 font-medium">Provider</th>
                  <th className="text-left py-2 px-3 font-medium">Model</th>
                  <th className="text-right py-2 px-3 font-medium">Input</th>
                  <th className="text-right py-2 px-3 font-medium">Output</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(pricing.pricing).map(([provider, models]) => (
                  Object.entries(models as ProviderPricing).slice(0, 3).map(([model, prices], idx) => (
                    <tr key={`${provider}-${model}`} className="border-b last:border-0 hover:bg-gray-50">
                      {idx === 0 && (
                        <td className="py-2 px-3 font-medium" rowSpan={Math.min(Object.keys(models as ProviderPricing).length, 3)}>
                          <div className="flex items-center gap-2">
                            <span>{PROVIDER_INFO[provider]?.icon || '🔑'}</span>
                            {PROVIDER_INFO[provider]?.name || provider}
                          </div>
                        </td>
                      )}
                      <td className="py-2 px-3 text-gray-600">{model}</td>
                      <td className="py-2 px-3 text-right text-gray-600">${prices.input_per_1m_tokens}</td>
                      <td className="py-2 px-3 text-right text-gray-600">${prices.output_per_1m_tokens}</td>
                    </tr>
                  ))
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Add/Update Key Modal */}
      {showAddKeyModal && selectedProvider && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg">
            <div className="p-4 border-b flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-10 h-10 rounded-lg ${PROVIDER_INFO[selectedProvider]?.color || 'bg-gray-500'} flex items-center justify-center text-xl`}>
                  {PROVIDER_INFO[selectedProvider]?.icon || '🔑'}
                </div>
                <div>
                  <h2 className="text-lg font-semibold">
                    {config?.has_byok_keys[selectedProvider] ? 'Update' : 'Add'} {PROVIDER_INFO[selectedProvider]?.name || selectedProvider} API Key
                  </h2>
                </div>
              </div>
              <button onClick={closeModal} className="text-gray-500 hover:text-gray-700">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {/* Security Notice */}
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-3">
                <div className="flex gap-2">
                  <AlertTriangle className="w-4 h-4 text-amber-600 flex-shrink-0 mt-0.5" />
                  <div>
                    <p className="text-sm text-amber-800">
                      <strong>Security:</strong> Your API key is encrypted before storage and never exposed in the UI.
                    </p>
                  </div>
                </div>
              </div>

              {/* Key Name (optional) */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Key Name <span className="text-gray-400 font-normal">(optional)</span>
                </label>
                <input
                  type="text"
                  value={keyName}
                  onChange={(e) => setKeyName(e.target.value)}
                  placeholder="e.g., Production Key, Development Key"
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                />
              </div>

              {/* API Key Input */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">API Key</label>
                <div className="relative">
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder={`Enter your ${PROVIDER_INFO[selectedProvider]?.name || selectedProvider} API key`}
                    className="w-full px-3 py-2 pr-10 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-700"
                  >
                    {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Expiration Date (optional) */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Expiration Date <span className="text-gray-400 font-normal">(optional - for renewal reminders)</span>
                </label>
                <div className="relative">
                  <input
                    type="date"
                    value={expiresAt}
                    onChange={(e) => setExpiresAt(e.target.value)}
                    min={new Date().toISOString().split('T')[0]}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm"
                  />
                  <Calendar className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400 pointer-events-none" />
                </div>
                <p className="mt-1 text-xs text-gray-500">
                  Set an expiration date to receive renewal reminders before your key expires
                </p>
              </div>

              {/* Get API Key Link */}
              {PROVIDER_INFO[selectedProvider]?.docsUrl && (
                <a
                  href={PROVIDER_INFO[selectedProvider].docsUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 text-sm text-blue-600 hover:text-blue-700"
                >
                  <ExternalLink className="w-4 h-4" />
                  Get your {PROVIDER_INFO[selectedProvider]?.name} API key
                </a>
              )}
            </div>

            <div className="p-4 border-t bg-gray-50 flex justify-end gap-2">
              <button
                onClick={closeModal}
                className="px-4 py-2 text-gray-700 hover:bg-gray-200 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={saveApiKey}
                disabled={!apiKey.trim() || saving}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 flex items-center gap-2"
              >
                {saving ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <Key className="w-4 h-4" />
                    Save API Key
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg ${
          toast.type === 'success' ? 'bg-green-500' : 'bg-red-500'
        } text-white flex items-center gap-2`}>
          {toast.type === 'success' ? (
            <CheckCircle className="w-4 h-4" />
          ) : (
            <XCircle className="w-4 h-4" />
          )}
          {toast.message}
        </div>
      )}
    </div>
  );
}

export default BYOKSettingsPage;
