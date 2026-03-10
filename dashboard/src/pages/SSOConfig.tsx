/**
 * SSO Configuration Page - Enterprise SAML/SSO Management
 *
 * Allows enterprise admins to configure SSO providers including:
 * - SAML 2.0 (Generic)
 * - OAuth 2.0/OIDC (Azure AD, Okta, Auth0, Google)
 *
 * Backend: /api/v1/sso/*
 */

import { useState, useEffect } from 'react';
import { UpgradeBanner } from '@/components/UpgradeBanner';
import { api } from '@/services/api';
import {
  Shield,
  Plus,
  CheckCircle,
  AlertTriangle,
  X,
  Loader2,
  Key,
  ExternalLink,
  Copy,
  Eye,
  EyeOff,
  Settings,
  Users,
  Clock,
  FileText,
  Link,
} from 'lucide-react';

interface SSOProvider {
  id: string;
  name: string;
  type: 'saml' | 'oauth';
  description: string;
  icon?: string;
}

interface SSOConfig {
  config_id: string;
  organization_id: string;
  provider: string;
  enabled: boolean;
  saml_entity_id?: string;
  saml_sso_url?: string;
  saml_slo_url?: string;
  oauth_client_id?: string;
  oauth_authorization_url?: string;
  oauth_scopes?: string[];
  attribute_mapping: Record<string, string>;
  jit_provisioning_enabled: boolean;
  default_role?: string;
  session_timeout_minutes: number;
  created_at: string;
  updated_at: string;
}

const SSO_PROVIDERS: SSOProvider[] = [
  { id: 'saml', name: 'SAML 2.0', type: 'saml', description: 'Generic SAML 2.0 identity provider' },
  { id: 'oauth_azure_ad', name: 'Microsoft Azure AD', type: 'oauth', description: 'Azure Active Directory with OAuth 2.0/OIDC' },
  { id: 'oauth_okta', name: 'Okta', type: 'oauth', description: 'Okta with OAuth 2.0/OIDC' },
  { id: 'oauth_auth0', name: 'Auth0', type: 'oauth', description: 'Auth0 with OAuth 2.0/OIDC' },
  { id: 'oauth_google', name: 'Google Workspace', type: 'oauth', description: 'Google Workspace with OAuth 2.0/OIDC' },
];

const API_BASE = 'http://localhost:8000';
const ORG_ID = 'default';

