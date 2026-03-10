/**
 * Memory Providers Page (BYOS - Bring Your Own Storage)
 *
 * Configure and manage vector database connections for agent memory.
 * Supports Pinecone, Qdrant, Weaviate, Redis, Chroma, pgvector.
 */

import { useState, useEffect } from 'react';
import {
  Database,
  Plus,
  Trash2,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Settings,
  Eye,
  EyeOff,
  X,
  Zap,
  Loader2,
  Brain,
  Activity,
  Search,
  Copy,
  Star,
  Edit,
} from 'lucide-react';

// Types
interface MemoryProvider {
  config_id: string;
  organization_id: string;
  provider_type: string;
  name: string;
  description: string | null;
  embedding_provider: string;
  embedding_model: string;
  embedding_dimensions: number;
  is_active: boolean;
  is_default: boolean;
  health_status: string | null;
  last_health_check: string | null;
  total_memories: number;
  total_queries: number;
  tags: string[] | null;
  created_at: string;
  updated_at: string;
}

interface ProviderSchema {
  required: string[];
  optional: string[];
  example: Record<string, unknown>;
}

interface EmbeddingModel {
  dimensions: number;
  cost_per_1k: number;
}

const PROVIDER_ICONS: Record<string, string> = {
  pinecone: '🌲',
  qdrant: '🔷',
  weaviate: '🌐',
  redis: '🔴',
  chroma: '🎨',
  pgvector: '🐘',
  custom: '⚙️',
};

const PROVIDER_COLORS: Record<string, string> = {
  pinecone: 'bg-green-500',
  qdrant: 'bg-blue-500',
  weaviate: 'bg-purple-500',
  redis: 'bg-red-500',
  chroma: 'bg-yellow-500',
  pgvector: 'bg-indigo-500',
  custom: 'bg-gray-500',
};

const API_BASE = 'http://localhost:8000';
const ORG_ID = 'my-org';

