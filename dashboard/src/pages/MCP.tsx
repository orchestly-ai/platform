/**
 * MCP (Model Context Protocol) Page - Tool Ecosystem Management
 *
 * Allows users to:
 * - Register and manage MCP servers
 * - Discover and invoke tools
 * - Manage resources and prompts
 * - View analytics and usage statistics
 *
 * Backend: /mcp/*
 */

import { useState, useEffect } from 'react';
import {
  Wrench,
  Plus,
  Trash2,
  CheckCircle,
  AlertTriangle,
  X,
  Loader2,
  Server,
  Activity,
  Link2,
  Unlink,
  Play,
  Search,
  Zap,
  Copy,
  Terminal,
  Globe,
  FolderOpen,
  MessageSquare,
  AlertCircle,
} from 'lucide-react';

type TransportType = 'stdio' | 'http' | 'sse' | 'websocket';
type ServerStatus = 'disconnected' | 'connecting' | 'connected' | 'error';

interface MCPServer {
  server_id: string;
  organization_id: string;
  name: string;
  description?: string;
  transport_type: TransportType;
  status: ServerStatus;
  server_info?: Record<string, any>;
  capabilities?: Record<string, any>;
  protocol_version?: string;
  total_requests: number;
  total_errors: number;
  average_latency_ms?: number;
  last_connected_at?: string;
}

interface MCPTool {
  tool_id: string;
  server_id: string;
  tool_name: string;
  description?: string;
  input_schema: Record<string, any>;
  category?: string;
  tags?: string[];
  total_invocations: number;
  total_errors: number;
  average_duration_ms?: number;
}

interface MCPResource {
  resource_id: string;
  server_id: string;
  resource_uri: string;
  name: string;
  description?: string;
  mime_type?: string;
  size_bytes?: number;
  total_reads: number;
}

interface MCPPrompt {
  prompt_id: string;
  server_id: string;
  prompt_name: string;
  description?: string;
  arguments?: Array<{ name: string; description?: string; required?: boolean }>;
  total_uses: number;
}

interface ServerAnalytics {
  servers: {
    total: number;
    connected: number;
    total_requests: number;
    total_errors: number;
    average_latency_ms: number;
  };
  tools: {
    total: number;
    total_invocations: number;
    total_errors: number;
  };
}

const TRANSPORT_INFO: Record<TransportType, { name: string; icon: typeof Terminal; color: string }> = {
  stdio: { name: 'Standard I/O', icon: Terminal, color: 'var(--text-secondary)' },
  http: { name: 'HTTP', icon: Globe, color: 'var(--cyan)' },
  sse: { name: 'Server-Sent Events', icon: Activity, color: 'var(--green)' },
  websocket: { name: 'WebSocket', icon: Zap, color: 'var(--purple)' },
};

const STATUS_STYLES: Record<ServerStatus, { bg: string; color: string }> = {
  disconnected: { bg: 'color-mix(in srgb, var(--text-tertiary) 15%, transparent)', color: 'var(--text-tertiary)' },
  connecting: { bg: 'color-mix(in srgb, var(--yellow) 15%, transparent)', color: 'var(--yellow)' },
  connected: { bg: 'color-mix(in srgb, var(--green) 15%, transparent)', color: 'var(--green)' },
  error: { bg: 'color-mix(in srgb, var(--error) 15%, transparent)', color: 'var(--error)' },
};

const CAPABILITY_COLORS: Record<string, string> = {
  tools: 'var(--orange)',
  resources: 'var(--cyan)',
  prompts: 'var(--purple)',
  logging: 'var(--yellow)',
  sampling: 'var(--pink)',
};

const API_BASE = 'http://localhost:8000';