export function SSOConfigPage() {
  const [loading, setLoading] = useState(true);
  const [config, setConfig] = useState<SSOConfig | null>(null);
  const [isFeatureGated, setIsFeatureGated] = useState(false);
  const [showConfigModal, setShowConfigModal] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);
  const [showSecret, setShowSecret] = useState(false);
  const [selectedProvider, setSelectedProvider] = useState<string>('');

  // Form state
  const [formData, setFormData] = useState({
    provider: '',
    enabled: true,
    // SAML fields
    saml_entity_id: '',
    saml_sso_url: '',
    saml_slo_url: '',
    saml_x509_cert: '',
    // OAuth fields
    oauth_client_id: '',
    oauth_client_secret: '',
    oauth_authorization_url: '',
    oauth_token_url: '',
    oauth_userinfo_url: '',
    oauth_scopes: '',
    // Settings
    jit_provisioning_enabled: true,
    default_role: 'member',
    session_timeout_minutes: 480,
    // Attribute mapping
    email_attr: 'email',
    name_attr: 'name',
    role_attr: 'role',
  });

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  useEffect(() => {
    fetchConfig();
    api.getOrgPlan().then(plan => {
      setIsFeatureGated(!plan.enabled_features.includes('sso_saml'));
    }).catch(() => {});
  }, []);

  const fetchConfig = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/sso/config/${ORG_ID}`);
      if (response.ok) {
        const data = await response.json();
        setConfig(data);
      } else if (response.status === 404) {
        setConfig(null);
      }
    } catch (error) {
      console.error('Error fetching SSO config:', error);
    } finally {
      setLoading(false);
    }
  };

  const openConfigModal = (providerId?: string) => {
    if (config) {
      // Edit existing
      setFormData({
        provider: config.provider,
        enabled: config.enabled,
        saml_entity_id: config.saml_entity_id || '',
        saml_sso_url: config.saml_sso_url || '',
        saml_slo_url: config.saml_slo_url || '',
        saml_x509_cert: '',
        oauth_client_id: config.oauth_client_id || '',
        oauth_client_secret: '',
        oauth_authorization_url: config.oauth_authorization_url || '',
        oauth_token_url: '',
        oauth_userinfo_url: '',
        oauth_scopes: config.oauth_scopes?.join(', ') || '',
        jit_provisioning_enabled: config.jit_provisioning_enabled,
        default_role: config.default_role || 'member',
        session_timeout_minutes: config.session_timeout_minutes,
        email_attr: config.attribute_mapping?.email || 'email',
        name_attr: config.attribute_mapping?.name || 'name',
        role_attr: config.attribute_mapping?.role || 'role',
      });
    } else {
      // New config
      setFormData({
        provider: providerId || '',
        enabled: true,
        saml_entity_id: '',
        saml_sso_url: '',
        saml_slo_url: '',
        saml_x509_cert: '',
        oauth_client_id: '',
        oauth_client_secret: '',
        oauth_authorization_url: '',
        oauth_token_url: '',
        oauth_userinfo_url: '',
        oauth_scopes: 'openid email profile',
        jit_provisioning_enabled: true,
        default_role: 'member',
        session_timeout_minutes: 480,
        email_attr: 'email',
        name_attr: 'name',
        role_attr: 'role',
      });
    }
    setSelectedProvider(providerId || config?.provider || '');
    setShowConfigModal(true);
  };

  const saveConfig = async () => {
    if (!formData.provider) {
      setToast({ message: 'Please select a provider', type: 'error' });
      return;
    }

    setSaving(true);
    try {
      const provider = SSO_PROVIDERS.find(p => p.id === formData.provider);
      const isSaml = provider?.type === 'saml';

      const payload = {
        organization_id: ORG_ID,
        provider: formData.provider,
        enabled: formData.enabled,
        ...(isSaml ? {
          saml_entity_id: formData.saml_entity_id,
          saml_sso_url: formData.saml_sso_url,
          saml_slo_url: formData.saml_slo_url || null,
          saml_x509_cert: formData.saml_x509_cert || null,
        } : {
          oauth_client_id: formData.oauth_client_id,
          oauth_client_secret: formData.oauth_client_secret || null,
          oauth_authorization_url: formData.oauth_authorization_url || null,
          oauth_token_url: formData.oauth_token_url || null,
          oauth_userinfo_url: formData.oauth_userinfo_url || null,
          oauth_scopes: formData.oauth_scopes.split(',').map(s => s.trim()).filter(Boolean),
        }),
        attribute_mapping: {
          email: formData.email_attr,
          name: formData.name_attr,
          role: formData.role_attr,
        },
        jit_provisioning_enabled: formData.jit_provisioning_enabled,
        default_role: formData.default_role || null,
        session_timeout_minutes: formData.session_timeout_minutes,
      };

      const response = await fetch(`${API_BASE}/api/v1/sso/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        setToast({ message: 'SSO configuration saved successfully', type: 'success' });
        setShowConfigModal(false);
        fetchConfig();
      } else {
        const error = await response.json();
        setToast({ message: error.detail || 'Failed to save configuration', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to save configuration', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setToast({ message: 'Copied to clipboard', type: 'success' });
  };

  const providerInfo = config ? SSO_PROVIDERS.find(p => p.id === config.provider) : null;
  const formProviderInfo = SSO_PROVIDERS.find(p => p.id === selectedProvider);

  return (
    <div className="p-6 max-w-6xl mx-auto">
      {isFeatureGated && <UpgradeBanner feature="SSO / SAML" />}
      {/* Toast */}
      {toast && (
        <div className={`fixed bottom-4 right-4 px-4 py-2 rounded-lg shadow-lg ${
          toast.type === 'success' ? 'bg-green-500' : 'bg-red-500'
        } text-white z-50 flex items-center gap-2`}>
          {toast.type === 'success' ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
          {toast.message}
        </div>
      )}

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
              <Shield className="w-8 h-8 text-indigo-600" />
              SSO Configuration
              <span className="text-sm font-normal text-indigo-600 bg-indigo-100 px-2 py-1 rounded">Enterprise</span>
            </h1>
            <p className="text-gray-600 mt-1">
              Configure Single Sign-On with SAML 2.0 or OAuth 2.0/OIDC providers
            </p>
          </div>
          <button
            onClick={() => openConfigModal()}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            <Plus className="w-4 h-4" />
            {config ? 'Edit Configuration' : 'Configure SSO'}
          </button>
        </div>
      </div>

      {loading ? (
        <div className="flex justify-center p-12">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600" />
        </div>
      ) : config ? (
        /* Current SSO Configuration */
        <div className="space-y-6">
          {/* Status Card */}
          <div className="bg-white rounded-lg shadow p-6">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-4">
                <div className={`w-14 h-14 rounded-lg ${config.enabled ? 'bg-green-100' : 'bg-gray-100'} flex items-center justify-center`}>
                  <Shield className={`w-7 h-7 ${config.enabled ? 'text-green-600' : 'text-gray-600'}`} />
                </div>
                <div>
                  <h2 className="text-xl font-semibold">{providerInfo?.name || config.provider}</h2>
                  <p className="text-sm text-gray-500">{providerInfo?.description}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${
                  config.enabled
                    ? 'bg-green-100 text-green-800'
                    : 'bg-gray-100 text-gray-800'
                }`}>
                  {config.enabled ? 'Active' : 'Disabled'}
                </span>
                <button
                  onClick={() => openConfigModal()}
                  className="p-2 text-gray-500 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg"
                  title="Edit Configuration"
                >
                  <Settings className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Configuration Details */}
            <div className="grid grid-cols-2 gap-6">
              {providerInfo?.type === 'saml' ? (
                <>
                  <div>
                    <label className="text-sm font-medium text-gray-500">Entity ID</label>
                    <div className="flex items-center gap-2 mt-1">
                      <code className="flex-1 text-sm bg-gray-50 p-2 rounded">{config.saml_entity_id || '-'}</code>
                      {config.saml_entity_id && (
                        <button onClick={() => copyToClipboard(config.saml_entity_id!)} className="text-gray-400 hover:text-gray-600">
                          <Copy className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-500">SSO URL</label>
                    <div className="flex items-center gap-2 mt-1">
                      <code className="flex-1 text-sm bg-gray-50 p-2 rounded truncate">{config.saml_sso_url || '-'}</code>
                      {config.saml_sso_url && (
                        <a href={config.saml_sso_url} target="_blank" rel="noopener noreferrer" className="text-gray-400 hover:text-gray-600">
                          <ExternalLink className="w-4 h-4" />
                        </a>
                      )}
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <div>
                    <label className="text-sm font-medium text-gray-500">Client ID</label>
                    <div className="flex items-center gap-2 mt-1">
                      <code className="flex-1 text-sm bg-gray-50 p-2 rounded truncate">{config.oauth_client_id || '-'}</code>
                      {config.oauth_client_id && (
                        <button onClick={() => copyToClipboard(config.oauth_client_id!)} className="text-gray-400 hover:text-gray-600">
                          <Copy className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-gray-500">Scopes</label>
                    <div className="flex flex-wrap gap-1 mt-1">
                      {config.oauth_scopes?.map((scope, i) => (
                        <span key={i} className="text-xs bg-gray-100 text-gray-700 px-2 py-1 rounded">{scope}</span>
                      )) || '-'}
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Settings Cards */}
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
                  <Users className="w-5 h-5 text-blue-600" />
                </div>
                <div>
                  <h3 className="font-medium">JIT Provisioning</h3>
                  <p className="text-xs text-gray-500">Auto-create users on login</p>
                </div>
              </div>
              <span className={`text-sm font-medium ${config.jit_provisioning_enabled ? 'text-green-600' : 'text-gray-500'}`}>
                {config.jit_provisioning_enabled ? 'Enabled' : 'Disabled'}
              </span>
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
                  <Clock className="w-5 h-5 text-purple-600" />
                </div>
                <div>
                  <h3 className="font-medium">Session Timeout</h3>
                  <p className="text-xs text-gray-500">Auto-logout duration</p>
                </div>
              </div>
              <span className="text-sm font-medium text-gray-900">
                {config.session_timeout_minutes} minutes ({Math.round(config.session_timeout_minutes / 60)}h)
              </span>
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 bg-amber-100 rounded-lg flex items-center justify-center">
                  <Key className="w-5 h-5 text-amber-600" />
                </div>
                <div>
                  <h3 className="font-medium">Default Role</h3>
                  <p className="text-xs text-gray-500">For new JIT users</p>
                </div>
              </div>
              <span className="text-sm font-medium text-gray-900 capitalize">
                {config.default_role || 'member'}
              </span>
            </div>
          </div>

          {/* SP Metadata */}
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="font-semibold mb-4 flex items-center gap-2">
              <FileText className="w-5 h-5 text-gray-600" />
              Service Provider (SP) Metadata
            </h3>
            <p className="text-sm text-gray-600 mb-4">
              Use this information to configure your Identity Provider.
            </p>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="text-sm font-medium text-gray-500">SP Entity ID</label>
                <div className="flex items-center gap-2 mt-1">
                  <code className="flex-1 text-sm bg-gray-50 p-2 rounded truncate">
                    https://platform.example.com/saml/{ORG_ID}
                  </code>
                  <button onClick={() => copyToClipboard(`https://platform.example.com/saml/${ORG_ID}`)} className="text-gray-400 hover:text-gray-600">
                    <Copy className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div>
                <label className="text-sm font-medium text-gray-500">ACS URL (Callback)</label>
                <div className="flex items-center gap-2 mt-1">
                  <code className="flex-1 text-sm bg-gray-50 p-2 rounded truncate">
                    {API_BASE}/api/v1/sso/callback/saml
                  </code>
                  <button onClick={() => copyToClipboard(`${API_BASE}/api/v1/sso/callback/saml`)} className="text-gray-400 hover:text-gray-600">
                    <Copy className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      ) : (
        /* No Configuration - Provider Selection */
        <div className="bg-white rounded-lg shadow p-8">
          <div className="text-center mb-8">
            <Shield className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h2 className="text-xl font-semibold text-gray-900 mb-2">No SSO Configuration</h2>
            <p className="text-gray-600">
              Configure Single Sign-On to enable secure authentication for your organization
            </p>
          </div>

          <h3 className="font-medium text-gray-900 mb-4">Choose a Provider</h3>
          <div className="grid grid-cols-2 gap-4">
            {SSO_PROVIDERS.map((provider) => (
              <button
                key={provider.id}
                onClick={() => openConfigModal(provider.id)}
                className="flex items-center gap-4 p-4 border rounded-lg hover:border-indigo-300 hover:bg-indigo-50 text-left transition-colors"
              >
                <div className="w-12 h-12 bg-indigo-100 rounded-lg flex items-center justify-center">
                  <Shield className="w-6 h-6 text-indigo-600" />
                </div>
                <div>
                  <h4 className="font-medium text-gray-900">{provider.name}</h4>
                  <p className="text-sm text-gray-500">{provider.description}</p>
                  <span className={`text-xs px-2 py-0.5 rounded mt-1 inline-block ${
                    provider.type === 'saml' ? 'bg-purple-100 text-purple-700' : 'bg-blue-100 text-blue-700'
                  }`}>
                    {provider.type === 'saml' ? 'SAML 2.0' : 'OAuth 2.0'}
                  </span>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Configuration Modal */}
      {showConfigModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-4 border-b flex items-center justify-between sticky top-0 bg-white">
              <h2 className="text-lg font-semibold">
                {config ? 'Edit SSO Configuration' : 'Configure SSO'}
              </h2>
              <button onClick={() => setShowConfigModal(false)} className="text-gray-500 hover:text-gray-700">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Provider Selection */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Identity Provider <span className="text-red-500">*</span>
                </label>
                <select
                  value={formData.provider}
                  onChange={(e) => {
                    setFormData({ ...formData, provider: e.target.value });
                    setSelectedProvider(e.target.value);
                  }}
                  disabled={!!config}
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="">Select a provider...</option>
                  {SSO_PROVIDERS.map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.name} ({provider.type === 'saml' ? 'SAML 2.0' : 'OAuth 2.0'})
                    </option>
                  ))}
                </select>
              </div>

              {/* SAML Configuration */}
              {formProviderInfo?.type === 'saml' && (
                <div className="space-y-4">
                  <h3 className="font-medium text-gray-900 flex items-center gap-2">
                    <Shield className="w-4 h-4" />
                    SAML Configuration
                  </h3>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      IdP Entity ID <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.saml_entity_id}
                      onChange={(e) => setFormData({ ...formData, saml_entity_id: e.target.value })}
                      placeholder="https://idp.example.com/saml/metadata"
                      className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      IdP SSO URL <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.saml_sso_url}
                      onChange={(e) => setFormData({ ...formData, saml_sso_url: e.target.value })}
                      placeholder="https://idp.example.com/saml/sso"
                      className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      IdP SLO URL (Optional)
                    </label>
                    <input
                      type="text"
                      value={formData.saml_slo_url}
                      onChange={(e) => setFormData({ ...formData, saml_slo_url: e.target.value })}
                      placeholder="https://idp.example.com/saml/slo"
                      className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      X.509 Certificate
                    </label>
                    <textarea
                      value={formData.saml_x509_cert}
                      onChange={(e) => setFormData({ ...formData, saml_x509_cert: e.target.value })}
                      placeholder="-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----"
                      rows={4}
                      className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500 font-mono text-sm"
                    />
                  </div>
                </div>
              )}

              {/* OAuth Configuration */}
              {formProviderInfo?.type === 'oauth' && (
                <div className="space-y-4">
                  <h3 className="font-medium text-gray-900 flex items-center gap-2">
                    <Key className="w-4 h-4" />
                    OAuth 2.0 Configuration
                  </h3>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Client ID <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={formData.oauth_client_id}
                      onChange={(e) => setFormData({ ...formData, oauth_client_id: e.target.value })}
                      placeholder="Enter your OAuth Client ID"
                      className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Client Secret {!config && <span className="text-red-500">*</span>}
                    </label>
                    <div className="relative">
                      <input
                        type={showSecret ? 'text' : 'password'}
                        value={formData.oauth_client_secret}
                        onChange={(e) => setFormData({ ...formData, oauth_client_secret: e.target.value })}
                        placeholder={config ? 'Leave blank to keep existing' : 'Enter your OAuth Client Secret'}
                        className="w-full border rounded-lg px-3 py-2 pr-10 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                      <button
                        type="button"
                        onClick={() => setShowSecret(!showSecret)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                      >
                        {showSecret ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                      </button>
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Scopes
                    </label>
                    <input
                      type="text"
                      value={formData.oauth_scopes}
                      onChange={(e) => setFormData({ ...formData, oauth_scopes: e.target.value })}
                      placeholder="openid email profile"
                      className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    />
                    <p className="text-xs text-gray-500 mt-1">Comma-separated list of OAuth scopes</p>
                  </div>
                </div>
              )}

              {/* Attribute Mapping */}
              {selectedProvider && (
                <div className="space-y-4">
                  <h3 className="font-medium text-gray-900 flex items-center gap-2">
                    <Link className="w-4 h-4" />
                    Attribute Mapping
                  </h3>
                  <div className="grid grid-cols-3 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Email Attribute</label>
                      <input
                        type="text"
                        value={formData.email_attr}
                        onChange={(e) => setFormData({ ...formData, email_attr: e.target.value })}
                        className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Name Attribute</label>
                      <input
                        type="text"
                        value={formData.name_attr}
                        onChange={(e) => setFormData({ ...formData, name_attr: e.target.value })}
                        className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Role Attribute</label>
                      <input
                        type="text"
                        value={formData.role_attr}
                        onChange={(e) => setFormData({ ...formData, role_attr: e.target.value })}
                        className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Settings */}
              {selectedProvider && (
                <div className="space-y-4">
                  <h3 className="font-medium text-gray-900 flex items-center gap-2">
                    <Settings className="w-4 h-4" />
                    Settings
                  </h3>

                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <div className="font-medium">Enable SSO</div>
                      <div className="text-sm text-gray-500">Allow users to sign in via SSO</div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={formData.enabled}
                        onChange={(e) => setFormData({ ...formData, enabled: e.target.checked })}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
                    </label>
                  </div>

                  <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                    <div>
                      <div className="font-medium">Just-In-Time Provisioning</div>
                      <div className="text-sm text-gray-500">Automatically create user accounts on first login</div>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={formData.jit_provisioning_enabled}
                        onChange={(e) => setFormData({ ...formData, jit_provisioning_enabled: e.target.checked })}
                        className="sr-only peer"
                      />
                      <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-indigo-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-indigo-600"></div>
                    </label>
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Default Role</label>
                      <select
                        value={formData.default_role}
                        onChange={(e) => setFormData({ ...formData, default_role: e.target.value })}
                        className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="viewer">Viewer</option>
                        <option value="member">Member</option>
                        <option value="admin">Admin</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">Session Timeout (minutes)</label>
                      <input
                        type="number"
                        value={formData.session_timeout_minutes}
                        onChange={(e) => setFormData({ ...formData, session_timeout_minutes: parseInt(e.target.value) || 480 })}
                        min={15}
                        max={10080}
                        className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      />
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="p-4 border-t bg-gray-50 flex justify-end gap-3 sticky bottom-0">
              <button
                onClick={() => setShowConfigModal(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={saveConfig}
                disabled={saving || !formData.provider}
                className="flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
              >
                {saving ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4" />
                    Save Configuration
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

export default SSOConfigPage;
