/**
 * Webhooks Management Page
 *
 * View webhook events, configure providers, and manage handlers.
 */

import { useState, useEffect } from 'react';
import {
  Webhook,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  AlertTriangle,
  Plus,
  Trash2,
  Copy,
  Eye,
  X,
  Loader2,
  Filter,
  Settings,
  Zap,
} from 'lucide-react';
import { api } from '@/services/api';

type TabType = 'events' | 'configs' | 'handlers';

interface WebhookEvent {
  event_id: string;
  provider: string;
  event_type: string;
  payload: Record<string, unknown>;
  status: string;
  received_at: string;
  processed_at?: string;
  error_message?: string;
  retry_count: number;
}

interface WebhookConfig {
  provider: string;
  enabled: boolean;
  has_secret: boolean;
  signature_header: string;
  event_types: string[];
}

interface WebhookHandler {
  event_type: string;
  handler_type: string;
  handler_config: Record<string, unknown>;
  enabled: boolean;
}

// Provider display info
const PROVIDERS = {
  stripe: { name: 'Stripe', color: '#635bff' },
  github: { name: 'GitHub', color: '#24292e' },
  slack: { name: 'Slack', color: '#4a154b' },
  discord: { name: 'Discord', color: '#5865f2' },
  hubspot: { name: 'HubSpot', color: '#ff7a59' },
};

