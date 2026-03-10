/**
 * Settings Page - Account and organization settings
 * Connected to backend API for team members and API keys
 */

import { useState, useEffect } from 'react';
import {
  Key,
  Users,
  Bell,
  Shield,
  CreditCard,
  Building,
  Plus,
  Copy,
  Trash2,
  AlertTriangle,
  CheckCircle,
  Loader2,
  X,
  KeyRound,
  ExternalLink,
  Info,
  Edit3,
} from 'lucide-react';
import { api } from '@/services/api';

type SettingsTab = 'api-keys' | 'oauth-apps' | 'team' | 'notifications' | 'security' | 'billing' | 'organization' | 'hipaa';

interface ApiKey {
  id: number;
  name: string;
  key?: string; // Only present on creation
  key_prefix: string;
  permissions?: string[];
  created_at: string;
  expires_at?: string;
  last_used_at?: string;
  is_active: boolean;
}

interface TeamMember {
  id: number;
  name?: string;
  email: string;
  role: string;
  status: string;
  joined_at?: string;
  last_seen_at?: string;
}

interface OAuthConfig {
  provider: string;
  client_id: string;
  client_id_masked: string;
  has_client_secret: boolean;
  custom_scopes?: string[];
  enabled: boolean;
  is_custom: boolean;
  created_at?: string;
  updated_at?: string;
}

// Available OAuth providers with display info
const OAUTH_PROVIDERS = [
  { id: 'google', name: 'Google', description: 'Google Workspace, Gmail, Drive, Calendar' },
  { id: 'slack', name: 'Slack', description: 'Team messaging and notifications' },
  { id: 'github', name: 'GitHub', description: 'Code repositories and issue tracking' },
  { id: 'microsoft', name: 'Microsoft', description: 'Microsoft 365, Azure AD, Teams' },
  { id: 'salesforce', name: 'Salesforce', description: 'CRM and sales automation' },
];

// Helper to get provider documentation URLs
function getProviderDocsUrl(provider: string): string {
  const docs: Record<string, string> = {
    google: 'https://developers.google.com/identity/protocols/oauth2',
    slack: 'https://api.slack.com/authentication/oauth-v2',
    github: 'https://docs.github.com/en/developers/apps/building-oauth-apps',
    microsoft: 'https://docs.microsoft.com/en-us/azure/active-directory/develop/v2-oauth2-auth-code-flow',
    salesforce: 'https://help.salesforce.com/s/articleView?id=sf.remoteaccess_oauth_web_server_flow.htm',
  };
  return docs[provider] || '#';
}