export function MCPPage() {
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'servers' | 'tools' | 'resources' | 'prompts'>('servers');
  const [servers, setServers] = useState<MCPServer[]>([]);
  const [tools, setTools] = useState<MCPTool[]>([]);
  const [resources, setResources] = useState<MCPResource[]>([]);
  const [prompts, setPrompts] = useState<MCPPrompt[]>([]);
  const [analytics, setAnalytics] = useState<ServerAnalytics | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  // Modal states
  const [showServerModal, setShowServerModal] = useState(false);
  const [showInvokeModal, setShowInvokeModal] = useState(false);
  const [selectedTool, setSelectedTool] = useState<MCPTool | null>(null);
  const [saving, setSaving] = useState(false);
  const [invoking, setInvoking] = useState(false);
  const [invocationResult, setInvocationResult] = useState<any>(null);

  // Form states
  const [serverForm, setServerForm] = useState({
    name: '',
    description: '',
    transport_type: 'http' as TransportType,
    endpoint_url: '',
    command: '',
    args: '',
    timeout_seconds: 30,
  });

  const [invokeArgs, setInvokeArgs] = useState<Record<string, any>>({});

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [serversRes, toolsRes, resourcesRes, promptsRes, analyticsRes] = await Promise.all([
        fetch(`${API_BASE}/mcp/servers`),
        fetch(`${API_BASE}/mcp/tools`),
        fetch(`${API_BASE}/mcp/resources`),
        fetch(`${API_BASE}/mcp/prompts`),
        fetch(`${API_BASE}/mcp/analytics/servers/summary`),
      ]);

      if (serversRes.ok) setServers(await serversRes.json());
      if (toolsRes.ok) setTools(await toolsRes.json());
      if (resourcesRes.ok) setResources(await resourcesRes.json());
      if (promptsRes.ok) setPrompts(await promptsRes.json());
      if (analyticsRes.ok) setAnalytics(await analyticsRes.json());
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const registerServer = async () => {
    if (!serverForm.name) {
      setToast({ message: 'Server name is required', type: 'error' });
      return;
    }

    if (serverForm.transport_type === 'http' && !serverForm.endpoint_url) {
      setToast({ message: 'Endpoint URL is required for HTTP transport', type: 'error' });
      return;
    }

    if (serverForm.transport_type === 'stdio' && !serverForm.command) {
      setToast({ message: 'Command is required for stdio transport', type: 'error' });
      return;
    }

    setSaving(true);
    try {
      const payload = {
        name: serverForm.name,
        description: serverForm.description || null,
        transport_type: serverForm.transport_type,
        endpoint_url: serverForm.transport_type !== 'stdio' ? serverForm.endpoint_url : null,
        command: serverForm.transport_type === 'stdio' ? serverForm.command : null,
        args: serverForm.transport_type === 'stdio' && serverForm.args
          ? serverForm.args.split(' ').filter(Boolean)
          : null,
        timeout_seconds: serverForm.timeout_seconds,
      };

      const response = await fetch(`${API_BASE}/mcp/servers`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        setToast({ message: 'MCP server registered successfully', type: 'success' });
        setShowServerModal(false);
        setServerForm({
          name: '',
          description: '',
          transport_type: 'http',
          endpoint_url: '',
          command: '',
          args: '',
          timeout_seconds: 30,
        });
        fetchData();
      } else {
        const error = await response.json();
        setToast({ message: error.detail || 'Failed to register server', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to register server', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const connectServer = async (serverId: string) => {
    try {
      const response = await fetch(`${API_BASE}/mcp/servers/${serverId}/connect`, {
        method: 'POST',
      });

      if (response.ok) {
        setToast({ message: 'Server connected successfully', type: 'success' });
        fetchData();
      } else {
        setToast({ message: 'Failed to connect to server', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to connect to server', type: 'error' });
    }
  };

  const disconnectServer = async (serverId: string) => {
    try {
      const response = await fetch(`${API_BASE}/mcp/servers/${serverId}/disconnect`, {
        method: 'POST',
      });

      if (response.ok) {
        setToast({ message: 'Server disconnected', type: 'success' });
        fetchData();
      } else {
        setToast({ message: 'Failed to disconnect server', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to disconnect server', type: 'error' });
    }
  };

  const deleteServer = async (serverId: string) => {
    if (!confirm('Are you sure you want to delete this MCP server? This will also remove all associated tools, resources, and prompts.')) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/mcp/servers/${serverId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        setToast({ message: 'Server deleted successfully', type: 'success' });
        fetchData();
      } else {
        setToast({ message: 'Failed to delete server', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to delete server', type: 'error' });
    }
  };

  const openInvokeModal = (tool: MCPTool) => {
    setSelectedTool(tool);
    setInvokeArgs({});
    setInvocationResult(null);
    setShowInvokeModal(true);
  };

  const invokeTool = async () => {
    if (!selectedTool) return;

    setInvoking(true);
    setInvocationResult(null);
    try {
      const response = await fetch(`${API_BASE}/mcp/tools/invoke`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tool_name: selectedTool.tool_name,
          arguments: invokeArgs,
          server_id: selectedTool.server_id,
        }),
      });

      const result = await response.json();
      setInvocationResult(result);

      if (result.success) {
        setToast({ message: 'Tool invoked successfully', type: 'success' });
      } else {
        setToast({ message: result.error_message || 'Tool invocation failed', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to invoke tool', type: 'error' });
    } finally {
      setInvoking(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setToast({ message: 'Copied to clipboard', type: 'success' });
  };

  const getServerName = (serverId: string) => {
    const server = servers.find(s => s.server_id === serverId);
    return server?.name || 'Unknown Server';
  };

  const filteredTools = tools.filter(tool =>
    tool.tool_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    tool.description?.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const tabs = [
    { key: 'servers' as const, label: `Servers (${servers.length})`, icon: Server },
    { key: 'tools' as const, label: `Tools (${tools.length})`, icon: Wrench },
    { key: 'resources' as const, label: `Resources (${resources.length})`, icon: FolderOpen },
    { key: 'prompts' as const, label: `Prompts (${prompts.length})`, icon: MessageSquare },
  ];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Wrench className="h-12 w-12 mx-auto mb-3 animate-pulse" style={{ color: 'var(--accent)' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Loading MCP tools...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Toast */}
      {toast && (
        <div
          className="fixed bottom-4 right-4 px-4 py-2 z-50 flex items-center gap-2 text-sm font-medium"
          style={{
            background: toast.type === 'success' ? 'var(--green)' : 'var(--error)',
            color: 'var(--bg-primary)',
            borderRadius: '0.5rem',
          }}
        >
          {toast.type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          {toast.message}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
            <Wrench className="h-7 w-7" style={{ color: 'var(--accent)' }} />
            MCP Tools
            <span
              className="text-xs font-normal px-2 py-0.5 rounded-full"
              style={{ background: 'color-mix(in srgb, var(--accent) 15%, transparent)', color: 'var(--accent)' }}
            >
              Model Context Protocol
            </span>
          </h1>
          <p className="mt-1" style={{ color: 'var(--text-secondary)' }}>
            Connect to MCP servers and discover tools for your AI agents
          </p>
        </div>
        <button
          onClick={() => setShowServerModal(true)}
          className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg"
          style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
        >
          <Plus className="h-4 w-4" />
          Register Server
        </button>
      </div>

      {/* Analytics Cards */}
      {analytics && (
        <div className="rounded-lg p-6" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
          <div className="flex items-center gap-2 mb-4">
            <Activity className="h-5 w-5" style={{ color: 'var(--cyan)' }} />
            <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Overview</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <div className="rounded-lg p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}>
              <div className="flex items-center gap-2 mb-2">
                <Server className="h-4 w-4" style={{ color: 'var(--orange)' }} />
                <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>MCP Servers</span>
              </div>
              <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{analytics.servers.total}</p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{analytics.servers.connected} connected</p>
            </div>
            <div className="rounded-lg p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}>
              <div className="flex items-center gap-2 mb-2">
                <Wrench className="h-4 w-4" style={{ color: 'var(--cyan)' }} />
                <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Available Tools</span>
              </div>
              <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{analytics.tools.total}</p>
            </div>
            <div className="rounded-lg p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}>
              <div className="flex items-center gap-2 mb-2">
                <Zap className="h-4 w-4" style={{ color: 'var(--green)' }} />
                <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Total Invocations</span>
              </div>
              <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{analytics.tools.total_invocations.toLocaleString()}</p>
            </div>
            <div className="rounded-lg p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}>
              <div className="flex items-center gap-2 mb-2">
                <Activity className="h-4 w-4" style={{ color: 'var(--purple)' }} />
                <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Avg Latency</span>
              </div>
              <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{analytics.servers.average_latency_ms?.toFixed(0) || 0}ms</p>
            </div>
            <div className="rounded-lg p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}>
              <div className="flex items-center gap-2 mb-2">
                <AlertTriangle className="h-4 w-4" style={{ color: 'var(--error)' }} />
                <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>Error Rate</span>
              </div>
              <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>
                {analytics.tools.total_invocations > 0
                  ? ((analytics.tools.total_errors / analytics.tools.total_invocations) * 100).toFixed(2)
                  : 0}%
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tabs + Content */}
      <div className="rounded-lg overflow-hidden" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
        <div className="flex" style={{ borderBottom: '1px solid var(--border-primary)', background: 'var(--bg-tertiary)' }}>
          {tabs.map((tab) => {
            const TabIcon = tab.icon;
            const isActive = activeTab === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className="px-5 py-3 font-medium text-sm flex items-center gap-2 transition-colors"
                style={
                  isActive
                    ? { color: 'var(--accent)', borderBottom: '2px solid var(--accent)', background: 'var(--bg-secondary)' }
                    : { color: 'var(--text-tertiary)', borderBottom: '2px solid transparent' }
                }
              >
                <TabIcon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        <div className="p-6">
          {/* Servers Tab */}
          {activeTab === 'servers' && (
            <div>
              {servers.length === 0 ? (
                <div className="text-center py-12">
                  <Server className="h-12 w-12 mx-auto mb-3" style={{ color: 'var(--text-tertiary)' }} />
                  <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>No MCP servers registered</h3>
                  <p className="text-sm mb-5" style={{ color: 'var(--text-secondary)' }}>
                    Register an MCP server to discover tools for your agents
                  </p>
                  <button
                    onClick={() => setShowServerModal(true)}
                    className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg mx-auto"
                    style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
                  >
                    <Plus size={14} /> Register Your First Server
                  </button>
                </div>
              ) : (
                <div className="space-y-4">
                  {servers.map((server) => {
                    const TransportIcon = TRANSPORT_INFO[server.transport_type]?.icon || Terminal;
                    const transportColor = TRANSPORT_INFO[server.transport_type]?.color || 'var(--text-secondary)';
                    const statusStyle = STATUS_STYLES[server.status] || STATUS_STYLES.disconnected;
                    return (
                      <div
                        key={server.server_id}
                        className="rounded-lg p-4"
                        style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-4">
                            <div
                              className="w-12 h-12 rounded-lg flex items-center justify-center"
                              style={{ background: `color-mix(in srgb, ${transportColor} 15%, transparent)` }}
                            >
                              <TransportIcon className="w-6 h-6" style={{ color: transportColor }} />
                            </div>
                            <div>
                              <div className="flex items-center gap-2">
                                <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>{server.name}</h3>
                                <span
                                  className="text-xs px-2 py-0.5 rounded-md font-medium"
                                  style={{ background: statusStyle.bg, color: statusStyle.color }}
                                >
                                  {server.status}
                                </span>
                              </div>
                              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{server.description || 'No description'}</p>
                              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                                {TRANSPORT_INFO[server.transport_type]?.name}
                                {server.protocol_version && ` \u2022 v${server.protocol_version}`}
                              </p>
                            </div>
                          </div>

                          <div className="flex items-center gap-6">
                            {/* Stats */}
                            <div className="hidden md:flex items-center gap-4">
                              <div className="rounded-lg px-3 py-2 text-center" style={{ background: 'var(--bg-secondary)' }}>
                                <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Requests</p>
                                <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{server.total_requests.toLocaleString()}</p>
                              </div>
                              <div className="rounded-lg px-3 py-2 text-center" style={{ background: 'var(--bg-secondary)' }}>
                                <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Errors</p>
                                <p className="text-sm font-semibold" style={{ color: server.total_errors > 0 ? 'var(--error)' : 'var(--text-primary)' }}>{server.total_errors.toLocaleString()}</p>
                              </div>
                              {server.average_latency_ms != null && (
                                <div className="rounded-lg px-3 py-2 text-center" style={{ background: 'var(--bg-secondary)' }}>
                                  <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>Latency</p>
                                  <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>{server.average_latency_ms.toFixed(0)}ms</p>
                                </div>
                              )}
                            </div>

                            {/* Actions */}
                            <div className="flex items-center gap-2">
                              {server.status === 'disconnected' ? (
                                <button
                                  onClick={() => connectServer(server.server_id)}
                                  className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg"
                                  style={{ background: 'color-mix(in srgb, var(--green) 15%, transparent)', color: 'var(--green)', border: '1px solid color-mix(in srgb, var(--green) 30%, transparent)' }}
                                >
                                  <Link2 className="w-4 h-4" />
                                  Connect
                                </button>
                              ) : (
                                <button
                                  onClick={() => disconnectServer(server.server_id)}
                                  className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg"
                                  style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-primary)' }}
                                >
                                  <Unlink className="w-4 h-4" />
                                  Disconnect
                                </button>
                              )}
                              <button
                                onClick={() => deleteServer(server.server_id)}
                                className="flex items-center justify-center p-1.5 rounded-lg"
                                style={{ background: 'color-mix(in srgb, var(--error) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--error) 25%, transparent)' }}
                                title="Delete Server"
                              >
                                <Trash2 className="w-4 h-4" style={{ color: 'var(--error)' }} />
                              </button>
                            </div>
                          </div>
                        </div>

                        {/* Capabilities */}
                        {server.capabilities && Object.keys(server.capabilities).length > 0 && (
                          <div className="mt-4 pt-4" style={{ borderTop: '1px solid var(--border-primary)' }}>
                            <p className="text-xs mb-2" style={{ color: 'var(--text-tertiary)' }}>Capabilities:</p>
                            <div className="flex flex-wrap gap-2">
                              {Object.entries(server.capabilities).map(([key, value]) => {
                                if (!value) return null;
                                const capColor = CAPABILITY_COLORS[key] || 'var(--accent)';
                                return (
                                  <span
                                    key={key}
                                    className="text-xs px-2 py-1 rounded-md font-medium"
                                    style={{ background: `color-mix(in srgb, ${capColor} 15%, transparent)`, color: capColor }}
                                  >
                                    {key}
                                  </span>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}

          {/* Tools Tab */}
          {activeTab === 'tools' && (
            <div>
              {/* Search */}
              <div className="mb-4">
                <div className="relative">
                  <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2" style={{ color: 'var(--text-tertiary)' }} />
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search tools..."
                    className="w-full px-3 py-2 pl-10 rounded-lg text-sm"
                    style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                  />
                </div>
              </div>

              {filteredTools.length === 0 ? (
                <div className="text-center py-12">
                  <Wrench className="h-12 w-12 mx-auto mb-3" style={{ color: 'var(--text-tertiary)' }} />
                  <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
                    {searchQuery ? 'No tools match your search' : 'No tools discovered yet'}
                  </h3>
                  {!searchQuery && (
                    <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Connect to MCP servers to discover available tools</p>
                  )}
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {filteredTools.map((tool) => (
                    <div
                      key={tool.tool_id}
                      className="rounded-lg p-4"
                      style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 mb-1">
                            <h3 className="font-semibold font-mono text-sm truncate" style={{ color: 'var(--text-primary)' }}>{tool.tool_name}</h3>
                            {tool.category && (
                              <span
                                className="text-xs px-2 py-0.5 rounded-md font-medium flex-shrink-0"
                                style={{ background: 'color-mix(in srgb, var(--cyan) 15%, transparent)', color: 'var(--cyan)' }}
                              >
                                {tool.category}
                              </span>
                            )}
                          </div>
                          <p className="text-sm line-clamp-2" style={{ color: 'var(--text-secondary)' }}>{tool.description || 'No description'}</p>
                          <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Server: {getServerName(tool.server_id)}</p>
                        </div>
                        <button
                          onClick={() => openInvokeModal(tool)}
                          className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg ml-3 flex-shrink-0"
                          style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
                        >
                          <Play className="w-4 h-4" />
                          Invoke
                        </button>
                      </div>

                      {/* Tags */}
                      {tool.tags && tool.tags.length > 0 && (
                        <div className="flex flex-wrap gap-1 mb-3">
                          {tool.tags.map((tag, i) => (
                            <span
                              key={i}
                              className="text-xs px-2 py-0.5 rounded-md"
                              style={{ background: 'color-mix(in srgb, var(--purple) 15%, transparent)', color: 'var(--purple)' }}
                            >
                              {tag}
                            </span>
                          ))}
                        </div>
                      )}

                      {/* Stats */}
                      <div className="flex items-center gap-4 text-xs pt-3" style={{ borderTop: '1px solid var(--border-primary)', color: 'var(--text-tertiary)' }}>
                        <span>{tool.total_invocations.toLocaleString()} invocations</span>
                        <span style={tool.total_errors > 0 ? { color: 'var(--error)' } : {}}>{tool.total_errors} errors</span>
                        {tool.average_duration_ms && (
                          <span>{tool.average_duration_ms.toFixed(0)}ms avg</span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Resources Tab */}
          {activeTab === 'resources' && (
            <div>
              {resources.length === 0 ? (
                <div className="text-center py-12">
                  <FolderOpen className="h-12 w-12 mx-auto mb-3" style={{ color: 'var(--text-tertiary)' }} />
                  <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>No resources discovered</h3>
                  <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Connect to MCP servers to discover available resources</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {resources.map((resource) => (
                    <div
                      key={resource.resource_id}
                      className="rounded-lg p-4"
                      style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div
                            className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                            style={{ background: 'color-mix(in srgb, var(--cyan) 15%, transparent)' }}
                          >
                            <FolderOpen className="w-5 h-5" style={{ color: 'var(--cyan)' }} />
                          </div>
                          <div>
                            <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>{resource.name}</h3>
                            <p
                              className="text-sm font-mono px-2 py-0.5 rounded mt-1 inline-block"
                              style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}
                            >
                              {resource.resource_uri}
                            </p>
                            <div className="flex items-center gap-3 text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>
                              <span>Server: {getServerName(resource.server_id)}</span>
                              {resource.mime_type && (
                                <span
                                  className="px-1.5 py-0.5 rounded"
                                  style={{ background: 'color-mix(in srgb, var(--orange) 15%, transparent)', color: 'var(--orange)' }}
                                >
                                  {resource.mime_type}
                                </span>
                              )}
                              {resource.size_bytes != null && <span>{(resource.size_bytes / 1024).toFixed(1)}KB</span>}
                              <span>{resource.total_reads} reads</span>
                            </div>
                          </div>
                        </div>
                        <button
                          onClick={() => copyToClipboard(resource.resource_uri)}
                          className="flex items-center justify-center p-2 rounded-lg"
                          style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}
                          title="Copy URI"
                        >
                          <Copy className="w-4 h-4" style={{ color: 'var(--text-secondary)' }} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Prompts Tab */}
          {activeTab === 'prompts' && (
            <div>
              {prompts.length === 0 ? (
                <div className="text-center py-12">
                  <MessageSquare className="h-12 w-12 mx-auto mb-3" style={{ color: 'var(--text-tertiary)' }} />
                  <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>No prompts discovered</h3>
                  <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>Connect to MCP servers to discover available prompts</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {prompts.map((prompt) => (
                    <div
                      key={prompt.prompt_id}
                      className="rounded-lg p-4"
                      style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <h3 className="font-semibold font-mono" style={{ color: 'var(--text-primary)' }}>{prompt.prompt_name}</h3>
                          <p className="text-sm mt-1" style={{ color: 'var(--text-secondary)' }}>{prompt.description || 'No description'}</p>
                          <div className="flex items-center gap-4 text-xs mt-2" style={{ color: 'var(--text-tertiary)' }}>
                            <span>Server: {getServerName(prompt.server_id)}</span>
                            <span>{prompt.total_uses} uses</span>
                          </div>
                        </div>
                        {prompt.arguments && prompt.arguments.length > 0 && (
                          <div className="text-sm" style={{ color: 'var(--text-tertiary)' }}>
                            {prompt.arguments.length} argument{prompt.arguments.length !== 1 ? 's' : ''}
                          </div>
                        )}
                      </div>

                      {/* Arguments */}
                      {prompt.arguments && prompt.arguments.length > 0 && (
                        <div className="mt-3 pt-3" style={{ borderTop: '1px solid var(--border-primary)' }}>
                          <p className="text-xs mb-2" style={{ color: 'var(--text-tertiary)' }}>Arguments:</p>
                          <div className="flex flex-wrap gap-2">
                            {prompt.arguments.map((arg, i) => (
                              <span
                                key={i}
                                className="text-xs px-2 py-1 rounded-md font-medium"
                                style={
                                  arg.required
                                    ? { background: 'color-mix(in srgb, var(--error) 15%, transparent)', color: 'var(--error)', border: '1px solid color-mix(in srgb, var(--error) 30%, transparent)' }
                                    : { background: 'var(--bg-tertiary)', color: 'var(--text-secondary)', border: '1px solid var(--border-primary)' }
                                }
                              >
                                {arg.name}
                                {arg.required && '*'}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Register Server Modal */}
      {showServerModal && (
        <div className="fixed inset-0 flex items-center justify-center z-50" style={{ background: 'rgba(0, 0, 0, 0.5)' }}>
          <div className="w-full max-w-lg rounded-lg overflow-hidden" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
            <div className="p-4 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border-primary)' }}>
              <h2 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <Server className="w-5 h-5" style={{ color: 'var(--accent)' }} />
                Register MCP Server
              </h2>
              <button onClick={() => setShowServerModal(false)} style={{ color: 'var(--text-tertiary)' }}>
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>
                  Server Name <span style={{ color: 'var(--error)' }}>*</span>
                </label>
                <input
                  type="text"
                  value={serverForm.name}
                  onChange={(e) => setServerForm({ ...serverForm, name: e.target.value })}
                  placeholder="GitHub MCP Server"
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Description</label>
                <input
                  type="text"
                  value={serverForm.description}
                  onChange={(e) => setServerForm({ ...serverForm, description: e.target.value })}
                  placeholder="Access GitHub repositories and issues"
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Transport Type</label>
                <select
                  value={serverForm.transport_type}
                  onChange={(e) => setServerForm({ ...serverForm, transport_type: e.target.value as TransportType })}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                >
                  <option value="http">HTTP</option>
                  <option value="sse">Server-Sent Events (SSE)</option>
                  <option value="websocket">WebSocket</option>
                  <option value="stdio">Standard I/O (Local Process)</option>
                </select>
              </div>

              {serverForm.transport_type !== 'stdio' ? (
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>
                    Endpoint URL <span style={{ color: 'var(--error)' }}>*</span>
                  </label>
                  <input
                    type="text"
                    value={serverForm.endpoint_url}
                    onChange={(e) => setServerForm({ ...serverForm, endpoint_url: e.target.value })}
                    placeholder="https://mcp.example.com"
                    className="w-full px-3 py-2 rounded-lg text-sm"
                    style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                  />
                </div>
              ) : (
                <>
                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>
                      Command <span style={{ color: 'var(--error)' }}>*</span>
                    </label>
                    <input
                      type="text"
                      value={serverForm.command}
                      onChange={(e) => setServerForm({ ...serverForm, command: e.target.value })}
                      placeholder="npx"
                      className="w-full px-3 py-2 rounded-lg text-sm"
                      style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Arguments</label>
                    <input
                      type="text"
                      value={serverForm.args}
                      onChange={(e) => setServerForm({ ...serverForm, args: e.target.value })}
                      placeholder="-y @modelcontextprotocol/server-github"
                      className="w-full px-3 py-2 rounded-lg text-sm"
                      style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                    />
                    <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>Space-separated arguments</p>
                  </div>
                </>
              )}

              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Timeout (seconds)</label>
                <input
                  type="number"
                  value={serverForm.timeout_seconds}
                  onChange={(e) => setServerForm({ ...serverForm, timeout_seconds: parseInt(e.target.value) || 30 })}
                  min={5}
                  max={300}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                />
              </div>
            </div>

            <div className="p-4 flex justify-end gap-3" style={{ borderTop: '1px solid var(--border-primary)', background: 'var(--bg-tertiary)' }}>
              <button
                onClick={() => setShowServerModal(false)}
                className="px-3 py-1.5 text-sm font-medium rounded-lg"
                style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}
              >
                Cancel
              </button>
              <button
                onClick={registerServer}
                disabled={saving}
                className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg disabled:opacity-50"
                style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                Register Server
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Invoke Tool Modal */}
      {showInvokeModal && selectedTool && (
        <div className="fixed inset-0 flex items-center justify-center z-50" style={{ background: 'rgba(0, 0, 0, 0.5)' }}>
          <div
            className="w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col rounded-lg"
            style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}
          >
            <div className="p-4 flex items-center justify-between" style={{ borderBottom: '1px solid var(--border-primary)' }}>
              <h2 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <Play className="w-5 h-5" style={{ color: 'var(--accent)' }} />
                Invoke Tool: <span className="font-mono" style={{ color: 'var(--accent)' }}>{selectedTool.tool_name}</span>
              </h2>
              <button onClick={() => setShowInvokeModal(false)} style={{ color: 'var(--text-tertiary)' }}>
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 flex-1 overflow-y-auto space-y-4">
              {/* Tool Description */}
              {selectedTool.description && (
                <div className="rounded-lg p-3" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
                  <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{selectedTool.description}</p>
                </div>
              )}

              {/* Input Schema */}
              <div>
                <h3 className="font-medium mb-3" style={{ color: 'var(--text-primary)' }}>Arguments</h3>
                {selectedTool.input_schema?.properties ? (
                  <div className="space-y-3">
                    {Object.entries(selectedTool.input_schema.properties).map(([key, schema]: [string, any]) => (
                      <div key={key}>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>
                          {key}
                          {selectedTool.input_schema.required?.includes(key) && (
                            <span className="ml-1" style={{ color: 'var(--error)' }}>*</span>
                          )}
                          {schema.description && (
                            <span className="font-normal ml-2" style={{ color: 'var(--text-tertiary)' }}>{schema.description}</span>
                          )}
                        </label>
                        {schema.type === 'boolean' ? (
                          <select
                            value={invokeArgs[key]?.toString() || ''}
                            onChange={(e) => setInvokeArgs({ ...invokeArgs, [key]: e.target.value === 'true' })}
                            className="w-full px-3 py-2 rounded-lg text-sm"
                            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                          >
                            <option value="">Select...</option>
                            <option value="true">true</option>
                            <option value="false">false</option>
                          </select>
                        ) : schema.type === 'number' || schema.type === 'integer' ? (
                          <input
                            type="number"
                            value={invokeArgs[key] || ''}
                            onChange={(e) => setInvokeArgs({ ...invokeArgs, [key]: parseFloat(e.target.value) })}
                            placeholder={schema.example?.toString() || `Enter ${key}`}
                            className="w-full px-3 py-2 rounded-lg text-sm"
                            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                          />
                        ) : schema.enum ? (
                          <select
                            value={invokeArgs[key] || ''}
                            onChange={(e) => setInvokeArgs({ ...invokeArgs, [key]: e.target.value })}
                            className="w-full px-3 py-2 rounded-lg text-sm"
                            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                          >
                            <option value="">Select...</option>
                            {schema.enum.map((opt: string) => (
                              <option key={opt} value={opt}>{opt}</option>
                            ))}
                          </select>
                        ) : (
                          <input
                            type="text"
                            value={invokeArgs[key] || ''}
                            onChange={(e) => setInvokeArgs({ ...invokeArgs, [key]: e.target.value })}
                            placeholder={schema.example || `Enter ${key}`}
                            className="w-full px-3 py-2 rounded-lg text-sm"
                            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                          />
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="rounded-lg p-4" style={{ background: 'var(--bg-tertiary)', border: '1px solid var(--border-primary)' }}>
                    <p className="text-sm mb-2" style={{ color: 'var(--text-secondary)' }}>Raw JSON arguments:</p>
                    <textarea
                      value={JSON.stringify(invokeArgs, null, 2)}
                      onChange={(e) => {
                        try {
                          setInvokeArgs(JSON.parse(e.target.value));
                        } catch {}
                      }}
                      rows={5}
                      className="w-full px-3 py-2 rounded-lg font-mono text-sm"
                      style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                      placeholder="{}"
                    />
                  </div>
                )}
              </div>

              {/* Result */}
              {invocationResult && (
                <div>
                  <h3 className="font-medium mb-3 flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                    Result
                    {invocationResult.success ? (
                      <CheckCircle className="w-4 h-4" style={{ color: 'var(--green)' }} />
                    ) : (
                      <AlertTriangle className="w-4 h-4" style={{ color: 'var(--error)' }} />
                    )}
                    {invocationResult.duration_ms && (
                      <span className="text-xs font-normal" style={{ color: 'var(--text-tertiary)' }}>
                        ({invocationResult.duration_ms.toFixed(0)}ms)
                      </span>
                    )}
                  </h3>
                  <pre
                    className="p-4 rounded-lg overflow-auto text-sm font-mono"
                    style={
                      invocationResult.success
                        ? { background: 'color-mix(in srgb, var(--green) 10%, var(--bg-primary))', color: 'var(--text-primary)', border: '1px solid color-mix(in srgb, var(--green) 30%, transparent)' }
                        : { background: 'color-mix(in srgb, var(--error) 10%, var(--bg-primary))', color: 'var(--text-primary)', border: '1px solid color-mix(in srgb, var(--error) 30%, transparent)' }
                    }
                  >
                    {invocationResult.success
                      ? JSON.stringify(invocationResult.result, null, 2)
                      : invocationResult.error_message || 'Unknown error'
                    }
                  </pre>
                </div>
              )}
            </div>

            <div className="p-4 flex justify-end gap-3" style={{ borderTop: '1px solid var(--border-primary)', background: 'var(--bg-tertiary)' }}>
              <button
                onClick={() => setShowInvokeModal(false)}
                className="px-3 py-1.5 text-sm font-medium rounded-lg"
                style={{ background: 'var(--bg-primary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}
              >
                Close
              </button>
              <button
                onClick={invokeTool}
                disabled={invoking}
                className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg disabled:opacity-50"
                style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
              >
                {invoking ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Invoking...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Invoke Tool
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MCPPage;