export function WebhooksPage() {
  const [activeTab, setActiveTab] = useState<TabType>('events');
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Events state
  const [events, setEvents] = useState<WebhookEvent[]>([]);
  const [loadingEvents, setLoadingEvents] = useState(true);
  const [eventFilter, setEventFilter] = useState({ provider: '', status: '' });
  const [selectedEvent, setSelectedEvent] = useState<WebhookEvent | null>(null);

  // Configs state
  const [configs, setConfigs] = useState<WebhookConfig[]>([]);
  const [loadingConfigs, setLoadingConfigs] = useState(true);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [editingConfig, setEditingConfig] = useState<string | null>(null);
  const [configForm, setConfigForm] = useState({
    provider: '',
    secret_key: '',
    enabled: true,
    event_types: '',
  });

  // Handlers state
  const [handlers, setHandlers] = useState<WebhookHandler[]>([]);
  const [loadingHandlers, setLoadingHandlers] = useState(true);
  const [showHandlerModal, setShowHandlerModal] = useState(false);
  const [handlerForm, setHandlerForm] = useState({
    event_type: '',
    handler_type: 'workflow',
    workflow_id: '',
    http_url: '',
    enabled: true,
  });

  // Toast auto-dismiss
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // Fetch data when tab changes
  useEffect(() => {
    if (activeTab === 'events') {
      fetchEvents();
    } else if (activeTab === 'configs') {
      fetchConfigs();
    } else if (activeTab === 'handlers') {
      fetchHandlers();
    }
  }, [activeTab, eventFilter]);

  const fetchEvents = async () => {
    setLoadingEvents(true);
    try {
      const data = await api.getWebhookEvents({
        provider: eventFilter.provider || undefined,
        status: eventFilter.status || undefined,
        limit: 100,
      });
      setEvents(data.events);
    } catch (error) {
      console.error('Error fetching events:', error);
      setToast({ message: 'Failed to load webhook events', type: 'error' });
    } finally {
      setLoadingEvents(false);
    }
  };

  const fetchConfigs = async () => {
    setLoadingConfigs(true);
    try {
      const data = await api.getWebhookConfigs();
      setConfigs(data);
    } catch (error) {
      console.error('Error fetching configs:', error);
      setToast({ message: 'Failed to load webhook configurations', type: 'error' });
    } finally {
      setLoadingConfigs(false);
    }
  };

  const fetchHandlers = async () => {
    setLoadingHandlers(true);
    try {
      const data = await api.getWebhookHandlers();
      setHandlers(data.handlers);
    } catch (error) {
      console.error('Error fetching handlers:', error);
      setToast({ message: 'Failed to load webhook handlers', type: 'error' });
    } finally {
      setLoadingHandlers(false);
    }
  };

  const retryEvent = async (eventId: string) => {
    try {
      await api.retryWebhookEvent(eventId);
      setToast({ message: 'Event retry initiated', type: 'success' });
      fetchEvents();
    } catch (error) {
      console.error('Error retrying event:', error);
      setToast({ message: 'Failed to retry event', type: 'error' });
    }
  };

  const saveConfig = async () => {
    if (!configForm.provider) {
      setToast({ message: 'Please select a provider', type: 'error' });
      return;
    }

    try {
      const eventTypes = configForm.event_types
        .split(',')
        .map(s => s.trim())
        .filter(s => s.length > 0);

      await api.configureWebhook(configForm.provider, {
        secret_key: configForm.secret_key || undefined,
        enabled: configForm.enabled,
        event_types: eventTypes.length > 0 ? eventTypes : undefined,
      });

      setShowConfigModal(false);
      setConfigForm({ provider: '', secret_key: '', enabled: true, event_types: '' });
      await fetchConfigs();
      setToast({ message: `Webhook configuration saved for ${configForm.provider}`, type: 'success' });
    } catch (error) {
      console.error('Error saving config:', error);
      setToast({ message: 'Failed to save configuration', type: 'error' });
    }
  };

  const toggleProviderEnabled = async (provider: string, currentEnabled: boolean) => {
    try {
      await api.configureWebhook(provider, {
        enabled: !currentEnabled,
      });
      await fetchConfigs();
      setToast({
        message: `${provider} webhook ${!currentEnabled ? 'enabled' : 'disabled'}`,
        type: 'success'
      });
    } catch (error) {
      console.error('Error toggling provider:', error);
      setToast({ message: 'Failed to update provider', type: 'error' });
    }
  };

  const saveHandler = async () => {
    if (!handlerForm.event_type || !handlerForm.handler_type) {
      setToast({ message: 'Please fill in required fields', type: 'error' });
      return;
    }

    try {
      const handlerConfig: Record<string, unknown> = {};
      if (handlerForm.handler_type === 'workflow') {
        handlerConfig.workflow_id = handlerForm.workflow_id;
      } else if (handlerForm.handler_type === 'http') {
        handlerConfig.url = handlerForm.http_url;
      }

      await api.registerWebhookHandler({
        event_type: handlerForm.event_type,
        handler_type: handlerForm.handler_type,
        handler_config: handlerConfig,
        enabled: handlerForm.enabled,
      });

      setShowHandlerModal(false);
      setHandlerForm({
        event_type: '',
        handler_type: 'workflow',
        workflow_id: '',
        http_url: '',
        enabled: true,
      });
      await fetchHandlers();
      setToast({ message: 'Handler registered successfully', type: 'success' });
    } catch (error) {
      console.error('Error registering handler:', error);
      setToast({ message: 'Failed to register handler', type: 'error' });
    }
  };

  const deleteHandler = async (eventType: string, handlerType: string) => {
    if (!confirm(`Remove ${handlerType} handler for ${eventType}?`)) return;

    try {
      await api.unregisterWebhookHandler(eventType, handlerType);
      await fetchHandlers();
      setToast({ message: 'Handler removed', type: 'success' });
    } catch (error) {
      console.error('Error removing handler:', error);
      setToast({ message: 'Failed to remove handler', type: 'error' });
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setToast({ message: 'Copied to clipboard', type: 'success' });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle size={16} className="text-green-500" />;
      case 'failed':
        return <XCircle size={16} className="text-red-500" />;
      case 'pending':
      case 'received':
        return <Clock size={16} className="text-yellow-500" />;
      case 'retrying':
        return <RefreshCw size={16} className="text-blue-500 animate-spin" />;
      default:
        return <AlertTriangle size={16} className="text-gray-400" />;
    }
  };

  const getStatusBadgeStyle = (status: string) => {
    switch (status) {
      case 'completed':
        return { background: 'rgba(16, 185, 129, 0.1)', color: '#10b981' };
      case 'failed':
        return { background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444' };
      case 'pending':
      case 'received':
        return { background: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b' };
      case 'retrying':
        return { background: 'rgba(99, 102, 241, 0.1)', color: '#6366f1' };
      default:
        return { background: 'rgba(107, 114, 128, 0.1)', color: '#6b7280' };
    }
  };

  const tabs = [
    { id: 'events' as const, label: 'Events', icon: Zap, count: events.length },
    { id: 'configs' as const, label: 'Providers', icon: Settings, count: configs.length },
    { id: 'handlers' as const, label: 'Handlers', icon: Webhook, count: handlers.length },
  ];

  return (
    <div>
      {/* Toast */}
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

      {/* Page Header */}
      <div className="page-header">
        <div className="page-title">
          <h1>Webhooks</h1>
          <p>Monitor incoming webhooks and configure event handlers</p>
        </div>
      </div>

      {/* Tab Navigation */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', borderBottom: '1px solid var(--border-color)', paddingBottom: '16px' }}>
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              padding: '10px 20px',
              border: 'none',
              borderRadius: '8px',
              background: activeTab === tab.id ? 'var(--primary-color)' : 'transparent',
              color: activeTab === tab.id ? 'white' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontSize: '14px',
              fontWeight: 500,
              transition: 'all 0.2s',
            }}
          >
            <tab.icon size={18} />
            {tab.label}
            {tab.count > 0 && (
              <span style={{
                padding: '2px 8px',
                borderRadius: '10px',
                background: activeTab === tab.id ? 'rgba(255,255,255,0.2)' : 'var(--bg-secondary)',
                fontSize: '12px',
              }}>
                {tab.count}
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Events Tab */}
      {activeTab === 'events' && (
        <div>
          {/* Filters */}
          <div style={{ display: 'flex', gap: '12px', marginBottom: '20px', alignItems: 'center' }}>
            <Filter size={18} style={{ color: 'var(--text-muted)' }} />
            <select
              value={eventFilter.provider}
              onChange={(e) => setEventFilter({ ...eventFilter, provider: e.target.value })}
              style={{ padding: '8px 12px', border: '1px solid var(--border-color)', borderRadius: '6px', fontSize: '14px' }}
            >
              <option value="">All Providers</option>
              {Object.entries(PROVIDERS).map(([id, info]) => (
                <option key={id} value={id}>{info.name}</option>
              ))}
            </select>
            <select
              value={eventFilter.status}
              onChange={(e) => setEventFilter({ ...eventFilter, status: e.target.value })}
              style={{ padding: '8px 12px', border: '1px solid var(--border-color)', borderRadius: '6px', fontSize: '14px' }}
            >
              <option value="">All Statuses</option>
              <option value="received">Received</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="retrying">Retrying</option>
            </select>
            <button
              className="btn-secondary"
              style={{ padding: '8px 12px' }}
              onClick={fetchEvents}
            >
              <RefreshCw size={16} />
            </button>
          </div>

          {loadingEvents ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
              <Loader2 size={24} className="animate-spin" />
            </div>
          ) : events.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
              <Webhook size={48} style={{ opacity: 0.3, marginBottom: '16px' }} />
              <p>No webhook events yet.</p>
              <p style={{ fontSize: '14px' }}>Events will appear here when webhooks are received.</p>
            </div>
          ) : (
            <div className="chart-card" style={{ padding: 0 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-secondary)' }}>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Event</th>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Provider</th>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Status</th>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Received</th>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {events.map((event) => (
                    <tr key={event.event_id} style={{ borderTop: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '14px 16px' }}>
                        <div>
                          <code style={{ fontSize: '13px', fontWeight: 500 }}>{event.event_type}</code>
                          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                            {event.event_id.slice(0, 12)}...
                          </div>
                        </div>
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '4px 10px',
                          borderRadius: '4px',
                          background: 'var(--bg-secondary)',
                          fontSize: '13px',
                          fontWeight: 500,
                        }}>
                          {(PROVIDERS as Record<string, { name: string }>)[event.provider]?.name || event.provider}
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '4px 10px',
                          borderRadius: '4px',
                          fontSize: '12px',
                          fontWeight: 500,
                          textTransform: 'capitalize',
                          ...getStatusBadgeStyle(event.status),
                        }}>
                          {getStatusIcon(event.status)}
                          {event.status}
                          {event.retry_count > 0 && ` (${event.retry_count})`}
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                        {new Date(event.received_at).toLocaleString()}
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <div style={{ display: 'flex', gap: '8px' }}>
                          <button
                            className="btn-secondary"
                            style={{ padding: '6px' }}
                            onClick={() => setSelectedEvent(event)}
                            title="View details"
                          >
                            <Eye size={14} />
                          </button>
                          {event.status === 'failed' && (
                            <button
                              className="btn-secondary"
                              style={{ padding: '6px' }}
                              onClick={() => retryEvent(event.event_id)}
                              title="Retry"
                            >
                              <RefreshCw size={14} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Providers Tab */}
      {activeTab === 'configs' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <p style={{ color: 'var(--text-secondary)', margin: 0 }}>Configure webhook endpoints and secrets for each provider</p>
            <button className="btn-primary" onClick={() => {
              setEditingConfig(null);
              setConfigForm({ provider: '', secret_key: '', enabled: true, event_types: '' });
              setShowConfigModal(true);
            }}>
              <Plus size={18} />Configure Provider
            </button>
          </div>

          {loadingConfigs ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
              <Loader2 size={24} className="animate-spin" />
            </div>
          ) : configs.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
              <Settings size={48} style={{ opacity: 0.3, marginBottom: '16px' }} />
              <p>No webhook providers configured yet.</p>
            </div>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))', gap: '16px' }}>
              {configs.map((config) => {
                const providerInfo = (PROVIDERS as Record<string, { name: string; color: string }>)[config.provider];
                return (
                  <div key={config.provider} className="chart-card">
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                        <div style={{
                          width: '40px',
                          height: '40px',
                          borderRadius: '8px',
                          background: providerInfo?.color || 'var(--primary-color)',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          color: 'white',
                          fontWeight: 600,
                          fontSize: '14px',
                        }}>
                          {config.provider.slice(0, 2).toUpperCase()}
                        </div>
                        <div>
                          <h3 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>
                            {providerInfo?.name || config.provider}
                          </h3>
                          <span style={{
                            fontSize: '12px',
                            padding: '2px 8px',
                            borderRadius: '4px',
                            background: config.enabled ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                            color: config.enabled ? '#10b981' : '#ef4444',
                          }}>
                            {config.enabled ? 'Active' : 'Disabled'}
                          </span>
                        </div>
                      </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '13px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-muted)' }}>Secret</span>
                        <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                          {config.has_secret ? (
                            <><CheckCircle size={14} style={{ color: '#10b981' }} /> Configured</>
                          ) : (
                            <><AlertTriangle size={14} style={{ color: '#f59e0b' }} /> Not set</>
                          )}
                        </span>
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <span style={{ color: 'var(--text-muted)' }}>Signature Header</span>
                        <code style={{ fontSize: '12px' }}>{config.signature_header}</code>
                      </div>
                    </div>

                    <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-color)' }}>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px' }}>Webhook URL</div>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <code style={{ flex: 1, fontSize: '11px', padding: '8px', background: 'var(--bg-secondary)', borderRadius: '4px', wordBreak: 'break-all' }}>
                          {window.location.origin}/api/webhooks/{config.provider}
                        </code>
                        <button
                          className="btn-secondary"
                          style={{ padding: '6px' }}
                          onClick={() => copyToClipboard(`${window.location.origin}/api/webhooks/${config.provider}`)}
                        >
                          <Copy size={14} />
                        </button>
                      </div>
                    </div>

                    {/* Enable/Disable Toggle */}
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-color)' }}>
                      <div>
                        <div style={{ fontWeight: 500, fontSize: '14px' }}>Enable Processing</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                          {config.enabled ? 'Webhooks are being processed' : 'Webhooks will be ignored'}
                        </div>
                      </div>
                      <label style={{ position: 'relative', width: '44px', height: '24px', cursor: 'pointer' }}>
                        <input
                          type="checkbox"
                          checked={config.enabled}
                          onChange={() => toggleProviderEnabled(config.provider, config.enabled)}
                          style={{ display: 'none' }}
                        />
                        <span style={{
                          position: 'absolute',
                          inset: 0,
                          background: config.enabled ? 'var(--primary-color)' : '#d1d5db',
                          borderRadius: '12px',
                          transition: '0.2s',
                        }}>
                          <span style={{
                            position: 'absolute',
                            top: '2px',
                            left: config.enabled ? '22px' : '2px',
                            width: '20px',
                            height: '20px',
                            background: 'white',
                            borderRadius: '50%',
                            transition: '0.2s',
                          }} />
                        </span>
                      </label>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Handlers Tab */}
      {activeTab === 'handlers' && (
        <div>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <p style={{ color: 'var(--text-secondary)', margin: 0 }}>Route webhook events to workflows, HTTP endpoints, or functions</p>
            <div style={{ display: 'flex', gap: '8px' }}>
              <button
                className="btn-secondary"
                style={{ padding: '10px 16px' }}
                onClick={fetchHandlers}
                title="Refresh handlers"
              >
                <RefreshCw size={16} />
              </button>
              <button className="btn-primary" onClick={() => setShowHandlerModal(true)}>
                <Plus size={18} />Add Handler
              </button>
            </div>
          </div>

          {loadingHandlers ? (
            <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
              <Loader2 size={24} className="animate-spin" />
            </div>
          ) : handlers.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-muted)' }}>
              <Webhook size={48} style={{ opacity: 0.3, marginBottom: '16px' }} />
              <p>No handlers registered yet.</p>
              <p style={{ fontSize: '14px' }}>Add a handler to route webhook events to workflows or HTTP endpoints.</p>
            </div>
          ) : (
            <div className="chart-card" style={{ padding: 0 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ background: 'var(--bg-secondary)' }}>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Event Pattern</th>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Handler Type</th>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Configuration</th>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Status</th>
                    <th style={{ padding: '12px 16px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {handlers.map((handler, idx) => (
                    <tr key={`${handler.event_type}-${handler.handler_type}-${idx}`} style={{ borderTop: '1px solid var(--border-color)' }}>
                      <td style={{ padding: '14px 16px' }}>
                        <code style={{ fontSize: '13px', fontWeight: 500 }}>{handler.event_type}</code>
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <span style={{
                          display: 'inline-flex',
                          alignItems: 'center',
                          gap: '6px',
                          padding: '4px 10px',
                          borderRadius: '4px',
                          background: 'var(--bg-secondary)',
                          fontSize: '13px',
                          fontWeight: 500,
                          textTransform: 'capitalize',
                        }}>
                          {handler.handler_type}
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                        {handler.handler_type === 'workflow' && (
                          <span>Workflow: {(handler.handler_config.workflow_id as string) || 'N/A'}</span>
                        )}
                        {handler.handler_type === 'http' && (
                          <span>URL: {(handler.handler_config.url as string) || 'N/A'}</span>
                        )}
                        {handler.handler_type === 'log' && <span>Console logging</span>}
                        {handler.handler_type === 'function' && (
                          <span>Function: {(handler.handler_config.function as string) || 'N/A'}</span>
                        )}
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <span style={{
                          padding: '4px 10px',
                          borderRadius: '4px',
                          fontSize: '12px',
                          background: handler.enabled ? 'rgba(16, 185, 129, 0.1)' : 'rgba(107, 114, 128, 0.1)',
                          color: handler.enabled ? '#10b981' : '#6b7280',
                        }}>
                          {handler.enabled ? 'Active' : 'Disabled'}
                        </span>
                      </td>
                      <td style={{ padding: '14px 16px' }}>
                        <button
                          className="btn-secondary"
                          style={{ padding: '6px', color: 'var(--error-color)' }}
                          onClick={() => deleteHandler(handler.event_type, handler.handler_type)}
                          title="Remove handler"
                        >
                          <Trash2 size={14} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {/* Event Detail Modal */}
      {selectedEvent && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: 'white', borderRadius: '12px', width: '600px', maxWidth: '90vw', maxHeight: '80vh', overflow: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px 24px', borderBottom: '1px solid var(--border-color)' }}>
              <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>Event Details</h3>
              <button onClick={() => setSelectedEvent(null)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>
            <div style={{ padding: '24px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', marginBottom: '20px' }}>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>Event ID</div>
                  <code style={{ fontSize: '13px' }}>{selectedEvent.event_id}</code>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>Provider</div>
                  <span style={{ fontSize: '14px', fontWeight: 500 }}>{selectedEvent.provider}</span>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>Event Type</div>
                  <code style={{ fontSize: '13px' }}>{selectedEvent.event_type}</code>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>Status</div>
                  <span style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: '6px',
                    padding: '4px 10px',
                    borderRadius: '4px',
                    fontSize: '12px',
                    ...getStatusBadgeStyle(selectedEvent.status),
                  }}>
                    {getStatusIcon(selectedEvent.status)}
                    {selectedEvent.status}
                  </span>
                </div>
                <div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>Received At</div>
                  <span style={{ fontSize: '14px' }}>{new Date(selectedEvent.received_at).toLocaleString()}</span>
                </div>
                {selectedEvent.processed_at && (
                  <div>
                    <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>Processed At</div>
                    <span style={{ fontSize: '14px' }}>{new Date(selectedEvent.processed_at).toLocaleString()}</span>
                  </div>
                )}
              </div>

              {selectedEvent.error_message && (
                <div style={{ marginBottom: '20px', padding: '12px', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
                  <div style={{ fontSize: '12px', color: '#ef4444', marginBottom: '4px', fontWeight: 500 }}>Error Message</div>
                  <code style={{ fontSize: '13px', color: '#b91c1c' }}>{selectedEvent.error_message}</code>
                </div>
              )}

              <div>
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '8px' }}>Payload</div>
                <pre style={{
                  padding: '16px',
                  background: 'var(--bg-secondary)',
                  borderRadius: '8px',
                  fontSize: '12px',
                  overflow: 'auto',
                  maxHeight: '300px',
                }}>
                  {JSON.stringify(selectedEvent.payload, null, 2)}
                </pre>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Configure Provider Modal */}
      {showConfigModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: 'white', borderRadius: '12px', width: '450px', maxWidth: '90vw' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px 24px', borderBottom: '1px solid var(--border-color)' }}>
              <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>
                {editingConfig ? `Edit ${editingConfig}` : 'Configure Webhook Provider'}
              </h3>
              <button onClick={() => setShowConfigModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>
            <div style={{ padding: '24px' }}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                  Provider <span style={{ color: 'var(--error-color)' }}>*</span>
                </label>
                <select
                  value={configForm.provider}
                  onChange={(e) => setConfigForm({ ...configForm, provider: e.target.value })}
                  disabled={!!editingConfig}
                  style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '14px' }}
                >
                  <option value="">Select provider...</option>
                  {Object.entries(PROVIDERS).map(([id, info]) => (
                    <option key={id} value={id}>{info.name}</option>
                  ))}
                  <option value="custom">Custom Provider</option>
                </select>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                  Webhook Secret
                </label>
                <input
                  type="password"
                  placeholder="Enter webhook signing secret"
                  value={configForm.secret_key}
                  onChange={(e) => setConfigForm({ ...configForm, secret_key: e.target.value })}
                  style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '14px' }}
                />
                <p style={{ margin: '6px 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>
                  Used for signature verification. Get this from your provider's webhook settings.
                </p>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                  Event Types (optional)
                </label>
                <input
                  type="text"
                  placeholder="e.g., payment.succeeded, payment.failed"
                  value={configForm.event_types}
                  onChange={(e) => setConfigForm({ ...configForm, event_types: e.target.value })}
                  style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '14px' }}
                />
                <p style={{ margin: '6px 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>
                  Comma-separated. Leave empty to accept all event types.
                </p>
              </div>

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', padding: '12px 16px', background: 'var(--bg-secondary)', borderRadius: '8px' }}>
                <div>
                  <div style={{ fontWeight: 500 }}>Enable webhook processing</div>
                </div>
                <label style={{ position: 'relative', width: '44px', height: '24px' }}>
                  <input
                    type="checkbox"
                    checked={configForm.enabled}
                    onChange={(e) => setConfigForm({ ...configForm, enabled: e.target.checked })}
                    style={{ display: 'none' }}
                  />
                  <span style={{
                    position: 'absolute',
                    inset: 0,
                    background: configForm.enabled ? 'var(--primary-color)' : '#d1d5db',
                    borderRadius: '12px',
                    cursor: 'pointer',
                    transition: '0.2s',
                  }}>
                    <span style={{
                      position: 'absolute',
                      top: '2px',
                      left: configForm.enabled ? '22px' : '2px',
                      width: '20px',
                      height: '20px',
                      background: 'white',
                      borderRadius: '50%',
                      transition: '0.2s',
                    }} />
                  </span>
                </label>
              </div>

              <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                <button className="btn-secondary" onClick={() => setShowConfigModal(false)}>Cancel</button>
                <button className="btn-primary" onClick={saveConfig}>Save</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Add Handler Modal */}
      {showHandlerModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: 'white', borderRadius: '12px', width: '450px', maxWidth: '90vw' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px 24px', borderBottom: '1px solid var(--border-color)' }}>
              <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>Add Webhook Handler</h3>
              <button onClick={() => setShowHandlerModal(false)} style={{ background: 'none', border: 'none', cursor: 'pointer' }}>
                <X size={20} />
              </button>
            </div>
            <div style={{ padding: '24px' }}>
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                  Event Pattern <span style={{ color: 'var(--error-color)' }}>*</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g., stripe.payment.succeeded or github.*"
                  value={handlerForm.event_type}
                  onChange={(e) => setHandlerForm({ ...handlerForm, event_type: e.target.value })}
                  style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '14px' }}
                />
                <p style={{ margin: '6px 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>
                  Use * for wildcards. E.g., "stripe.*" matches all Stripe events.
                </p>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                  Handler Type <span style={{ color: 'var(--error-color)' }}>*</span>
                </label>
                <select
                  value={handlerForm.handler_type}
                  onChange={(e) => setHandlerForm({ ...handlerForm, handler_type: e.target.value })}
                  style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '14px' }}
                >
                  <option value="workflow">Trigger Workflow</option>
                  <option value="http">HTTP Webhook</option>
                  <option value="log">Log Only</option>
                </select>
              </div>

              {handlerForm.handler_type === 'workflow' && (
                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                    Workflow ID
                  </label>
                  <input
                    type="text"
                    placeholder="e.g., wf-payment-handler"
                    value={handlerForm.workflow_id}
                    onChange={(e) => setHandlerForm({ ...handlerForm, workflow_id: e.target.value })}
                    style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '14px' }}
                  />
                </div>
              )}

              {handlerForm.handler_type === 'http' && (
                <div style={{ marginBottom: '16px' }}>
                  <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                    HTTP URL
                  </label>
                  <input
                    type="url"
                    placeholder="https://your-service.com/webhook"
                    value={handlerForm.http_url}
                    onChange={(e) => setHandlerForm({ ...handlerForm, http_url: e.target.value })}
                    style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '14px' }}
                  />
                </div>
              )}

              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', padding: '12px 16px', background: 'var(--bg-secondary)', borderRadius: '8px' }}>
                <div>
                  <div style={{ fontWeight: 500 }}>Enable handler</div>
                </div>
                <label style={{ position: 'relative', width: '44px', height: '24px' }}>
                  <input
                    type="checkbox"
                    checked={handlerForm.enabled}
                    onChange={(e) => setHandlerForm({ ...handlerForm, enabled: e.target.checked })}
                    style={{ display: 'none' }}
                  />
                  <span style={{
                    position: 'absolute',
                    inset: 0,
                    background: handlerForm.enabled ? 'var(--primary-color)' : '#d1d5db',
                    borderRadius: '12px',
                    cursor: 'pointer',
                    transition: '0.2s',
                  }}>
                    <span style={{
                      position: 'absolute',
                      top: '2px',
                      left: handlerForm.enabled ? '22px' : '2px',
                      width: '20px',
                      height: '20px',
                      background: 'white',
                      borderRadius: '50%',
                      transition: '0.2s',
                    }} />
                  </span>
                </label>
              </div>

              <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                <button className="btn-secondary" onClick={() => setShowHandlerModal(false)}>Cancel</button>
                <button className="btn-primary" onClick={saveHandler}>Add Handler</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
