/**
 * Multi-Cloud Deployment Page - Enterprise Infrastructure Management
 *
 * Allows enterprise customers to:
 * - Manage deployments across AWS, Azure, GCP, and on-premises
 * - Configure auto-scaling policies
 * - Monitor deployment metrics
 * - Manage load balancers
 *
 * Backend: /api/v1/multicloud/*
 */

import { useState, useEffect } from 'react';
import {
  Cloud,
  Plus,
  Trash2,
  CheckCircle,
  AlertTriangle,
  X,
  Loader2,
  Server,
  Activity,
  Scale,
  Globe2,
  Cpu,
  Play,
  TrendingUp,
  BarChart3,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react';

type CloudProvider = 'aws' | 'azure' | 'gcp' | 'onprem';
type DeploymentStatus = 'pending' | 'deploying' | 'running' | 'scaling' | 'stopped' | 'failed' | 'terminated';

interface CloudAccount {
  id: number;
  provider: CloudProvider;
  account_name: string;
  account_id: string;
  region: string;
  is_default: boolean;
  is_active: boolean;
  created_at: string;
}

interface Deployment {
  id: number;
  name: string;
  agent_id?: number;
  cloud_account_id: number;
  provider: CloudProvider;
  region: string;
  instance_type: string;
  desired_instances: number;
  current_instances: number;
  status: DeploymentStatus;
  endpoint_url?: string;
  container_image?: string;
  cpu_limit?: string;
  memory_limit?: string;
  created_at: string;
  deployed_at?: string;
}

// AutoScalingPolicy interface - reserved for future auto-scaling UI
// interface AutoScalingPolicy {
//   id: number;
//   deployment_id: number;
//   min_instances: number;
//   max_instances: number;
//   target_cpu_percent: number;
//   target_memory_percent?: number;
//   scale_up_cooldown_seconds: number;
//   scale_down_cooldown_seconds: number;
//   is_enabled: boolean;
// }

interface LoadBalancer {
  id: number;
  name: string;
  provider: CloudProvider;
  lb_type: string;
  endpoint_url?: string;
  health_check_path: string;
  is_active: boolean;
}

interface DeploymentMetrics {
  timestamp: string;
  cpu_percent: number;
  memory_percent: number;
  requests_per_second: number;
  latency_p50_ms: number;
  latency_p99_ms: number;
  error_rate: number;
}

interface MultiCloudStats {
  total_deployments: number;
  running_deployments: number;
  total_instances: number;
  by_provider: Record<CloudProvider, number>;
  total_cost_estimate: number;
}

const PROVIDER_INFO: Record<CloudProvider, { name: string; color: string; icon: string }> = {
  aws: { name: 'Amazon AWS', color: 'orange', icon: '🔶' },
  azure: { name: 'Microsoft Azure', color: 'blue', icon: '🔷' },
  gcp: { name: 'Google Cloud', color: 'red', icon: '🔴' },
  onprem: { name: 'On-Premises', color: 'gray', icon: '🏢' },
};

const STATUS_COLORS: Record<DeploymentStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-800',
  deploying: 'bg-blue-100 text-blue-800',
  running: 'bg-green-100 text-green-800',
  scaling: 'bg-purple-100 text-purple-800',
  stopped: 'bg-gray-100 text-gray-800',
  failed: 'bg-red-100 text-red-800',
  terminated: 'bg-gray-100 text-gray-600',
};

const API_BASE = 'http://localhost:8000';

