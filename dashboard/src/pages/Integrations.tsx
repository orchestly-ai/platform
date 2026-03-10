/**
 * Integrations Page - Connect tools and services
 *
 * Supports OAuth 2.0 authentication for:
 * - Slack (OAuth 2.0)
 * - Gmail (Google OAuth 2.0)
 * - GitHub (OAuth 2.0)
 * - Discord (Bot Token / API Key)
 */

import React, { useState, useEffect } from 'react';
import {
  Search,
  Plus,
  CheckCircle,
  Clock,
  RefreshCw,
  ExternalLink,
  Key,
  Trash2,
  Link,
  Zap,
  Globe,
  MessageSquare,
  Cloud,
  Code2,
  LayoutGrid,
  Headphones,
  FileText,
  Puzzle,
  Star,
  Download,
  ArrowRight,
  Shield,
  Activity,
} from 'lucide-react';
import { api } from '@/services/api';
import { ConnectIntegration } from '@/components/integrations/ConnectIntegration';
import { BrandIcon, getBrandInfo } from '@/components/integrations/BrandIcons';

interface Integration {
  id: string;
  name: string;
  description: string;
  category: string;
  status: 'active' | 'inactive';
  verified: boolean;
  install_count: number;
  avg_rating: number;
  slug?: string;
  auth_type?: string;
}

// Integrations that support OAuth
const OAUTH_INTEGRATIONS = ['slack', 'gmail', 'github'];

// Get slug from integration name
const getSlug = (name: string): string => {
  return name.toLowerCase().replace(/\s+/g, '-');
};

// Category metadata for styling — uses CSS vars from Monokai Pro theme
const categoryMeta: Record<string, { icon: React.ComponentType<{ size?: number; className?: string }>, color: string; label: string }> = {
  ai: { icon: Zap, color: 'var(--purple)', label: 'AI' },
  communication: { icon: MessageSquare, color: 'var(--cyan)', label: 'Communication' },
  crm: { icon: Cloud, color: 'var(--green)', label: 'CRM' },
  development: { icon: Code2, color: 'var(--orange)', label: 'Development' },
  project_management: { icon: LayoutGrid, color: 'var(--yellow)', label: 'Project Mgmt' },
  support: { icon: Headphones, color: 'var(--pink)', label: 'Support' },
  productivity: { icon: FileText, color: 'var(--cyan)', label: 'Productivity' },
};

const getCategoryMeta = (category: string) => {
  return categoryMeta[category.toLowerCase()] || {
    icon: Puzzle,
    color: 'var(--accent)',
    label: category,
  };
};

