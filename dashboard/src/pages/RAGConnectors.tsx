/**
 * RAG Connectors Page (BYOD - Bring Your Own Data)
 *
 * Configure and manage document store connections for RAG.
 * Supports S3, Elasticsearch, Notion, Confluence, Google Drive, etc.
 */

import { useState, useEffect } from 'react';
import {
  FolderOpen,
  Plus,
  Trash2,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  X,
  Loader2,
  FileText,
  Search,
  Download,
  Upload,
  Clock,
  Database,
  Cloud,
  Star,
  Zap,
  Eye,
  Edit,
} from 'lucide-react';

// Types
interface RAGConnector {
  config_id: string;
  organization_id: string;
  provider_type: string;
  name: string;
  description: string | null;
  chunking_strategy: string;
  chunk_size: number;
  chunk_overlap: number;
  memory_provider_id: string | null;
  embedding_provider: string | null;
  embedding_model: string | null;
  sync_enabled: boolean;
  sync_interval_hours: number | null;
  last_sync_at: string | null;
  last_sync_status: string | null;
  last_sync_documents: number | null;
  is_active: boolean;
  is_default: boolean;
  health_status: string | null;
  last_health_check: string | null;
  total_documents: number;
  total_chunks: number;
  total_queries: number;
  tags: string[] | null;
  created_at: string;
  updated_at: string;
}

interface DocumentIndex {
  document_id: string;
  connector_id: string;
  source_id: string;
  source_path: string | null;
  source_type: string;
  title: string | null;
  chunk_count: number;
  index_status: string;
  index_error: string | null;
  indexed_at: string | null;
  source_modified_at: string | null;
  needs_reindex: boolean;
  created_at: string;
}

const PROVIDER_ICONS: Record<string, string> = {
  s3: '☁️',
  gcs: '🌐',
  azure_blob: '📦',
  elasticsearch: '🔍',
  opensearch: '🔎',
  mongodb: '🍃',
  postgresql: '🐘',
  notion: '📝',
  confluence: '📚',
  google_drive: '📁',
  sharepoint: '📂',
  custom: '⚙️',
};

const PROVIDER_COLORS: Record<string, string> = {
  s3: 'bg-orange-500',
  gcs: 'bg-blue-500',
  azure_blob: 'bg-sky-500',
  elasticsearch: 'bg-yellow-500',
  opensearch: 'bg-purple-500',
  mongodb: 'bg-green-500',
  postgresql: 'bg-indigo-500',
  notion: 'bg-gray-800',
  confluence: 'bg-blue-600',
  google_drive: 'bg-emerald-500',
  sharepoint: 'bg-teal-500',
  custom: 'bg-gray-500',
};

const CHUNKING_STRATEGIES = [
  { value: 'recursive', label: 'Recursive Character', description: 'Best for most documents' },
  { value: 'sentence', label: 'Sentence', description: 'Split at sentence boundaries' },
  { value: 'paragraph', label: 'Paragraph', description: 'Split at paragraph boundaries' },
  { value: 'fixed_size', label: 'Fixed Size', description: 'Fixed character count' },
  { value: 'semantic', label: 'Semantic', description: 'Split by semantic similarity' },
  { value: 'code', label: 'Code', description: 'Language-aware code splitting' },
];

const API_BASE = 'http://localhost:8000';
const ORG_ID = 'my-org';