export function SettingsPage() {
  const [activeTab, setActiveTab] = useState<SettingsTab>('api-keys');
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<string | null>(null);

  // API Keys state
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loadingKeys, setLoadingKeys] = useState(true);
  const [creatingKey, setCreatingKey] = useState(false);
  const [showCreateKeyModal, setShowCreateKeyModal] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');

  // Team members state
  const [teamMembers, setTeamMembers] = useState<TeamMember[]>([]);
  const [loadingTeam, setLoadingTeam] = useState(true);
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteName, setInviteName] = useState('');
  const [inviteRole, setInviteRole] = useState('member');
  const [inviting, setInviting] = useState(false);

  // Toast state
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // OAuth configs state
  const [oauthConfigs, setOauthConfigs] = useState<OAuthConfig[]>([]);
  const [loadingOAuth, setLoadingOAuth] = useState(true);
  const [showOAuthModal, setShowOAuthModal] = useState(false);
  const [editingProvider, setEditingProvider] = useState<string | null>(null);
  const [oauthForm, setOauthForm] = useState({
    provider: '',
    client_id: '',
    client_secret: '',
    custom_scopes: '',
    enabled: true,
  });
  const [savingOAuth, setSavingOAuth] = useState(false);
  const [redirectUri, setRedirectUri] = useState<string | null>(null);

  // Default organization ID (in real app, get from auth context)
  const organizationId = 'default';

  const tabs = [
    { id: 'api-keys' as const, label: 'API Keys', icon: Key },
    { id: 'oauth-apps' as const, label: 'OAuth Apps', icon: KeyRound },
    { id: 'team' as const, label: 'Team', icon: Users },
    { id: 'notifications' as const, label: 'Notifications', icon: Bell },
    { id: 'security' as const, label: 'Security', icon: Shield },
    { id: 'billing' as const, label: 'Billing', icon: CreditCard },
    { id: 'organization' as const, label: 'Organization', icon: Building },
    { id: 'hipaa' as const, label: 'HIPAA', icon: Shield },
  ];

  // Auto-hide toast
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // Fetch API keys
  useEffect(() => {
    if (activeTab === 'api-keys') {
      fetchApiKeys();
    }
  }, [activeTab]);

  // Fetch team members
  useEffect(() => {
    if (activeTab === 'team') {
      fetchTeamMembers();
    }
  }, [activeTab]);

  // Fetch OAuth configs
  useEffect(() => {
    if (activeTab === 'oauth-apps') {
      fetchOAuthConfigs();
    }
  }, [activeTab]);

  const fetchApiKeys = async () => {
    setLoadingKeys(true);
    try {
      const data = await api.getApiKeys();
      setApiKeys(data);
    } catch (error) {
      console.error('Error fetching API keys:', error);
      setToast({ message: 'Failed to load API keys', type: 'error' });
    } finally {
      setLoadingKeys(false);
    }
  };

  const fetchTeamMembers = async () => {
    setLoadingTeam(true);
    try {
      const data = await api.getTeamMembers();
      setTeamMembers(data);
    } catch (error) {
      console.error('Error fetching team members:', error);
      setToast({ message: 'Failed to load team members', type: 'error' });
    } finally {
      setLoadingTeam(false);
    }
  };

  const createApiKey = async () => {
    if (!newKeyName.trim()) {
      setToast({ message: 'Please enter a name for the API key', type: 'error' });
      return;
    }

    setCreatingKey(true);
    try {
      const data = await api.createApiKey(newKeyName);
      setNewlyCreatedKey(data.key);
      setApiKeys([data, ...apiKeys]);
      setNewKeyName('');
      setShowCreateKeyModal(false);
      setToast({ message: 'API key created successfully', type: 'success' });
    } catch (error) {
      console.error('Error creating API key:', error);
      setToast({ message: 'Failed to create API key', type: 'error' });
    } finally {
      setCreatingKey(false);
    }
  };

  const revokeApiKey = async (keyId: number) => {
    if (!confirm('Are you sure you want to revoke this API key? This action cannot be undone.')) {
      return;
    }

    try {
      await api.revokeApiKey(keyId);
      setApiKeys(apiKeys.filter(k => k.id !== keyId));
      setToast({ message: 'API key revoked successfully', type: 'success' });
    } catch (error) {
      console.error('Error revoking API key:', error);
      setToast({ message: 'Failed to revoke API key', type: 'error' });
    }
  };

  const inviteTeamMember = async () => {
    if (!inviteEmail.trim()) {
      setToast({ message: 'Please enter an email address', type: 'error' });
      return;
    }

    setInviting(true);
    try {
      const data = await api.inviteTeamMember(inviteEmail, inviteName || undefined, inviteRole);
      setTeamMembers([...teamMembers, data]);
      setInviteEmail('');
      setInviteName('');
      setInviteRole('member');
      setShowInviteModal(false);
      setToast({ message: 'Team member invited successfully', type: 'success' });
    } catch (error: any) {
      console.error('Error inviting team member:', error);
      if (error.message?.includes('400')) {
        setToast({ message: 'Email already exists', type: 'error' });
      } else {
        setToast({ message: 'Failed to invite team member', type: 'error' });
      }
    } finally {
      setInviting(false);
    }
  };

  const removeTeamMember = async (memberId: number) => {
    if (!confirm('Are you sure you want to remove this team member?')) {
      return;
    }

    try {
      await api.removeTeamMember(memberId);
      setTeamMembers(teamMembers.filter(m => m.id !== memberId));
      setToast({ message: 'Team member removed successfully', type: 'success' });
    } catch (error: any) {
      console.error('Error removing team member:', error);
      if (error.message?.includes('400')) {
        setToast({ message: 'Cannot remove the last admin', type: 'error' });
      } else {
        setToast({ message: 'Failed to remove team member', type: 'error' });
      }
    }
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setToast({ message: 'Copied to clipboard', type: 'success' });
  };

  // OAuth Functions
  const fetchOAuthConfigs = async () => {
    setLoadingOAuth(true);
    try {
      const data = await api.getOAuthConfigs(organizationId);
      setOauthConfigs(data);
    } catch (error) {
      console.error('Error fetching OAuth configs:', error);
      setToast({ message: 'Failed to load OAuth configurations', type: 'error' });
    } finally {
      setLoadingOAuth(false);
    }
  };

  const openOAuthModal = async (provider?: string) => {
    if (provider) {
      // Editing existing config
      const existing = oauthConfigs.find(c => c.provider === provider);
      setEditingProvider(provider);
      setOauthForm({
        provider,
        client_id: existing?.client_id || '',
        client_secret: '', // Never pre-fill secret
        custom_scopes: existing?.custom_scopes?.join(', ') || '',
        enabled: existing?.enabled ?? true,
      });
    } else {
      // New config
      setEditingProvider(null);
      setOauthForm({
        provider: '',
        client_id: '',
        client_secret: '',
        custom_scopes: '',
        enabled: true,
      });
    }
    setRedirectUri(null);
    setShowOAuthModal(true);
  };

  const fetchRedirectUri = async (provider: string) => {
    try {
      const result = await api.getOAuthRedirectUri(provider, window.location.origin);
      setRedirectUri(result.redirect_uri);
    } catch (error) {
      console.error('Error fetching redirect URI:', error);
    }
  };

  const saveOAuthConfig = async () => {
    if (!oauthForm.provider) {
      setToast({ message: 'Please select a provider', type: 'error' });
      return;
    }
    if (!oauthForm.client_id.trim()) {
      setToast({ message: 'Client ID is required', type: 'error' });
      return;
    }
    if (!editingProvider && !oauthForm.client_secret.trim()) {
      setToast({ message: 'Client Secret is required for new configurations', type: 'error' });
      return;
    }

    setSavingOAuth(true);
    try {
      const customScopes = oauthForm.custom_scopes
        .split(',')
        .map(s => s.trim())
        .filter(s => s.length > 0);

      await api.saveOAuthConfig(oauthForm.provider, organizationId, {
        client_id: oauthForm.client_id,
        client_secret: oauthForm.client_secret,
        custom_scopes: customScopes.length > 0 ? customScopes : undefined,
        enabled: oauthForm.enabled,
      });

      setShowOAuthModal(false);
      await fetchOAuthConfigs();
      setToast({ message: `OAuth configuration for ${oauthForm.provider} saved successfully`, type: 'success' });
    } catch (error) {
      console.error('Error saving OAuth config:', error);
      setToast({ message: 'Failed to save OAuth configuration', type: 'error' });
    } finally {
      setSavingOAuth(false);
    }
  };

  const deleteOAuthConfig = async (provider: string) => {
    if (!confirm(`Are you sure you want to delete your custom OAuth configuration for ${provider}? This will revert to the platform default.`)) {
      return;
    }

    try {
      await api.deleteOAuthConfig(provider, organizationId);
      await fetchOAuthConfigs();
      setToast({ message: `Custom OAuth configuration for ${provider} deleted`, type: 'success' });
    } catch (error) {
      console.error('Error deleting OAuth config:', error);
      setToast({ message: 'Failed to delete OAuth configuration', type: 'error' });
    }
  };

  const renderApiKeysTab = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0 }}>API Keys</h2>
          <p style={{ color: 'var(--text-secondary)', margin: '8px 0 0' }}>Manage API keys for programmatic access</p>
        </div>
        <button className="btn-primary" onClick={() => setShowCreateKeyModal(true)}>
          <Plus size={18} />Create API Key
        </button>
      </div>

      {/* Newly created key banner */}
      {newlyCreatedKey && (
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '16px', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '8px', marginBottom: '24px', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
          <CheckCircle size={18} style={{ color: '#10b981', flexShrink: 0 }} />
          <div style={{ flex: 1 }}>
            <strong style={{ display: 'block', marginBottom: '4px', color: '#10b981' }}>API Key Created</strong>
            <code style={{ display: 'block', padding: '8px 12px', background: 'white', borderRadius: '4px', fontSize: '13px', fontFamily: 'monospace' }}>
              {newlyCreatedKey}
            </code>
            <p style={{ margin: '8px 0 0', fontSize: '13px', color: 'var(--text-secondary)' }}>
              Copy this key now. You won't be able to see it again.
            </p>
          </div>
          <button className="btn-secondary" style={{ padding: '8px' }} onClick={() => copyToClipboard(newlyCreatedKey)}>
            <Copy size={16} />
          </button>
          <button className="btn-secondary" style={{ padding: '8px' }} onClick={() => setNewlyCreatedKey(null)}>
            <X size={16} />
          </button>
        </div>
      )}

      {loadingKeys ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
          <Loader2 size={24} className="animate-spin" />
        </div>
      ) : apiKeys.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
          <Key size={48} style={{ opacity: 0.3, marginBottom: '16px' }} />
          <p>No API keys yet. Create one to get started.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {apiKeys.map((apiKey) => (
            <div key={apiKey.id} className="chart-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <h3 style={{ fontSize: '16px', fontWeight: 600, margin: 0 }}>{apiKey.name}</h3>
                  <span className={`status-badge ${apiKey.is_active ? 'success' : 'error'}`}>
                    <CheckCircle size={12} />{apiKey.is_active ? 'active' : 'revoked'}
                  </span>
                </div>
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    className="btn-secondary"
                    style={{ padding: '8px', color: 'var(--error-color)' }}
                    onClick={() => revokeApiKey(apiKey.id)}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>

              <div style={{ marginBottom: '16px' }}>
                <code style={{ display: 'block', padding: '12px 16px', background: 'var(--bg-secondary)', borderRadius: '6px', fontSize: '13px', fontFamily: 'monospace' }}>
                  {apiKey.key_prefix}...
                </code>
                <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px', fontSize: '12px', color: 'var(--text-muted)' }}>
                  <Info size={14} />
                  <span>Full key is only shown once at creation for security</span>
                </div>
              </div>

              <div style={{ display: 'flex', gap: '24px', fontSize: '13px', color: 'var(--text-secondary)' }}>
                <span>Created: {new Date(apiKey.created_at).toLocaleDateString()}</span>
                {apiKey.last_used_at && <span>Last used: {new Date(apiKey.last_used_at).toLocaleDateString()}</span>}
                {apiKey.expires_at && <span>Expires: {new Date(apiKey.expires_at).toLocaleDateString()}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', padding: '16px', background: 'rgba(245, 158, 11, 0.1)', borderRadius: '8px', marginTop: '24px' }}>
        <AlertTriangle size={18} style={{ color: '#f59e0b', flexShrink: 0, marginTop: '2px' }} />
        <div>
          <strong style={{ display: 'block', marginBottom: '4px' }}>Security Notice</strong>
          <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-secondary)' }}>API keys provide full access to your account. Keep them secure and never share them publicly.</p>
        </div>
      </div>

      {/* Create Key Modal */}
      {showCreateKeyModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: 'white', borderRadius: '12px', padding: '24px', width: '400px', maxWidth: '90vw' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: '18px', fontWeight: 600 }}>Create API Key</h3>
            <input
              type="text"
              placeholder="Key name (e.g., Production API)"
              value={newKeyName}
              onChange={(e) => setNewKeyName(e.target.value)}
              style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '14px', marginBottom: '16px' }}
            />
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button className="btn-secondary" onClick={() => setShowCreateKeyModal(false)}>Cancel</button>
              <button className="btn-primary" onClick={createApiKey} disabled={creatingKey}>
                {creatingKey ? <Loader2 size={16} className="animate-spin" /> : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderTeamTab = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0 }}>Team Members</h2>
          <p style={{ color: 'var(--text-secondary)', margin: '8px 0 0' }}>Manage who has access to your organization</p>
        </div>
        <button className="btn-primary" onClick={() => setShowInviteModal(true)}>
          <Plus size={18} />Invite Member
        </button>
      </div>

      {loadingTeam ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
          <Loader2 size={24} className="animate-spin" />
        </div>
      ) : (
        <div className="team-table">
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: 'var(--bg-secondary)', textAlign: 'left' }}>
                <th style={{ padding: '14px 20px', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Member</th>
                <th style={{ padding: '14px 20px', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Role</th>
                <th style={{ padding: '14px 20px', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Status</th>
                <th style={{ padding: '14px 20px', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Joined</th>
                <th style={{ padding: '14px 20px', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {teamMembers.map((member) => (
                <tr key={member.id} style={{ borderTop: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '16px 20px' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                      <div style={{ width: '36px', height: '36px', borderRadius: '8px', background: 'linear-gradient(135deg, var(--primary-color), #8b5cf6)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 600, fontSize: '13px' }}>
                        {(member.name || member.email).split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)}
                      </div>
                      <div>
                        <div style={{ fontWeight: 500, color: 'var(--text-primary)', fontSize: '14px' }}>{member.name || 'Invited User'}</div>
                        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{member.email}</div>
                      </div>
                    </div>
                  </td>
                  <td style={{ padding: '16px 20px' }}>
                    <span className={`role-badge ${member.role}`}>{member.role}</span>
                  </td>
                  <td style={{ padding: '16px 20px' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: 'var(--text-secondary)', textTransform: 'capitalize' }}>
                      <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: member.status === 'active' ? '#10b981' : '#f59e0b' }} />
                      {member.status}
                    </span>
                  </td>
                  <td style={{ padding: '16px 20px', fontSize: '13px', color: 'var(--text-muted)' }}>
                    {member.joined_at ? new Date(member.joined_at).toLocaleDateString() : '-'}
                  </td>
                  <td style={{ padding: '16px 20px' }}>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      {member.role !== 'admin' && (
                        <button
                          className="btn-secondary"
                          style={{ padding: '6px 12px', fontSize: '12px', color: 'var(--error-color)' }}
                          onClick={() => removeTeamMember(member.id)}
                        >
                          Remove
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

      {/* Invite Modal */}
      {showInviteModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: 'white', borderRadius: '12px', padding: '24px', width: '400px', maxWidth: '90vw' }}>
            <h3 style={{ margin: '0 0 16px', fontSize: '18px', fontWeight: 600 }}>Invite Team Member</h3>
            <input
              type="email"
              placeholder="Email address"
              value={inviteEmail}
              onChange={(e) => setInviteEmail(e.target.value)}
              style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '14px', marginBottom: '12px' }}
            />
            <input
              type="text"
              placeholder="Name (optional)"
              value={inviteName}
              onChange={(e) => setInviteName(e.target.value)}
              style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '14px', marginBottom: '12px' }}
            />
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value)}
              style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '14px', marginBottom: '16px' }}
            >
              <option value="member">Member</option>
              <option value="admin">Admin</option>
              <option value="viewer">Viewer</option>
            </select>
            <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
              <button className="btn-secondary" onClick={() => setShowInviteModal(false)}>Cancel</button>
              <button className="btn-primary" onClick={inviteTeamMember} disabled={inviting}>
                {inviting ? <Loader2 size={16} className="animate-spin" /> : 'Invite'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderOAuthAppsTab = () => (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '24px' }}>
        <div>
          <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0 }}>OAuth Applications</h2>
          <p style={{ color: 'var(--text-secondary)', margin: '8px 0 0' }}>Configure custom OAuth credentials for integrations</p>
        </div>
        <button className="btn-primary" onClick={() => openOAuthModal()}>
          <Plus size={18} />Add OAuth App
        </button>
      </div>

      {/* Info Banner */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', padding: '16px', background: 'rgba(99, 102, 241, 0.1)', borderRadius: '8px', marginBottom: '24px', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
        <Info size={18} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '2px' }} />
        <div>
          <strong style={{ display: 'block', marginBottom: '4px', color: 'var(--primary-color)' }}>Hybrid OAuth Support</strong>
          <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-secondary)' }}>
            By default, integrations use platform-managed OAuth apps. Enterprise customers can configure their own OAuth applications for enhanced security and control.
          </p>
        </div>
      </div>

      {loadingOAuth ? (
        <div style={{ display: 'flex', justifyContent: 'center', padding: '40px' }}>
          <Loader2 size={24} className="animate-spin" />
        </div>
      ) : oauthConfigs.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-secondary)' }}>
          <KeyRound size={48} style={{ opacity: 0.3, marginBottom: '16px' }} />
          <p>No custom OAuth configurations yet.</p>
          <p style={{ fontSize: '14px' }}>Using platform-managed OAuth apps for all integrations.</p>
        </div>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          {oauthConfigs.map((config) => {
            const providerInfo = OAUTH_PROVIDERS.find(p => p.id === config.provider);
            return (
              <div key={config.provider} className="chart-card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '16px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <div style={{ width: '40px', height: '40px', borderRadius: '8px', background: 'linear-gradient(135deg, var(--primary-color), #8b5cf6)', display: 'flex', alignItems: 'center', justifyContent: 'center', color: 'white', fontWeight: 600, fontSize: '14px' }}>
                      {config.provider.slice(0, 2).toUpperCase()}
                    </div>
                    <div>
                      <h3 style={{ fontSize: '16px', fontWeight: 600, margin: 0, display: 'flex', alignItems: 'center', gap: '8px' }}>
                        {providerInfo?.name || config.provider}
                        {config.is_custom ? (
                          <span style={{ fontSize: '11px', padding: '2px 8px', background: 'rgba(99, 102, 241, 0.1)', color: 'var(--primary-color)', borderRadius: '4px' }}>Custom</span>
                        ) : (
                          <span style={{ fontSize: '11px', padding: '2px 8px', background: 'rgba(16, 185, 129, 0.1)', color: '#10b981', borderRadius: '4px' }}>Platform Default</span>
                        )}
                        {!config.enabled && (
                          <span style={{ fontSize: '11px', padding: '2px 8px', background: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b', borderRadius: '4px' }}>Disabled</span>
                        )}
                      </h3>
                      <p style={{ fontSize: '13px', color: 'var(--text-muted)', margin: '4px 0 0' }}>
                        {providerInfo?.description || 'OAuth integration'}
                      </p>
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    {config.is_custom && (
                      <>
                        <button
                          className="btn-secondary"
                          style={{ padding: '8px' }}
                          onClick={() => openOAuthModal(config.provider)}
                          title="Edit configuration"
                        >
                          <Edit3 size={16} />
                        </button>
                        <button
                          className="btn-secondary"
                          style={{ padding: '8px', color: 'var(--error-color)' }}
                          onClick={() => deleteOAuthConfig(config.provider)}
                          title="Delete custom configuration"
                        >
                          <Trash2 size={16} />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '0', padding: '0', background: 'var(--bg-secondary)', borderRadius: '8px', overflow: 'hidden' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: '1px solid var(--border-color)' }}>
                    <div style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>Client ID</div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <code style={{ fontSize: '13px', fontFamily: 'monospace', background: 'white', padding: '6px 12px', borderRadius: '4px', border: '1px solid var(--border-color)' }}>{config.client_id_masked}</code>
                      <button
                        className="btn-secondary"
                        style={{ padding: '6px', border: 'none', background: 'transparent' }}
                        onClick={() => copyToClipboard(config.client_id)}
                        title="Copy full Client ID"
                      >
                        <Copy size={14} />
                      </button>
                    </div>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: config.custom_scopes && config.custom_scopes.length > 0 ? '1px solid var(--border-color)' : 'none' }}>
                    <div style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500 }}>Client Secret</div>
                    <div style={{ fontSize: '13px', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      {config.has_client_secret ? (
                        <>
                          <CheckCircle size={14} style={{ color: '#10b981' }} />
                          <span style={{ fontWeight: 500 }}>Configured</span>
                        </>
                      ) : (
                        <>
                          <AlertTriangle size={14} style={{ color: '#f59e0b' }} />
                          <span>Not set</span>
                        </>
                      )}
                    </div>
                  </div>
                  {config.custom_scopes && config.custom_scopes.length > 0 && (
                    <div style={{ padding: '16px 20px' }}>
                      <div style={{ fontSize: '13px', color: 'var(--text-muted)', fontWeight: 500, marginBottom: '12px' }}>Custom Scopes</div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
                        {config.custom_scopes.map((scope, i) => (
                          <span key={i} style={{ fontSize: '12px', padding: '6px 12px', background: 'white', borderRadius: '6px', border: '1px solid var(--border-color)' }}>
                            {scope}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {config.created_at && (
                  <div style={{ marginTop: '12px', fontSize: '12px', color: 'var(--text-muted)' }}>
                    Created: {new Date(config.created_at).toLocaleDateString()}
                    {config.updated_at && ` · Updated: ${new Date(config.updated_at).toLocaleDateString()}`}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* Add OAuth App Modal */}
      {showOAuthModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}>
          <div style={{ background: 'white', borderRadius: '12px', width: '500px', maxWidth: '90vw', maxHeight: '90vh', overflow: 'auto' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '20px 24px', borderBottom: '1px solid var(--border-color)' }}>
              <h3 style={{ margin: 0, fontSize: '18px', fontWeight: 600 }}>
                {editingProvider ? `Edit ${OAUTH_PROVIDERS.find(p => p.id === editingProvider)?.name || editingProvider} OAuth` : 'Add OAuth Application'}
              </h3>
              <button
                onClick={() => setShowOAuthModal(false)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', padding: '4px' }}
              >
                <X size={20} />
              </button>
            </div>

            <div style={{ padding: '24px' }}>
              {/* Provider Selection */}
              <div style={{ marginBottom: '20px' }}>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                  Provider <span style={{ color: 'var(--error-color)' }}>*</span>
                </label>
                <select
                  value={oauthForm.provider}
                  onChange={(e) => {
                    setOauthForm({ ...oauthForm, provider: e.target.value });
                    if (e.target.value) {
                      fetchRedirectUri(e.target.value);
                    }
                  }}
                  disabled={!!editingProvider}
                  style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '14px', background: editingProvider ? 'var(--bg-secondary)' : 'white' }}
                >
                  <option value="">Select a provider...</option>
                  {OAUTH_PROVIDERS.map((provider) => (
                    <option key={provider.id} value={provider.id}>
                      {provider.name} - {provider.description}
                    </option>
                  ))}
                </select>
              </div>

              {/* Redirect URI Info */}
              {(oauthForm.provider || editingProvider) && (
                <div style={{ marginBottom: '20px', padding: '16px', background: 'rgba(99, 102, 241, 0.05)', borderRadius: '8px', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
                  <div style={{ fontSize: '12px', fontWeight: 500, color: 'var(--primary-color)', marginBottom: '8px' }}>
                    Redirect URI (add this to your OAuth app)
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <code style={{ flex: 1, fontSize: '12px', padding: '8px 12px', background: 'white', borderRadius: '4px', wordBreak: 'break-all' }}>
                      {redirectUri || `${window.location.origin}/api/oauth/callback/${oauthForm.provider || editingProvider}`}
                    </code>
                    <button
                      className="btn-secondary"
                      style={{ padding: '6px', flexShrink: 0 }}
                      onClick={() => copyToClipboard(redirectUri || `${window.location.origin}/api/oauth/callback/${oauthForm.provider || editingProvider}`)}
                    >
                      <Copy size={14} />
                    </button>
                  </div>
                </div>
              )}

              {/* Client ID */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                  Client ID <span style={{ color: 'var(--error-color)' }}>*</span>
                </label>
                <input
                  type="text"
                  placeholder="Enter your OAuth Client ID"
                  value={oauthForm.client_id}
                  onChange={(e) => setOauthForm({ ...oauthForm, client_id: e.target.value })}
                  style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '14px' }}
                />
              </div>

              {/* Client Secret */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                  Client Secret {!editingProvider && <span style={{ color: 'var(--error-color)' }}>*</span>}
                </label>
                <input
                  type="password"
                  placeholder={editingProvider ? 'Leave blank to keep existing secret' : 'Enter your OAuth Client Secret'}
                  value={oauthForm.client_secret}
                  onChange={(e) => setOauthForm({ ...oauthForm, client_secret: e.target.value })}
                  style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '14px' }}
                />
                {editingProvider && (
                  <p style={{ margin: '6px 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>
                    Leave blank to keep the existing client secret.
                  </p>
                )}
              </div>

              {/* Custom Scopes */}
              <div style={{ marginBottom: '16px' }}>
                <label style={{ display: 'block', fontSize: '14px', fontWeight: 500, marginBottom: '8px' }}>
                  Custom Scopes <span style={{ fontSize: '12px', fontWeight: 400, color: 'var(--text-muted)' }}>(optional)</span>
                </label>
                <input
                  type="text"
                  placeholder="e.g., read:user, repo, admin:org"
                  value={oauthForm.custom_scopes}
                  onChange={(e) => setOauthForm({ ...oauthForm, custom_scopes: e.target.value })}
                  style={{ width: '100%', padding: '10px 14px', border: '1px solid var(--border-color)', borderRadius: '8px', fontSize: '14px' }}
                />
                <p style={{ margin: '6px 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>
                  Comma-separated list of OAuth scopes. Leave empty to use default scopes.
                </p>
              </div>

              {/* Enabled Toggle */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '24px', padding: '12px 16px', background: 'var(--bg-secondary)', borderRadius: '8px' }}>
                <div>
                  <div style={{ fontWeight: 500 }}>Enable this configuration</div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>When disabled, falls back to platform default</div>
                </div>
                <label style={{ position: 'relative', width: '44px', height: '24px' }}>
                  <input
                    type="checkbox"
                    checked={oauthForm.enabled}
                    onChange={(e) => setOauthForm({ ...oauthForm, enabled: e.target.checked })}
                    style={{ display: 'none' }}
                  />
                  <span style={{
                    position: 'absolute',
                    inset: 0,
                    background: oauthForm.enabled ? 'var(--primary-color)' : '#d1d5db',
                    borderRadius: '12px',
                    cursor: 'pointer',
                    transition: '0.2s',
                  }}>
                    <span style={{
                      position: 'absolute',
                      top: '2px',
                      left: oauthForm.enabled ? '22px' : '2px',
                      width: '20px',
                      height: '20px',
                      background: 'white',
                      borderRadius: '50%',
                      transition: '0.2s',
                    }} />
                  </span>
                </label>
              </div>

              {/* Action Buttons */}
              <div style={{ display: 'flex', gap: '12px', justifyContent: 'flex-end' }}>
                <button className="btn-secondary" onClick={() => setShowOAuthModal(false)}>
                  Cancel
                </button>
                <button className="btn-primary" onClick={saveOAuthConfig} disabled={savingOAuth}>
                  {savingOAuth ? <Loader2 size={16} className="animate-spin" /> : (editingProvider ? 'Update' : 'Save')}
                </button>
              </div>
            </div>

            {/* Footer Help */}
            <div style={{ padding: '16px 24px', background: 'var(--bg-secondary)', borderTop: '1px solid var(--border-color)', fontSize: '13px', color: 'var(--text-muted)' }}>
              <strong>Need help?</strong> Create an OAuth app in your provider's developer console, then enter the credentials here.{' '}
              {oauthForm.provider && (
                <a
                  href={getProviderDocsUrl(oauthForm.provider)}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{ color: 'var(--primary-color)', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                >
                  View {OAUTH_PROVIDERS.find(p => p.id === oauthForm.provider)?.name} docs <ExternalLink size={12} />
                </a>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );

  const renderNotificationsTab = () => (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0 }}>Notification Preferences</h2>
        <p style={{ color: 'var(--text-secondary)', margin: '8px 0 0' }}>Configure how you want to receive alerts and updates</p>
      </div>

      <div className="chart-card">
        <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px' }}>Email Notifications</h3>
        {[
          { name: 'Workflow Failures', desc: 'Get notified when a workflow execution fails' },
          { name: 'Budget Alerts', desc: 'Notify when spending exceeds threshold' },
          { name: 'Weekly Reports', desc: 'Receive weekly usage and cost summaries' },
          { name: 'Security Alerts', desc: 'Important security notifications' },
        ].map((setting) => (
          <div key={setting.name} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 0', borderBottom: '1px solid var(--border-color)' }}>
            <div>
              <div style={{ fontWeight: 500 }}>{setting.name}</div>
              <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>{setting.desc}</div>
            </div>
            <label style={{ position: 'relative', width: '44px', height: '24px' }}>
              <input type="checkbox" defaultChecked style={{ display: 'none' }} />
              <span style={{ position: 'absolute', inset: 0, background: 'var(--primary-color)', borderRadius: '12px', cursor: 'pointer' }}>
                <span style={{ position: 'absolute', top: '2px', left: '22px', width: '20px', height: '20px', background: 'white', borderRadius: '50%', transition: '0.2s' }} />
              </span>
            </label>
          </div>
        ))}
      </div>
    </div>
  );

  const renderHIPAATab = () => (
    <div>
      <div style={{ marginBottom: '24px' }}>
        <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0 }}>HIPAA Compliance</h2>
        <p style={{ color: 'var(--text-secondary)', margin: '8px 0 0' }}>Business Associate compliance posture for the orchestration platform</p>
      </div>

      {/* Status Card */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '20px', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '12px', marginBottom: '24px', border: '1px solid rgba(16, 185, 129, 0.3)' }}>
        <div style={{ width: '48px', height: '48px', borderRadius: '12px', background: '#10b981', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
          <Shield size={24} style={{ color: 'white' }} />
        </div>
        <div>
          <div style={{ fontWeight: 600, fontSize: '16px', color: '#065f46' }}>HIPAA Compliant</div>
          <div style={{ fontSize: '13px', color: '#047857' }}>All safeguards are active and enforced</div>
        </div>
        <div style={{ marginLeft: 'auto', padding: '6px 16px', background: '#10b981', color: 'white', borderRadius: '20px', fontSize: '13px', fontWeight: 600 }}>
          Enforced
        </div>
      </div>

      {/* Role & Safeguards */}
      <div className="chart-card" style={{ marginBottom: '16px' }}>
        <h3 style={{ fontSize: '16px', fontWeight: 600, marginBottom: '16px' }}>Platform Role</h3>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid var(--border-color)' }}>
          <div>
            <div style={{ fontWeight: 500 }}>Business Associate</div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Processes PHI on behalf of healthcare covered entities</div>
          </div>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid var(--border-color)' }}>
          <div>
            <div style={{ fontWeight: 500 }}>PHI Detection Middleware</div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Scans all POST/PUT/PATCH requests for PHI patterns</div>
          </div>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: '#10b981', fontWeight: 500 }}>
            <CheckCircle size={14} /> Active
          </span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid var(--border-color)' }}>
          <div>
            <div style={{ fontWeight: 500 }}>Audit Logging</div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Comprehensive logging with tamper-evident records</div>
          </div>
          <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>7-year retention</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid var(--border-color)' }}>
          <div>
            <div style={{ fontWeight: 500 }}>Encryption</div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>Data protected in transit and at rest</div>
          </div>
          <span style={{ fontSize: '13px', color: 'var(--text-secondary)' }}>TLS 1.2+ / AES-256</span>
        </div>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0' }}>
          <div>
            <div style={{ fontWeight: 500 }}>Access Control</div>
            <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>RBAC with API key authentication and multi-tenant isolation</div>
          </div>
          <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: '#10b981', fontWeight: 500 }}>
            <CheckCircle size={14} /> Enabled
          </span>
        </div>
      </div>

      {/* BAA Requirements */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', padding: '16px', background: 'rgba(99, 102, 241, 0.1)', borderRadius: '8px', border: '1px solid rgba(99, 102, 241, 0.2)' }}>
        <Info size={18} style={{ color: 'var(--primary-color)', flexShrink: 0, marginTop: '2px' }} />
        <div>
          <strong style={{ display: 'block', marginBottom: '4px', color: 'var(--primary-color)' }}>BAA Required</strong>
          <p style={{ margin: 0, fontSize: '14px', color: 'var(--text-secondary)' }}>
            A Business Associate Agreement is required for all healthcare tenants routing PHI through the platform.
            Covered data includes: agent task data, workflow inputs/outputs, and memory/RAG content.
          </p>
        </div>
      </div>
    </div>
  );

  const renderContent = () => {
    switch (activeTab) {
      case 'api-keys': return renderApiKeysTab();
      case 'oauth-apps': return renderOAuthAppsTab();
      case 'team': return renderTeamTab();
      case 'notifications': return renderNotificationsTab();
      case 'hipaa': return renderHIPAATab();
      default:
        return (
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '60px', color: 'var(--text-muted)', textAlign: 'center' }}>
            <Shield size={48} style={{ opacity: 0.3, marginBottom: '16px' }} />
            <h3 style={{ fontSize: '18px', fontWeight: 600, margin: '0 0 8px' }}>{tabs.find(t => t.id === activeTab)?.label} Settings</h3>
            <p style={{ margin: 0 }}>This settings section is coming soon</p>
          </div>
        );
    }
  };

  return (
    <div>
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

      {/* Page Header */}
      <div className="page-header">
        <div className="page-title">
          <h1>Settings</h1>
          <p>Manage your account and organization settings</p>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '240px 1fr', gap: '24px' }}>
        {/* Settings Navigation */}
        <nav style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '12px',
                  padding: '12px 16px',
                  border: 'none',
                  background: activeTab === tab.id ? 'rgba(99, 102, 241, 0.1)' : 'transparent',
                  color: activeTab === tab.id ? 'var(--primary-color)' : 'var(--text-secondary)',
                  borderRadius: '8px',
                  fontSize: '14px',
                  fontWeight: 500,
                  cursor: 'pointer',
                  textAlign: 'left',
                }}
              >
                <Icon size={18} />
                {tab.label}
              </button>
            );
          })}
        </nav>

        {/* Settings Content */}
        <div>{renderContent()}</div>
      </div>
    </div>
  );
}

export default SettingsPage;