export function IntegrationsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [integrations, setIntegrations] = useState<Integration[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [installingIntegrations, setInstallingIntegrations] = useState<Set<string>>(new Set());
  const [testingIntegrations, setTestingIntegrations] = useState<Set<string>>(new Set());
  const [connectingOAuth, setConnectingOAuth] = useState<Set<string>>(new Set());
  const [installedIntegrations, setInstalledIntegrations] = useState<Map<string, string>>(new Map());
  const [connectingIntegration, setConnectingIntegration] = useState<Integration | null>(null);

  const categories = ['all', 'ai', 'communication', 'crm', 'development', 'project_management', 'support', 'productivity'];

  useEffect(() => {
    loadInstalledIntegrations();
  }, []);

  useEffect(() => {
    loadIntegrations();
  }, [searchQuery, categoryFilter]);

  const loadInstalledIntegrations = async () => {
    try {
      const installed = await api.getInstalledIntegrations('default-org');
      const map = new Map<string, string>();
      installed.forEach(inst => {
        map.set(inst.integration_id, inst.installation_id);
      });
      setInstalledIntegrations(map);
    } catch (err) {
      console.error('Failed to load installed integrations:', err);
    }
  };

  const loadIntegrations = async () => {
    try {
      setLoading(true);
      setError(null);
      const filters = {
        search: searchQuery || undefined,
        category: categoryFilter !== 'all' ? categoryFilter : undefined,
        verified: undefined,
      };
      const result = await api.browseIntegrations(filters);
      setIntegrations(result.integrations);
    } catch (err) {
      console.error('Failed to load integrations:', err);
      setError(null);
      setIntegrations([]);
    } finally {
      setLoading(false);
    }
  };

  const handleInstall = async (integrationId: string) => {
    try {
      setInstallingIntegrations(prev => new Set(prev).add(integrationId));
      const result = await api.installIntegration(integrationId, 'default-org', 'default-user');
      setInstalledIntegrations(prev => new Map(prev).set(integrationId, result.installation_id));
      alert('Integration enabled! Click "Configure" to add your API key or connect with OAuth.');
    } catch (err) {
      console.error('Failed to install integration:', err);
      alert(`Failed to install integration: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setInstallingIntegrations(prev => {
        const next = new Set(prev);
        next.delete(integrationId);
        return next;
      });
    }
  };

  const handleUninstall = async (integration: Integration) => {
    const confirmed = window.confirm(
      `Are you sure you want to disconnect ${integration.name}?\n\n` +
      `This will remove your stored credentials and disable this integration.`
    );
    if (!confirmed) return;
    try {
      const slug = integration.slug || getSlug(integration.name);
      await api.uninstallIntegration(slug, 'default-org');
      setInstalledIntegrations(prev => {
        const next = new Map(prev);
        next.delete(integration.id);
        return next;
      });
      alert(`${integration.name} disconnected successfully.`);
    } catch (err) {
      console.error('Failed to uninstall integration:', err);
      alert(`Failed to disconnect integration: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  };

  const handleTest = async (integration: Integration) => {
    try {
      setTestingIntegrations(prev => new Set(prev).add(integration.id));
      const installationId = installedIntegrations.get(integration.id);
      if (!installationId) {
        alert('Please install the integration first before testing.');
        return;
      }
      const slug = integration.slug || getSlug(integration.name);
      const result = await api.testIntegration(slug, installationId, 'test_connection', {});
      if (result.success) {
        alert('Integration test successful!');
      } else {
        alert(`Integration test failed: ${result.error_message || 'Unknown error'}`);
      }
    } catch (err) {
      console.error('Failed to test integration:', err);
      alert(`Failed to test integration: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setTestingIntegrations(prev => {
        const next = new Set(prev);
        next.delete(integration.id);
        return next;
      });
    }
  };

  const handleConfigure = (integrationId: string) => {
    const integration = integrations.find(i => i.id === integrationId);
    if (integration) {
      setConnectingIntegration(integration);
    }
  };

  const handleConnected = async (installationId: string) => {
    if (connectingIntegration) {
      setInstalledIntegrations(prev => new Map(prev).set(connectingIntegration.id, installationId));
    }
    await loadInstalledIntegrations();
    setConnectingIntegration(null);
  };

  const handleOpenConnect = (integration: Integration) => {
    setConnectingIntegration(integration);
  };

  const handleOAuthConnect = async (integration: Integration) => {
    const slug = integration.slug || getSlug(integration.name);
    if (!OAUTH_INTEGRATIONS.includes(slug)) {
      await handleInstall(integration.id);
      return;
    }
    try {
      setConnectingOAuth(prev => new Set(prev).add(integration.id));
      const result = await api.startOAuthFlow(slug, 'default-org');
      sessionStorage.setItem(`oauth_state_${slug}`, result.state);
      sessionStorage.setItem(`oauth_integration_id`, integration.id);
      window.open(result.authorization_url, '_blank', 'width=600,height=700');
      alert(
        `OAuth window opened for ${integration.name}.\n\n` +
        `After authorizing, you'll be redirected back to complete the connection.\n\n` +
        `Note: In production, the callback URL would be configured in your OAuth app settings.`
      );
    } catch (err) {
      console.error('Failed to start OAuth flow:', err);
      alert(`Failed to connect ${integration.name}: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setConnectingOAuth(prev => {
        const next = new Set(prev);
        next.delete(integration.id);
        return next;
      });
    }
  };

  const supportsOAuth = (integration: Integration): boolean => {
    const slug = integration.slug || getSlug(integration.name);
    return OAUTH_INTEGRATIONS.includes(slug);
  };

  const connectedCount = integrations.filter((i) => installedIntegrations.has(i.id)).length;
  const activeCount = integrations.filter((i) => i.status === 'active').length;

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Puzzle className="h-12 w-12 mx-auto mb-3 animate-pulse" style={{ color: 'var(--accent)' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Loading integrations...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
          <Puzzle className="h-7 w-7" style={{ color: 'var(--accent)' }} />
          Integrations
        </h1>
        <p className="mt-1" style={{ color: 'var(--text-secondary)' }}>
          Connect your tools and services to Orchestly agents and workflows
        </p>
      </div>

      {/* Stats Section */}
      <div className="rounded-lg p-6" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[
            { value: connectedCount, label: 'Connected', sublabel: 'Active connections', Icon: Link, iconColor: 'var(--green)' },
            { value: activeCount, label: 'Available', sublabel: 'Ready to connect', Icon: Globe, iconColor: 'var(--accent)' },
            { value: integrations.length, label: 'Total', sublabel: 'In marketplace', Icon: Puzzle, iconColor: 'var(--yellow)' },
            { value: '5,170', label: 'API Requests', sublabel: 'Last 30 days', Icon: Activity, iconColor: 'var(--purple)' },
          ].map((stat) => (
            <div key={stat.label} className="rounded-lg p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}>
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
                  <stat.Icon className="h-5 w-5" style={{ color: stat.iconColor }} />
                </div>
                <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>{stat.label}</span>
              </div>
              <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{stat.value}</p>
              <p className="text-xs mt-1" style={{ color: 'var(--text-tertiary)' }}>{stat.sublabel}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Search + Category Filters */}
      <div className="flex gap-3 items-center flex-wrap">
        <div className="flex items-center gap-2 flex-1 max-w-xs">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
            <input
              type="text"
              placeholder="Search integrations..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 px-3 py-2 rounded-lg text-sm"
              style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
            />
          </div>
        </div>
        <div className="flex gap-2 flex-wrap">
          {categories.map((category) => {
            const meta = category === 'all' ? null : getCategoryMeta(category);
            const isActive = categoryFilter === category;
            const IconComp = meta?.icon;
            return (
              <button
                key={category}
                onClick={() => setCategoryFilter(category)}
                className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors"
                style={{
                  border: isActive ? '1px solid var(--accent)' : '1px solid var(--border-primary)',
                  background: isActive ? 'var(--accent)' : 'var(--bg-primary)',
                  color: isActive ? 'var(--bg-primary)' : 'var(--text-secondary)',
                }}
              >
                {IconComp && <IconComp size={14} />}
                {category === 'all' ? 'All' : (meta?.label || category)}
              </button>
            );
          })}
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="rounded-lg p-4" style={{ background: 'color-mix(in srgb, var(--error) 10%, var(--bg-secondary))', border: '1px solid var(--error)', borderLeft: '3px solid var(--error)' }}>
          <div className="flex items-center gap-3">
            <ExternalLink className="h-5 w-5 flex-shrink-0" style={{ color: 'var(--error)' }} />
            <div>
              <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Connection Error</p>
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Integrations Grid */}
      {integrations.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {integrations.map((integration) => {
            const meta = getCategoryMeta(integration.category);
            const isInstalled = installedIntegrations.has(integration.id);
            const IconComp = meta.icon;
            const slug = integration.slug || getSlug(integration.name);
            const brand = getBrandInfo(slug);
            const accentColor = brand ? brand.color : meta.color;

            return (
              <div
                key={integration.id}
                className="rounded-lg overflow-hidden"
                style={{
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-primary)',
                  borderTop: `2px solid ${isInstalled ? 'var(--green)' : accentColor}`,
                }}
              >
                {/* Card Body */}
                <div className="p-5">
                  <div className="flex justify-between items-start mb-3">
                    {/* Icon */}
                    {(() => {
                      const slug = integration.slug || getSlug(integration.name);
                      const brand = getBrandInfo(slug);
                      const iconBg = brand ? `color-mix(in srgb, ${brand.color} 15%, transparent)` : `color-mix(in srgb, ${meta.color} 15%, transparent)`;
                      return (
                        <div
                          className="w-11 h-11 rounded-lg flex items-center justify-center"
                          style={{ background: iconBg }}
                        >
                          <BrandIcon slug={slug} size={22} fallbackIcon={IconComp} fallbackColor={meta.color} />
                        </div>
                      );
                    })()}
                    {/* Status badges */}
                    <div className="flex items-center gap-2">
                      {isInstalled && (
                        <span
                          className="flex items-center gap-1 text-xs font-semibold px-2 py-0.5 rounded-md uppercase"
                          style={{ background: 'color-mix(in srgb, var(--green) 15%, transparent)', color: 'var(--green)' }}
                        >
                          <CheckCircle size={10} /> Connected
                        </span>
                      )}
                      {integration.status === 'active' ? (
                        <span
                          className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-md"
                          style={{ background: 'color-mix(in srgb, var(--green) 15%, transparent)', color: 'var(--green)' }}
                        >
                          <CheckCircle size={10} /> Active
                        </span>
                      ) : (
                        <span
                          className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-md"
                          style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}
                        >
                          <Clock size={10} /> Inactive
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Name + Verified */}
                  <div className="flex items-center gap-2 mb-1">
                    <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>
                      {integration.name}
                    </h3>
                    {integration.verified && (
                      <Shield size={14} style={{ color: 'var(--accent)' }} title="Verified" />
                    )}
                  </div>

                  {/* Description */}
                  <p
                    className="text-sm mb-3 line-clamp-2"
                    style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}
                  >
                    {integration.description}
                  </p>

                  {/* Category + Stats row */}
                  <div className="flex items-center gap-3 flex-wrap">
                    <span
                      className="flex items-center gap-1.5 text-xs font-medium px-2.5 py-1 rounded-md"
                      style={{ background: `color-mix(in srgb, ${meta.color} 15%, transparent)`, color: meta.color }}
                    >
                      <IconComp size={12} /> {meta.label}
                    </span>
                    {integration.status === 'active' && (
                      <>
                        <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                          <Download size={11} /> {integration.install_count.toLocaleString()}
                        </span>
                        <span className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                          <Star size={11} style={{ color: 'var(--yellow)' }} /> {integration.avg_rating.toFixed(1)}
                        </span>
                      </>
                    )}
                  </div>
                </div>

                {/* Action Bar */}
                <div
                  className="flex gap-2 px-5 py-3"
                  style={{ borderTop: '1px solid var(--border-primary)', background: 'var(--bg-tertiary)' }}
                >
                  {isInstalled ? (
                    <>
                      <button
                        className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors"
                        style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)' }}
                        onClick={() => handleConfigure(integration.id)}
                        title="Add or update your credentials"
                      >
                        <Key size={13} /> Configure
                      </button>
                      <button
                        className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors"
                        style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)' }}
                        onClick={() => handleTest(integration)}
                        disabled={testingIntegrations.has(integration.id)}
                        title="Test the connection"
                      >
                        <RefreshCw size={13} className={testingIntegrations.has(integration.id) ? 'animate-spin' : ''} />
                        {testingIntegrations.has(integration.id) ? 'Testing...' : 'Test'}
                      </button>
                      <button
                        className="flex items-center justify-center p-1.5 rounded-lg transition-colors"
                        style={{ background: 'color-mix(in srgb, var(--error) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--error) 25%, transparent)' }}
                        onClick={() => handleUninstall(integration)}
                        title="Disconnect this integration"
                      >
                        <Trash2 size={13} style={{ color: 'var(--error)' }} />
                      </button>
                    </>
                  ) : (
                    <button
                      className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors"
                      style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
                      onClick={() => handleOpenConnect(integration)}
                      disabled={installingIntegrations.has(integration.id)}
                    >
                      {supportsOAuth(integration) ? <ExternalLink size={14} /> : <Key size={14} />}
                      {installingIntegrations.has(integration.id) ? 'Connecting...' : 'Connect'}
                      <ArrowRight size={14} style={{ opacity: 0.7 }} />
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Empty State */}
      {!loading && integrations.length === 0 && !error && (
        <div className="rounded-lg p-6" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
          <div className="text-center py-12">
            <Puzzle className="h-12 w-12 mx-auto mb-3" style={{ color: 'var(--text-tertiary)' }} />
            <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
              No integrations found
            </h3>
            <p className="text-sm mb-5 max-w-sm mx-auto" style={{ color: 'var(--text-secondary)' }}>
              Try adjusting your search query or category filter to discover available integrations.
            </p>
            <button
              className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg mx-auto"
              style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)' }}
              onClick={() => { setSearchQuery(''); setCategoryFilter('all'); }}
            >
              <RefreshCw size={14} /> Clear Filters
            </button>
          </div>
        </div>
      )}

      {/* Connect Integration Modal */}
      {connectingIntegration && (
        <ConnectIntegration
          integrationId={connectingIntegration.slug || getSlug(connectingIntegration.name)}
          integrationName={connectingIntegration.name}
          organizationId="default-org"
          onConnected={handleConnected}
          onClose={() => setConnectingIntegration(null)}
        />
      )}
    </div>
  );
}

export default IntegrationsPage;