export function MulticloudPage() {
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'deployments' | 'accounts' | 'loadbalancers'>('deployments');
  const [deployments, setDeployments] = useState<Deployment[]>([]);
  const [accounts, setAccounts] = useState<CloudAccount[]>([]);
  const [loadBalancers, setLoadBalancers] = useState<LoadBalancer[]>([]);
  const [stats, setStats] = useState<MultiCloudStats | null>(null);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Modal states
  const [showDeployModal, setShowDeployModal] = useState(false);
  const [showAccountModal, setShowAccountModal] = useState(false);
  const [showMetricsModal, setShowMetricsModal] = useState(false);
  const [selectedDeployment, setSelectedDeployment] = useState<Deployment | null>(null);
  const [metrics, setMetrics] = useState<DeploymentMetrics[]>([]);
  const [saving, setSaving] = useState(false);

  // Form states
  const [deployForm, setDeployForm] = useState({
    name: '',
    cloud_account_id: 0,
    region: '',
    instance_type: 't3.medium',
    desired_instances: 2,
    container_image: '',
    cpu_limit: '1',
    memory_limit: '2Gi',
  });

  const [accountForm, setAccountForm] = useState({
    provider: 'aws' as CloudProvider,
    account_name: '',
    account_id: '',
    region: '',
    credentials: '',
  });

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
      const [deploymentsRes, accountsRes, lbsRes, statsRes] = await Promise.all([
        fetch(`${API_BASE}/api/v1/multicloud/deployments`),
        fetch(`${API_BASE}/api/v1/multicloud/accounts`),
        fetch(`${API_BASE}/api/v1/multicloud/load-balancers`),
        fetch(`${API_BASE}/api/v1/multicloud/stats`),
      ]);

      if (deploymentsRes.ok) setDeployments(await deploymentsRes.json());
      if (accountsRes.ok) setAccounts(await accountsRes.json());
      if (lbsRes.ok) setLoadBalancers(await lbsRes.json());
      if (statsRes.ok) setStats(await statsRes.json());
    } catch (error) {
      console.error('Error fetching data:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchMetrics = async (deploymentId: number) => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/multicloud/deployments/${deploymentId}/metrics?hours=24`);
      if (response.ok) {
        const data = await response.json();
        setMetrics(data);
      }
    } catch (error) {
      console.error('Error fetching metrics:', error);
    }
  };

  const createDeployment = async () => {
    if (!deployForm.name || !deployForm.cloud_account_id) {
      setToast({ message: 'Name and cloud account are required', type: 'error' });
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/multicloud/deployments`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(deployForm),
      });

      if (response.ok) {
        setToast({ message: 'Deployment created successfully', type: 'success' });
        setShowDeployModal(false);
        fetchData();
      } else {
        const error = await response.json();
        setToast({ message: error.detail || 'Failed to create deployment', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to create deployment', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const deployDeployment = async (deploymentId: number) => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/multicloud/deployments/${deploymentId}/deploy`, {
        method: 'POST',
      });

      if (response.ok) {
        setToast({ message: 'Deployment started', type: 'success' });
        fetchData();
      } else {
        setToast({ message: 'Failed to deploy', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to deploy', type: 'error' });
    }
  };

  const scaleDeployment = async (deploymentId: number, instances: number) => {
    try {
      const response = await fetch(`${API_BASE}/api/v1/multicloud/deployments/${deploymentId}/scale?desired_instances=${instances}`, {
        method: 'POST',
      });

      if (response.ok) {
        setToast({ message: `Scaling to ${instances} instances`, type: 'success' });
        fetchData();
      } else {
        setToast({ message: 'Failed to scale', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to scale', type: 'error' });
    }
  };

  const terminateDeployment = async (deploymentId: number) => {
    if (!confirm('Are you sure you want to terminate this deployment?')) return;

    try {
      const response = await fetch(`${API_BASE}/api/v1/multicloud/deployments/${deploymentId}`, {
        method: 'DELETE',
      });

      if (response.ok) {
        setToast({ message: 'Deployment terminated', type: 'success' });
        fetchData();
      } else {
        setToast({ message: 'Failed to terminate', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to terminate', type: 'error' });
    }
  };

  const createAccount = async () => {
    if (!accountForm.account_name || !accountForm.account_id) {
      setToast({ message: 'Account name and ID are required', type: 'error' });
      return;
    }

    setSaving(true);
    try {
      const response = await fetch(`${API_BASE}/api/v1/multicloud/accounts`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(accountForm),
      });

      if (response.ok) {
        setToast({ message: 'Cloud account added successfully', type: 'success' });
        setShowAccountModal(false);
        fetchData();
      } else {
        const error = await response.json();
        setToast({ message: error.detail || 'Failed to add account', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to add account', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const openMetricsModal = (deployment: Deployment) => {
    setSelectedDeployment(deployment);
    setShowMetricsModal(true);
    fetchMetrics(deployment.id);
  };

  const getProviderColor = (provider: CloudProvider) => {
    switch (provider) {
      case 'aws': return 'bg-orange-100 text-orange-800 border-orange-200';
      case 'azure': return 'bg-blue-100 text-blue-800 border-blue-200';
      case 'gcp': return 'bg-red-100 text-red-800 border-red-200';
      case 'onprem': return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
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
              <Cloud className="w-8 h-8 text-cyan-600" />
              Multi-Cloud Deployments
              <span className="text-sm font-normal text-cyan-600 bg-cyan-100 px-2 py-1 rounded">Enterprise</span>
            </h1>
            <p className="text-gray-600 mt-1">
              Deploy and manage infrastructure across AWS, Azure, GCP, and on-premises
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setShowAccountModal(true)}
              className="flex items-center gap-2 px-4 py-2 border border-cyan-600 text-cyan-600 rounded-lg hover:bg-cyan-50"
            >
              <Plus className="w-4 h-4" />
              Add Cloud Account
            </button>
            <button
              onClick={() => setShowDeployModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700"
            >
              <Plus className="w-4 h-4" />
              New Deployment
            </button>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-5 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Total Deployments</p>
                <p className="text-2xl font-bold">{stats.total_deployments}</p>
              </div>
              <Server className="w-8 h-8 text-cyan-500" />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Running</p>
                <p className="text-2xl font-bold">{stats.running_deployments}</p>
              </div>
              <Activity className="w-8 h-8 text-green-500" />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Total Instances</p>
                <p className="text-2xl font-bold">{stats.total_instances}</p>
              </div>
              <Cpu className="w-8 h-8 text-purple-500" />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Cloud Accounts</p>
                <p className="text-2xl font-bold">{accounts.length}</p>
              </div>
              <Globe2 className="w-8 h-8 text-blue-500" />
            </div>
          </div>
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm text-gray-500">Est. Monthly Cost</p>
                <p className="text-2xl font-bold">${stats.total_cost_estimate?.toLocaleString() || 0}</p>
              </div>
              <TrendingUp className="w-8 h-8 text-amber-500" />
            </div>
          </div>
        </div>
      )}

      {/* Provider Distribution */}
      {stats && stats.by_provider && (
        <div className="grid grid-cols-4 gap-4 mb-6">
          {Object.entries(stats.by_provider).map(([provider, count]) => (
            <div key={provider} className={`rounded-lg p-4 border ${getProviderColor(provider as CloudProvider)}`}>
              <div className="flex items-center gap-3">
                <span className="text-2xl">{PROVIDER_INFO[provider as CloudProvider]?.icon}</span>
                <div>
                  <p className="font-medium">{PROVIDER_INFO[provider as CloudProvider]?.name}</p>
                  <p className="text-sm">{count} deployment{count !== 1 ? 's' : ''}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Tabs */}
      <div className="bg-white rounded-lg shadow">
        <div className="border-b flex">
          <button
            onClick={() => setActiveTab('deployments')}
            className={`px-6 py-3 font-medium ${
              activeTab === 'deployments'
                ? 'text-cyan-600 border-b-2 border-cyan-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Server className="w-4 h-4 inline mr-2" />
            Deployments
          </button>
          <button
            onClick={() => setActiveTab('accounts')}
            className={`px-6 py-3 font-medium ${
              activeTab === 'accounts'
                ? 'text-cyan-600 border-b-2 border-cyan-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Cloud className="w-4 h-4 inline mr-2" />
            Cloud Accounts
          </button>
          <button
            onClick={() => setActiveTab('loadbalancers')}
            className={`px-6 py-3 font-medium ${
              activeTab === 'loadbalancers'
                ? 'text-cyan-600 border-b-2 border-cyan-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            <Scale className="w-4 h-4 inline mr-2" />
            Load Balancers
          </button>
        </div>

        <div className="p-6">
          {loading ? (
            <div className="flex justify-center p-12">
              <Loader2 className="w-8 h-8 animate-spin text-cyan-600" />
            </div>
          ) : (
            <>
              {activeTab === 'deployments' && (
                <div>
                  {deployments.length === 0 ? (
                    <div className="text-center py-12">
                      <Server className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                      <p className="text-gray-600 mb-4">No deployments yet</p>
                      <button
                        onClick={() => setShowDeployModal(true)}
                        className="px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700"
                      >
                        Create Deployment
                      </button>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {deployments.map((deployment) => (
                        <div key={deployment.id} className="border rounded-lg p-4 hover:border-cyan-200 transition-colors">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-4">
                              <div className={`w-12 h-12 rounded-lg flex items-center justify-center text-2xl ${
                                deployment.status === 'running' ? 'bg-green-100' : 'bg-gray-100'
                              }`}>
                                {PROVIDER_INFO[deployment.provider]?.icon}
                              </div>
                              <div>
                                <div className="flex items-center gap-2">
                                  <h3 className="font-semibold">{deployment.name}</h3>
                                  <span className={`text-xs px-2 py-0.5 rounded ${STATUS_COLORS[deployment.status]}`}>
                                    {deployment.status}
                                  </span>
                                </div>
                                <div className="text-sm text-gray-500 flex items-center gap-3 mt-1">
                                  <span>{PROVIDER_INFO[deployment.provider]?.name}</span>
                                  <span>•</span>
                                  <span>{deployment.region}</span>
                                  <span>•</span>
                                  <span>{deployment.instance_type}</span>
                                </div>
                              </div>
                            </div>

                            <div className="flex items-center gap-6">
                              {/* Instance Count */}
                              <div className="text-center">
                                <div className="flex items-center gap-1 text-lg font-semibold">
                                  <span>{deployment.current_instances}</span>
                                  <span className="text-gray-400">/</span>
                                  <span className="text-gray-500">{deployment.desired_instances}</span>
                                </div>
                                <p className="text-xs text-gray-500">instances</p>
                              </div>

                              {/* Quick Actions */}
                              <div className="flex items-center gap-2">
                                <button
                                  onClick={() => scaleDeployment(deployment.id, deployment.desired_instances + 1)}
                                  className="p-2 text-gray-500 hover:text-cyan-600 hover:bg-cyan-50 rounded"
                                  title="Scale Up"
                                  disabled={deployment.status !== 'running'}
                                >
                                  <ArrowUpRight className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => scaleDeployment(deployment.id, Math.max(1, deployment.desired_instances - 1))}
                                  className="p-2 text-gray-500 hover:text-cyan-600 hover:bg-cyan-50 rounded"
                                  title="Scale Down"
                                  disabled={deployment.status !== 'running' || deployment.desired_instances <= 1}
                                >
                                  <ArrowDownRight className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => openMetricsModal(deployment)}
                                  className="p-2 text-gray-500 hover:text-cyan-600 hover:bg-cyan-50 rounded"
                                  title="View Metrics"
                                >
                                  <BarChart3 className="w-4 h-4" />
                                </button>
                                {deployment.status === 'pending' && (
                                  <button
                                    onClick={() => deployDeployment(deployment.id)}
                                    className="p-2 text-gray-500 hover:text-green-600 hover:bg-green-50 rounded"
                                    title="Deploy"
                                  >
                                    <Play className="w-4 h-4" />
                                  </button>
                                )}
                                <button
                                  onClick={() => terminateDeployment(deployment.id)}
                                  className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded"
                                  title="Terminate"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              </div>
                            </div>
                          </div>

                          {deployment.endpoint_url && (
                            <div className="mt-3 pt-3 border-t">
                              <span className="text-sm text-gray-500">Endpoint: </span>
                              <a href={deployment.endpoint_url} target="_blank" rel="noopener noreferrer" className="text-sm text-cyan-600 hover:underline">
                                {deployment.endpoint_url}
                              </a>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'accounts' && (
                <div>
                  {accounts.length === 0 ? (
                    <div className="text-center py-12">
                      <Cloud className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                      <p className="text-gray-600 mb-4">No cloud accounts configured</p>
                      <button
                        onClick={() => setShowAccountModal(true)}
                        className="px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700"
                      >
                        Add Cloud Account
                      </button>
                    </div>
                  ) : (
                    <div className="grid grid-cols-2 gap-4">
                      {accounts.map((account) => (
                        <div key={account.id} className={`border rounded-lg p-4 ${getProviderColor(account.provider)}`}>
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-3">
                              <span className="text-2xl">{PROVIDER_INFO[account.provider]?.icon}</span>
                              <div>
                                <h3 className="font-semibold">{account.account_name}</h3>
                                <p className="text-sm opacity-75">{PROVIDER_INFO[account.provider]?.name}</p>
                              </div>
                            </div>
                            {account.is_default && (
                              <span className="text-xs bg-white/50 px-2 py-1 rounded">Default</span>
                            )}
                          </div>
                          <div className="text-sm space-y-1">
                            <p><span className="opacity-75">Account ID:</span> {account.account_id}</p>
                            <p><span className="opacity-75">Region:</span> {account.region}</p>
                            <p><span className="opacity-75">Status:</span> {account.is_active ? 'Active' : 'Inactive'}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {activeTab === 'loadbalancers' && (
                <div>
                  {loadBalancers.length === 0 ? (
                    <div className="text-center py-12">
                      <Scale className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                      <p className="text-gray-600">No load balancers configured</p>
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {loadBalancers.map((lb) => (
                        <div key={lb.id} className="border rounded-lg p-4">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-3">
                              <Scale className="w-8 h-8 text-cyan-600" />
                              <div>
                                <h3 className="font-semibold">{lb.name}</h3>
                                <p className="text-sm text-gray-500">{lb.lb_type} • {PROVIDER_INFO[lb.provider]?.name}</p>
                              </div>
                            </div>
                            <span className={`text-xs px-2 py-1 rounded ${lb.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'}`}>
                              {lb.is_active ? 'Active' : 'Inactive'}
                            </span>
                          </div>
                          {lb.endpoint_url && (
                            <div className="mt-3 pt-3 border-t text-sm">
                              <span className="text-gray-500">Endpoint: </span>
                              <span className="font-mono">{lb.endpoint_url}</span>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* Create Deployment Modal */}
      {showDeployModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg">
            <div className="p-4 border-b flex items-center justify-between">
              <h2 className="text-lg font-semibold">Create Deployment</h2>
              <button onClick={() => setShowDeployModal(false)} className="text-gray-500 hover:text-gray-700">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Deployment Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={deployForm.name}
                  onChange={(e) => setDeployForm({ ...deployForm, name: e.target.value })}
                  placeholder="my-agent-deployment"
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Cloud Account <span className="text-red-500">*</span>
                </label>
                <select
                  value={deployForm.cloud_account_id}
                  onChange={(e) => setDeployForm({ ...deployForm, cloud_account_id: parseInt(e.target.value) })}
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                >
                  <option value={0}>Select account...</option>
                  {accounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.account_name} ({PROVIDER_INFO[account.provider]?.name})
                    </option>
                  ))}
                </select>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Region</label>
                  <input
                    type="text"
                    value={deployForm.region}
                    onChange={(e) => setDeployForm({ ...deployForm, region: e.target.value })}
                    placeholder="us-east-1"
                    className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Instance Type</label>
                  <select
                    value={deployForm.instance_type}
                    onChange={(e) => setDeployForm({ ...deployForm, instance_type: e.target.value })}
                    className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  >
                    <option value="t3.small">t3.small (2 vCPU, 2GB)</option>
                    <option value="t3.medium">t3.medium (2 vCPU, 4GB)</option>
                    <option value="t3.large">t3.large (2 vCPU, 8GB)</option>
                    <option value="m5.large">m5.large (2 vCPU, 8GB)</option>
                    <option value="m5.xlarge">m5.xlarge (4 vCPU, 16GB)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Desired Instances</label>
                <input
                  type="number"
                  value={deployForm.desired_instances}
                  onChange={(e) => setDeployForm({ ...deployForm, desired_instances: parseInt(e.target.value) || 1 })}
                  min={1}
                  max={100}
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Container Image</label>
                <input
                  type="text"
                  value={deployForm.container_image}
                  onChange={(e) => setDeployForm({ ...deployForm, container_image: e.target.value })}
                  placeholder="ghcr.io/org/agent:latest"
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">CPU Limit</label>
                  <input
                    type="text"
                    value={deployForm.cpu_limit}
                    onChange={(e) => setDeployForm({ ...deployForm, cpu_limit: e.target.value })}
                    placeholder="1"
                    className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Memory Limit</label>
                  <input
                    type="text"
                    value={deployForm.memory_limit}
                    onChange={(e) => setDeployForm({ ...deployForm, memory_limit: e.target.value })}
                    placeholder="2Gi"
                    className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                  />
                </div>
              </div>
            </div>

            <div className="p-4 border-t bg-gray-50 flex justify-end gap-3">
              <button
                onClick={() => setShowDeployModal(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={createDeployment}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                Create Deployment
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Add Cloud Account Modal */}
      {showAccountModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
            <div className="p-4 border-b flex items-center justify-between">
              <h2 className="text-lg font-semibold">Add Cloud Account</h2>
              <button onClick={() => setShowAccountModal(false)} className="text-gray-500 hover:text-gray-700">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Cloud Provider</label>
                <select
                  value={accountForm.provider}
                  onChange={(e) => setAccountForm({ ...accountForm, provider: e.target.value as CloudProvider })}
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                >
                  <option value="aws">Amazon AWS</option>
                  <option value="azure">Microsoft Azure</option>
                  <option value="gcp">Google Cloud</option>
                  <option value="onprem">On-Premises</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Account Name <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={accountForm.account_name}
                  onChange={(e) => setAccountForm({ ...accountForm, account_name: e.target.value })}
                  placeholder="Production AWS"
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Account ID <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={accountForm.account_id}
                  onChange={(e) => setAccountForm({ ...accountForm, account_id: e.target.value })}
                  placeholder="123456789012"
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Default Region</label>
                <input
                  type="text"
                  value={accountForm.region}
                  onChange={(e) => setAccountForm({ ...accountForm, region: e.target.value })}
                  placeholder="us-east-1"
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-cyan-500"
                />
              </div>

              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-3">
                <p className="text-sm text-yellow-800">
                  <AlertTriangle className="w-4 h-4 inline mr-1" />
                  Credentials should be configured via environment variables or IAM roles for security.
                </p>
              </div>
            </div>

            <div className="p-4 border-t bg-gray-50 flex justify-end gap-3">
              <button
                onClick={() => setShowAccountModal(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={createAccount}
                disabled={saving}
                className="flex items-center gap-2 px-4 py-2 bg-cyan-600 text-white rounded-lg hover:bg-cyan-700 disabled:opacity-50"
              >
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                Add Account
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Metrics Modal */}
      {showMetricsModal && selectedDeployment && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden">
            <div className="p-4 border-b flex items-center justify-between">
              <h2 className="text-lg font-semibold">
                Metrics - {selectedDeployment.name}
              </h2>
              <button onClick={() => setShowMetricsModal(false)} className="text-gray-500 hover:text-gray-700">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6">
              {metrics.length === 0 ? (
                <div className="text-center py-12">
                  <BarChart3 className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                  <p className="text-gray-600">No metrics available yet</p>
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Latest metrics summary */}
                  <div className="grid grid-cols-4 gap-4">
                    <div className="bg-blue-50 rounded-lg p-4">
                      <p className="text-sm text-blue-600">CPU Usage</p>
                      <p className="text-2xl font-bold text-blue-900">{metrics[metrics.length - 1]?.cpu_percent.toFixed(1)}%</p>
                    </div>
                    <div className="bg-purple-50 rounded-lg p-4">
                      <p className="text-sm text-purple-600">Memory Usage</p>
                      <p className="text-2xl font-bold text-purple-900">{metrics[metrics.length - 1]?.memory_percent.toFixed(1)}%</p>
                    </div>
                    <div className="bg-green-50 rounded-lg p-4">
                      <p className="text-sm text-green-600">Requests/sec</p>
                      <p className="text-2xl font-bold text-green-900">{metrics[metrics.length - 1]?.requests_per_second.toFixed(1)}</p>
                    </div>
                    <div className="bg-amber-50 rounded-lg p-4">
                      <p className="text-sm text-amber-600">P99 Latency</p>
                      <p className="text-2xl font-bold text-amber-900">{metrics[metrics.length - 1]?.latency_p99_ms.toFixed(0)}ms</p>
                    </div>
                  </div>

                  {/* Simple metrics table */}
                  <div className="border rounded-lg overflow-hidden">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50">
                        <tr>
                          <th className="px-4 py-2 text-left">Time</th>
                          <th className="px-4 py-2 text-right">CPU %</th>
                          <th className="px-4 py-2 text-right">Memory %</th>
                          <th className="px-4 py-2 text-right">RPS</th>
                          <th className="px-4 py-2 text-right">P50 (ms)</th>
                          <th className="px-4 py-2 text-right">P99 (ms)</th>
                          <th className="px-4 py-2 text-right">Error %</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y">
                        {metrics.slice(-10).reverse().map((m, i) => (
                          <tr key={i} className="hover:bg-gray-50">
                            <td className="px-4 py-2">{new Date(m.timestamp).toLocaleTimeString()}</td>
                            <td className="px-4 py-2 text-right">{m.cpu_percent.toFixed(1)}</td>
                            <td className="px-4 py-2 text-right">{m.memory_percent.toFixed(1)}</td>
                            <td className="px-4 py-2 text-right">{m.requests_per_second.toFixed(1)}</td>
                            <td className="px-4 py-2 text-right">{m.latency_p50_ms.toFixed(0)}</td>
                            <td className="px-4 py-2 text-right">{m.latency_p99_ms.toFixed(0)}</td>
                            <td className="px-4 py-2 text-right">{(m.error_rate * 100).toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MulticloudPage;