export function RAGConnectorsPage() {
  const [connectors, setConnectors] = useState<RAGConnector[]>([]);
  const [schemas, setSchemas] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showDocumentsModal, setShowDocumentsModal] = useState(false);
  const [selectedConnector, setSelectedConnector] = useState<RAGConnector | null>(null);
  const [documents, setDocuments] = useState<DocumentIndex[]>([]);
  const [loadingDocuments, setLoadingDocuments] = useState(false);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [editMode, setEditMode] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  // Form state
  const [form, setForm] = useState({
    provider_type: 's3',
    name: '',
    description: '',
    chunking_strategy: 'recursive',
    chunk_size: 1000,
    chunk_overlap: 200,
    memory_provider_id: '',
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
    fetchConnectors();
  }, []);

  const fetchSchemas = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/rag/connectors/schemas`);
      if (response.ok) {
        const data = await response.json();
        setSchemas(data.connectors || {});
      }
    } catch (error) {
      console.error('Error fetching schemas:', error);
    }
  };

  const fetchConnectors = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/rag/connectors`, {
        headers: { 'X-Organization-Id': ORG_ID },
      });
      if (response.ok) {
        const data = await response.json();
        setConnectors(data);
      }
    } catch (error) {
      console.error('Error fetching connectors:', error);
      setToast({ message: 'Failed to fetch connectors', type: 'error' });
    } finally {
      setLoading(false);
    }
  };

  const fetchDocuments = async (connectorId: string) => {
    setLoadingDocuments(true);
    try {
      const response = await fetch(`${API_BASE}/api/rag/index?connector_id=${connectorId}`, {
        headers: { 'X-Organization-Id': ORG_ID },
      });
      if (response.ok) {
        const data = await response.json();
        setDocuments(data);
      }
    } catch (error) {
      console.error('Error fetching documents:', error);
    } finally {
      setLoadingDocuments(false);
    }
  };

  const createConnector = async () => {
    try {
      let connectionConfig;
      try {
        connectionConfig = JSON.parse(form.connection_config);
      } catch {
        setToast({ message: 'Invalid JSON in connection config', type: 'error' });
        return;
      }

      const response = await fetch(`${API_BASE}/api/rag/connectors`, {
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
          chunking_strategy: form.chunking_strategy,
          chunk_size: form.chunk_size,
          chunk_overlap: form.chunk_overlap,
          memory_provider_id: form.memory_provider_id || null,
          is_default: form.is_default,
        }),
      });

      if (response.ok) {
        setToast({ message: 'Connector created successfully', type: 'success' });
        setShowCreateModal(false);
        resetForm();
        fetchConnectors();
      } else {
        const error = await response.json();
        setToast({ message: error.detail || 'Failed to create connector', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to create connector', type: 'error' });
    }
  };

  const deleteConnector = async (configId: string) => {
    if (!confirm('Are you sure you want to delete this connector?')) return;

    try {
      const response = await fetch(`${API_BASE}/api/rag/connectors/${configId}`, {
        method: 'DELETE',
        headers: { 'X-Organization-Id': ORG_ID },
      });

      if (response.ok) {
        setToast({ message: 'Connector deleted', type: 'success' });
        fetchConnectors();
      } else {
        setToast({ message: 'Failed to delete connector', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to delete connector', type: 'error' });
    }
  };

  const syncConnector = async (configId: string) => {
    setSyncing(configId);
    try {
      const response = await fetch(`${API_BASE}/api/rag/connectors/${configId}/sync`, {
        method: 'POST',
        headers: { 'X-Organization-Id': ORG_ID },
      });

      if (response.ok) {
        const result = await response.json();
        setToast({
          message: `Sync complete: ${result.new_documents} new, ${result.updated_documents} updated`,
          type: 'success'
        });
        fetchConnectors();
      } else {
        setToast({ message: 'Sync failed', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Sync failed', type: 'error' });
    } finally {
      setSyncing(null);
    }
  };

  const testConnection = async (configId: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/rag/connectors/${configId}/test`, {
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
        fetchConnectors();
      }
    } catch (error) {
      setToast({ message: 'Failed to test connection', type: 'error' });
    }
  };

  const setAsDefault = async (configId: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/rag/connectors/${configId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-Organization-Id': ORG_ID,
        },
        body: JSON.stringify({ is_default: true }),
      });

      if (response.ok) {
        setToast({ message: 'Default connector updated', type: 'success' });
        fetchConnectors();
      }
    } catch (error) {
      setToast({ message: 'Failed to update default', type: 'error' });
    }
  };

  const openDocuments = (connector: RAGConnector) => {
    setSelectedConnector(connector);
    setShowDocumentsModal(true);
    fetchDocuments(connector.config_id);
  };

  const openEditModal = (connector: RAGConnector) => {
    setEditMode(true);
    setEditingId(connector.config_id);
    setForm({
      provider_type: connector.provider_type,
      name: connector.name,
      description: connector.description || '',
      chunking_strategy: connector.chunking_strategy,
      chunk_size: connector.chunk_size,
      chunk_overlap: connector.chunk_overlap,
      memory_provider_id: connector.memory_provider_id || '',
      is_default: connector.is_default,
      connection_config: '{}', // Don't show existing secrets
    });
    setShowCreateModal(true);
  };

  const updateConnector = async () => {
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
        chunking_strategy: form.chunking_strategy,
        chunk_size: form.chunk_size,
        chunk_overlap: form.chunk_overlap,
        memory_provider_id: form.memory_provider_id || null,
        is_default: form.is_default,
      };

      // Only include connection_config if it was changed
      if (Object.keys(connectionConfig).length > 0) {
        updateData.connection_config = connectionConfig;
      }

      const response = await fetch(`${API_BASE}/api/rag/connectors/${editingId}`, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          'X-Organization-Id': ORG_ID,
        },
        body: JSON.stringify(updateData),
      });

      if (response.ok) {
        setToast({ message: 'Connector updated successfully', type: 'success' });
        closeModal();
        fetchConnectors();
      } else {
        const error = await response.json();
        setToast({ message: error.detail || 'Failed to update connector', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to update connector', type: 'error' });
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
      provider_type: 's3',
      name: '',
      description: '',
      chunking_strategy: 'recursive',
      chunk_size: 1000,
      chunk_overlap: 200,
      memory_provider_id: '',
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
              <FolderOpen className="w-8 h-8 text-blue-600" />
              RAG Connectors
              <span className="text-sm font-normal text-blue-600 bg-blue-100 px-2 py-1 rounded">BYOD</span>
            </h1>
            <p className="text-gray-600 mt-1">
              Connect your document stores for retrieval-augmented generation
            </p>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <Plus className="w-4 h-4" />
            Add Connector
          </button>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Connectors</p>
              <p className="text-2xl font-bold">{connectors.length}</p>
            </div>
            <Cloud className="w-8 h-8 text-blue-500" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Documents</p>
              <p className="text-2xl font-bold">{connectors.reduce((sum, c) => sum + c.total_documents, 0).toLocaleString()}</p>
            </div>
            <FileText className="w-8 h-8 text-green-500" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Chunks</p>
              <p className="text-2xl font-bold">{connectors.reduce((sum, c) => sum + c.total_chunks, 0).toLocaleString()}</p>
            </div>
            <Database className="w-8 h-8 text-purple-500" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Queries</p>
              <p className="text-2xl font-bold">{connectors.reduce((sum, c) => sum + c.total_queries, 0).toLocaleString()}</p>
            </div>
            <Search className="w-8 h-8 text-orange-500" />
          </div>
        </div>
      </div>

      {/* Connectors List */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b">
          <h2 className="text-lg font-semibold">Configured Connectors</h2>
        </div>

        {loading ? (
          <div className="p-8 text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-600" />
            <p className="mt-2 text-gray-500">Loading connectors...</p>
          </div>
        ) : connectors.length === 0 ? (
          <div className="p-8 text-center">
            <FolderOpen className="w-12 h-12 mx-auto text-gray-400" />
            <p className="mt-2 text-gray-500">No RAG connectors configured</p>
            <p className="text-sm text-gray-400">Add a connector to enable document retrieval</p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
            >
              Add Your First Connector
            </button>
          </div>
        ) : (
          <div className="divide-y">
            {connectors.map((connector) => (
              <div key={connector.config_id} className="p-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-lg ${PROVIDER_COLORS[connector.provider_type] || 'bg-gray-500'} flex items-center justify-center text-2xl`}>
                      {PROVIDER_ICONS[connector.provider_type] || '⚙️'}
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold">{connector.name}</h3>
                        {connector.is_default && (
                          <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded flex items-center gap-1">
                            <Star className="w-3 h-3" /> Default
                          </span>
                        )}
                        <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded capitalize">
                          {connector.provider_type.replace('_', ' ')}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500">
                        {connector.chunking_strategy} chunks ({connector.chunk_size} chars, {connector.chunk_overlap} overlap)
                      </p>
                      {connector.last_sync_at && (
                        <p className="text-xs text-gray-400">
                          Last sync: {formatDate(connector.last_sync_at)} - {connector.last_sync_status}
                        </p>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    {/* Stats */}
                    <div className="text-right">
                      <p className="text-sm font-medium">{connector.total_documents.toLocaleString()} docs</p>
                      <p className="text-xs text-gray-500">{connector.total_chunks.toLocaleString()} chunks</p>
                    </div>

                    {/* Health Status */}
                    <div className="flex items-center gap-2">
                      {connector.health_status === 'healthy' ? (
                        <CheckCircle className="w-5 h-5 text-green-500" />
                      ) : connector.health_status === 'unhealthy' ? (
                        <XCircle className="w-5 h-5 text-red-500" />
                      ) : (
                        <AlertTriangle className="w-5 h-5 text-yellow-500" />
                      )}
                    </div>

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => openDocuments(connector)}
                        className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded"
                        title="View Documents"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => syncConnector(connector.config_id)}
                        disabled={syncing === connector.config_id}
                        className="p-2 text-gray-500 hover:text-green-600 hover:bg-green-50 rounded disabled:opacity-50"
                        title="Sync Documents"
                      >
                        {syncing === connector.config_id ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <RefreshCw className="w-4 h-4" />
                        )}
                      </button>
                      <button
                        onClick={() => testConnection(connector.config_id)}
                        className="p-2 text-gray-500 hover:text-green-600 hover:bg-green-50 rounded"
                        title="Test Connection"
                      >
                        <Zap className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => openEditModal(connector)}
                        className="p-2 text-gray-500 hover:text-orange-600 hover:bg-orange-50 rounded"
                        title="Edit"
                      >
                        <Edit className="w-4 h-4" />
                      </button>
                      {!connector.is_default && (
                        <button
                          onClick={() => setAsDefault(connector.config_id)}
                          className="p-2 text-gray-500 hover:text-yellow-600 hover:bg-yellow-50 rounded"
                          title="Set as Default"
                        >
                          <Star className="w-4 h-4" />
                        </button>
                      )}
                      <button
                        onClick={() => deleteConnector(connector.config_id)}
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

      {/* Create/Edit Connector Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-4 border-b flex items-center justify-between">
              <h2 className="text-lg font-semibold">{editMode ? 'Edit RAG Connector' : 'Add RAG Connector'}</h2>
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
                          ? 'border-blue-500 bg-blue-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <span className="text-2xl">{PROVIDER_ICONS[type] || '⚙️'}</span>
                      <p className="text-xs mt-1 capitalize">{type.replace('_', ' ')}</p>
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
                  placeholder="Knowledge Base Documents"
                  className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>

              {/* Chunking Settings */}
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Chunking Strategy</label>
                  <select
                    value={form.chunking_strategy}
                    onChange={(e) => setForm({ ...form, chunking_strategy: e.target.value })}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  >
                    {CHUNKING_STRATEGIES.map((strategy) => (
                      <option key={strategy.value} value={strategy.value}>{strategy.label}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Chunk Size</label>
                  <input
                    type="number"
                    value={form.chunk_size}
                    onChange={(e) => setForm({ ...form, chunk_size: parseInt(e.target.value) })}
                    min={100}
                    max={10000}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Chunk Overlap</label>
                  <input
                    type="number"
                    value={form.chunk_overlap}
                    onChange={(e) => setForm({ ...form, chunk_overlap: parseInt(e.target.value) })}
                    min={0}
                    max={1000}
                    className="w-full px-3 py-2 border rounded-lg focus:ring-2 focus:ring-blue-500"
                  />
                </div>
              </div>

              {/* Connection Config */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Connection Configuration</label>
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
                  className="w-full px-3 py-2 border rounded-lg font-mono text-sm focus:ring-2 focus:ring-blue-500"
                />
                {schemas[form.provider_type] && (
                  <p className="text-xs text-gray-500 mt-1">
                    Required: {schemas[form.provider_type].required?.join(', ')}
                  </p>
                )}
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
                onClick={editMode ? updateConnector : createConnector}
                disabled={!form.name}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {editMode ? 'Update Connector' : 'Create Connector'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Documents Modal */}
      {showDocumentsModal && selectedConnector && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
            <div className="p-4 border-b flex items-center justify-between">
              <h2 className="text-lg font-semibold">Documents - {selectedConnector.name}</h2>
              <button onClick={() => setShowDocumentsModal(false)} className="text-gray-500 hover:text-gray-700">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto">
              {loadingDocuments ? (
                <div className="p-8 text-center">
                  <Loader2 className="w-8 h-8 animate-spin mx-auto text-blue-600" />
                </div>
              ) : documents.length === 0 ? (
                <div className="p-8 text-center">
                  <FileText className="w-12 h-12 mx-auto text-gray-400" />
                  <p className="mt-2 text-gray-500">No documents indexed yet</p>
                  <button
                    onClick={() => syncConnector(selectedConnector.config_id)}
                    className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                  >
                    Sync Documents
                  </button>
                </div>
              ) : (
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Document</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Type</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Chunks</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Status</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Indexed</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {documents.map((doc) => (
                      <tr key={doc.document_id} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <p className="font-medium text-sm">{doc.title || doc.source_id}</p>
                          {doc.source_path && (
                            <p className="text-xs text-gray-500 truncate max-w-xs">{doc.source_path}</p>
                          )}
                        </td>
                        <td className="px-4 py-3">
                          <span className="text-xs bg-gray-100 px-2 py-1 rounded">{doc.source_type}</span>
                        </td>
                        <td className="px-4 py-3 text-sm">{doc.chunk_count}</td>
                        <td className="px-4 py-3">
                          <span className={`text-xs px-2 py-1 rounded ${
                            doc.index_status === 'indexed' ? 'bg-green-100 text-green-800' :
                            doc.index_status === 'pending' ? 'bg-yellow-100 text-yellow-800' :
                            'bg-red-100 text-red-800'
                          }`}>
                            {doc.index_status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {formatDate(doc.indexed_at)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
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

export default RAGConnectorsPage;