export function MemoryProvidersPage() {
  const [providers, setProviders] = useState<MemoryProvider[]>([]);
  const [schemas, setSchemas] = useState<Record<string, ProviderSchema>>({});
  const [embeddingProviders, setEmbeddingProviders] = useState<Record<string, { models: Record<string, EmbeddingModel> }>>({});
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<MemoryProvider | null>(null);
  const [showSecrets, setShowSecrets] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  // Form state
  const [form, setForm] = useState({
    provider_type: 'pinecone',
    name: '',
    description: '',
    embedding_provider: 'openai',
    embedding_model: 'text-embedding-3-small',
    is_default: false,
    connection_config: '{}',
  });

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  useEffect(() => {
    fetchSchemas();
    fetchProviders();
  }, []);

  const fetchSchemas = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/memory/providers/schemas`);
      if (response.ok) {
        const data = await response.json();
        setSchemas(data.providers || {});
        setEmbeddingProviders(data.embedding_providers || {});
      }
    } catch (error) {
      console.error('Error fetching schemas:', error);
    }
  };

  const fetchProviders = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/memory/providers`, {
        headers: { 'X-Organization-Id': ORG_ID },
      });
      if (response.ok) {
        const data = await response.json();
        setProviders(data);
      }
    } catch (error) {
      console.error('Error fetching providers:', error);
      setToast({ message: 'Failed to fetch providers', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const createProvider = async () => {
    try {
      let connectionConfig;
      try {
        connectionConfig = JSON.parse(form.connection_config);
      } catch {
        setToast({ message: 'Invalid JSON in connection config', type: 'error' });
        return;
      }

      const response = await fetch(`${API_BASE}/api/memory/providers`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Organization-Id': ORG_ID,
        },
        body: JSON.stringify({
          provider_type: form.provider_type,
          name: form.name,
          description: form.description || null,
          connection_config: connectionConfig,
          embedding_provider: form.embedding_provider,
          embedding_model: form.embedding_model,
          is_default: form.is_default,
        }),
      });

      if (response.ok) {
        setToast({ message: 'Provider created successfully', type: 'success' });
        setShowCreateModal(false);
        resetForm();
        fetchProviders();
      } else {
        const error = await response.json();
        setToast({ message: error.detail || 'Failed to create provider', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to create provider', type: 'error' });
    }
  };

  const deleteProvider = async (configId: string) => {
    if (!confirm('Are you sure you want to delete this provider?')) return;

    try {
      const response = await fetch(`${API_BASE}/api/memory/providers/${configId}`, {
        method: 'DELETE',
        headers: { 'X-Organization-Id': ORG_ID },
      });

      if (response.ok) {
        setToast({ message: 'Provider deleted', type: 'success' });
        fetchProviders();
      } else {
        setToast({ message: 'Failed to delete provider', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to delete provider', type: 'error' });
    }
  };

  const testConnection = async (configId: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/memory/providers/${configId}/test`, {
        method: 'POST',
        headers: { 'X-Organization-Id': ORG_ID },
      });

      if (response.ok) {
        const result = await response.json();
        if (result.status === 'healthy') {
          setToast({ message: `Connection healthy (${result.latency_ms?.toFixed(0)}ms)`, type: 'success' });
        } else {
          setToast({ message: `Connection unhealthy: ${result.error}`, type: 'error' });
        }
        fetchProviders();
      }
    } catch (error) {
      setToast({ message: 'Failed to test connection', type: 'error' });
    }
  };

  const setAsDefault = async (configId: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/memory/providers/${configId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-Organization-Id': ORG_ID,
        },
        body: JSON.stringify({ is_default: true }),
      });

      if (response.ok) {
        setToast({ message: 'Default provider updated', type: 'success' });
        fetchProviders();
      }
    } catch (error) {
      setToast({ message: 'Failed to update default', type: 'error' });
    }
  };

  const openEditModal = (provider: MemoryProvider) => {
    setEditMode(true);
    setEditingId(provider.config_id);
    setForm({
      provider_type: provider.provider_type,
      name: provider.name,
      description: provider.description || '',
      embedding_provider: provider.embedding_provider,
      embedding_model: provider.embedding_model,
      is_default: provider.is_default,
      connection_config: '{}', // Don't show existing secrets, require re-entry for security
    });
    setShowCreateModal(true);
  };

  const updateProvider = async () => {
    if (!editingId) return;

    try {
      let connectionConfig;
      try {
        connectionConfig = JSON.parse(form.connection_config);
      } catch {
        setToast({ message: 'Invalid JSON in connection config', type: 'error' });
        return;
      }

      const updateData: Record<string, unknown> = {
        name: form.name,
        description: form.description || null,
        embedding_provider: form.embedding_provider,
        embedding_model: form.embedding_model,
        is_default: form.is_default,
      };

      // Only include connection_config if it was changed (not empty {})
      if (Object.keys(connectionConfig).length > 0) {
        updateData.connection_config = connectionConfig;
      }

      const response = await fetch(`${API_BASE}/api/memory/providers/${editingId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-Organization-Id': ORG_ID,
        },
        body: JSON.stringify(updateData),
      });

      if (response.ok) {
        setToast({ message: 'Provider updated successfully', type: 'success' });
        closeModal();
        fetchProviders();
      } else {
        const error = await response.json();
        setToast({ message: error.detail || 'Failed to update provider', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to update provider', type: 'error' });
    }
  };

  const closeModal = () => {
    setShowCreateModal(false);
    setEditMode(false);
    setEditingId(null);
    resetForm();
  };

  const resetForm = () => {
    setForm({
      provider_type: 'pinecone',
      name: '',
      description: '',
      embedding_provider: 'openai',
      embedding_model: 'text-embedding-3-small',
      is_default: false,
      connection_config: '{}',
    });
  };

  const getExampleConfig = (providerType: string) => {
    const schema = schemas[providerType];
    if (schema?.example) {
      return JSON.stringify(schema.example, null, 2);
    }
    return '{}';
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Brain className="w-8 h-8 text-purple-600" />
              Memory Providers
              <span className="text-sm font-normal text-purple-600 bg-purple-100 px-2 py-1 rounded">BYOS</span>
            </h1>
            <p className="text-gray-600 mt-1">
              Connect your own vector databases for agent memory storage
            </p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
          >
            <Plus className="w-4 h-4" />
            Add Provider
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Providers</p>
              <p className="text-2xl font-bold">{providers.length}</p>
            </div>
            <Database className="w-8 h-8 text-purple-500" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Memories</p>
              <p className="text-2xl font-bold">{providers.reduce((sum, p) => sum + p.total_memories, 0).toLocaleString()}</p>
            </div>
            <Brain className="w-8 h-8 text-blue-500" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Queries</p>
              <p className="text-2xl font-bold">{providers.reduce((sum, p) => sum + p.total_queries, 0).toLocaleString()}</p>
            </div>
            <Search className="w-8 h-8 text-green-500" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Healthy</p>
              <p className="text-2xl font-bold">{providers.filter(p => p.health_status === 'healthy').length} / {providers.length}</p>
            </div>
            <Activity className="w-8 h-8 text-emerald-500" />
          </div>
        </div>
      </div>

      {/* Providers List */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b">
          <h2 className="text-lg font-semibold">Configured Providers</h2>
        </div>

        {loading ? (
          <div className="p-8 text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-purple-600" />
            <p className="mt-2 text-gray-500">Loading providers...</p>
          </div>
        ) : providers.length === 0 ? (
          <div className="p-8 text-center">
            <Database className="w-12 h-12 mx-auto text-gray-400" />
            <p className="mt-2 text-gray-500">No memory providers configured</p>
            <p className="text-sm text-gray-400">Add a provider to enable agent memory</p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="mt-4 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700"
            >
              Add Your First Provider
            </button>
          </div>
        ) : (
          <div className="divide-y">
            {providers.map((provider) => (
              <div key={provider.config_id} className="p-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-lg ${PROVIDER_COLORS[provider.provider_type] || 'bg-gray-500'} flex items-center justify-center text-2xl`}>
                      {PROVIDER_ICONS[provider.provider_type] || '⚙️'}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold">{provider.name}</h3>
                        {provider.is_default && (
                          <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded flex items-center gap-1">
                            <Star className="w-3 h-3" /> Default
                          </span>
                        )}
                        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded capitalize">
                          {provider.provider_type}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500">
                        {provider.embedding_provider} / {provider.embedding_model} ({provider.embedding_dimensions}d)
                      </p>
                      {provider.description && (
                        <p className="text-sm text-gray-400">{provider.description}</p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    {/* Stats */}
                    <div className="text-right">
                      <p className="text-sm font-medium">{provider.total_memories.toLocaleString()} memories</p>
                      <p className="text-xs text-gray-500">{provider.total_queries.toLocaleString()} queries</p>
                    </div>

                    {/* Health Status */}
                    <div className="flex items-center gap-2">
                      {provider.health_status === 'healthy' ? (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      ) : provider.health_status === 'unhealthy' ? (
                        <XCircle className="w-5 h-5 text-red-500" />
                      ) : (
                        <AlertTriangle className="w-5 h-5 text-yellow-500" />
                      )}
                      <span className={`text-sm ${
                        provider.health_status === 'healthy' ? 'text-green-600' :
                        provider.health_status === 'unhealthy' ? 'text-red-600' : 'text-yellow-600'
                      }`}>
                        {provider.health_status || 'Unknown'}
                      </span>
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => testConnection(provider.config_id)}
                        className="p-2 text-gray-500 hover:text-green-600 hover:bg-green-50 rounded"
                        title="Test Connection"
                      >
                        <Zap className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => openEditModal(provider)}
                        className="p-2 text-gray-500 hover:text-purple-600 hover:bg-purple-50 rounded"
                        title="Edit"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      {!provider.is_default && (
                        <button
                          onClick={() => setAsDefault(provider.config_id)}
                          className="p-2 text-gray-500 hover:text-yellow-600 hover:bg-yellow-50 rounded"
                          title="Set as Default"
                        >
                          <Star className="w-4 h-4" />
                        </button>
                      )}
                      <button
                        onClick={() => deleteProvider(provider.config_id)}
                        className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded"
                        title="Delete"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create/Edit Provider Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-4 border-b flex items-center justify-between">
              <h2 className="text-lg font-semibold">{editMode ? 'Edit Memory Provider' : 'Add Memory Provider'}</h2>
              <button onClick={closeModal} className="text-gray-500 hover:text-gray-700">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              {/* Provider Type */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Provider Type</label>
                <div className="grid grid-cols-4 gap-2">
                  {Object.keys(schemas).map((type) => (
                    <button
                      key={type}
                      onClick={() => {
                        setForm({ ...form, provider_type: type, connection_config: getExampleConfig(type) });
                      }}
                      className={`p-3 rounded-lg border-2 text-center ${
                        form.provider_type === type
                          ? 'border-purple-500 bg-purple-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <span className="text-2xl">{PROVIDER_ICONS[type] || '⚙️'}</span>
                      <p className="text-sm mt-1 capitalize">{type}</p>
                    </button>
                  ))}
                </div>
              </div>

              {/* Name */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="Production Vector DB"
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                />
              </div>

              {/* Description */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Description (optional)</label>
                <input
                  type="text"
                  value={form.description}
                  onChange={(e) => setForm({ ...form, description: e.target.value })}
                  placeholder="Main memory store for production agents"
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                />
              </div>

              {/* Embedding Provider */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Embedding Provider</label>
                  <select
                    value={form.embedding_provider}
                    onChange={(e) => {
                      const provider = e.target.value;
                      const models = Object.keys(embeddingProviders[provider]?.models || {});
                      setForm({
                        ...form,
                        embedding_provider: provider,
                        embedding_model: models[0] || '',
                      });
                    }}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  >
                    {Object.keys(embeddingProviders).map((provider) => (
                      <option key={provider} value={provider}>{provider}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Embedding Model</label>
                  <select
                    value={form.embedding_model}
                    onChange={(e) => setForm({ ...form, embedding_model: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                  >
                    {Object.entries(embeddingProviders[form.embedding_provider]?.models || {}).map(([model, config]) => (
                      <option key={model} value={model}>
                        {model} ({config.dimensions}d)
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {/* Connection Config */}
              <div>
                <div className="flex items-center justify-between mb-1">
                  <label className="block text-sm font-medium text-gray-700">Connection Configuration</label>
                  <button
                    onClick={() => setShowSecrets(!showSecrets)}
                    className="text-sm text-gray-500 hover:text-gray-700 flex items-center gap-1"
                  >
                    {showSecrets ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                    {showSecrets ? 'Hide' : 'Show'} secrets
                  </button>
                </div>
                {editMode && (
                  <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 mb-2">
                    <p className="text-sm text-amber-800 flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4" />
                      <span>
                        <strong>Security Note:</strong> Existing credentials are not displayed.
                        Leave as <code className="bg-amber-100 px-1 rounded">{'{}'}</code> to keep current config,
                        or enter new values to update.
                      </span>
                    </p>
                  </div>
                )}
                <textarea
                  value={form.connection_config}
                  onChange={(e) => setForm({ ...form, connection_config: e.target.value })}
                  rows={6}
                  placeholder={editMode ? '{"api_key": "new-key-if-changing"}' : undefined}
                  className={`w-full px-3 py-2 border rounded-lg font-mono text-sm focus:ring-2 focus:ring-purple-500 focus:border-purple-500 ${
                    !showSecrets ? 'text-security-disc' : ''
                  }`}
                  style={!showSecrets ? { WebkitTextSecurity: 'disc' } as React.CSSProperties : {}}
                />
                {schemas[form.provider_type] && (
                  <p className="text-xs text-gray-500 mt-1">
                    Required: {schemas[form.provider_type].required.join(', ')}
                    {schemas[form.provider_type].optional?.length > 0 && (
                      <> | Optional: {schemas[form.provider_type].optional.join(', ')}</>
                    )}
                  </p>
                )}
              </div>

              {/* Default Toggle */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_default"
                  checked={form.is_default}
                  onChange={(e) => setForm({ ...form, is_default: e.target.checked })}
                  className="rounded text-purple-600 focus:ring-purple-500"
                />
                <label htmlFor="is_default" className="text-sm text-gray-700">Set as default provider</label>
              </div>
            </div>

            <div className="p-4 border-t bg-gray-50 flex justify-end gap-2">
              <button
                onClick={closeModal}
                className="px-4 py-2 text-gray-700 hover:bg-gray-200 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={editMode ? updateProvider : createProvider}
                disabled={!form.name || (!editMode && !form.connection_config)}
                className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 disabled:opacity-50"
              >
                {editMode ? 'Update Provider' : 'Create Provider'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg ${
          toast.type === 'success' ? 'bg-green-500' : 'bg-red-500'
        } text-white`}>
          {toast.message}
        </div>
      )}
    </div>
  );
}

export default MemoryProvidersPage;
