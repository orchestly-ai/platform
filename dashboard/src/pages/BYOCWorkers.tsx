/**
 * BYOC Workers Page (Bring Your Own Compute)
 *
 * Monitor and manage customer-deployed workers that execute workflows
 * on their own infrastructure using their own LLM keys.
 */

import { useState, useEffect } from 'react';
import {
  Server,
  Plus,
  Trash2,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  X,
  Loader2,
  Play,
  Pause,
  Activity,
  Clock,
  Cpu,
  Zap,
  Download,
  Edit,
  Eye,
  Copy,
  Terminal,
  ExternalLink,
  Settings,
  BarChart3,
} from 'lucide-react';

// Types
interface BYOCWorker {
  worker_id: string;
  organization_id: string;
  status: 'online' | 'offline' | 'busy' | 'unhealthy';
  max_concurrent_jobs: number;
  current_job_id: string | null;
  jobs_completed: number;
  jobs_failed: number;
  total_duration_seconds: number;
  capabilities: string[] | null;
  metadata: Record<string, any> | null;
  last_heartbeat: string | null;
  registered_at: string;
}

interface WorkerJob {
  job_id: string;
  workflow_id: string;
  execution_id: string;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  tokens_used: number | null;
  cost: number | null;
  error: string | null;
}

const STATUS_COLORS: Record<string, string> = {
  online: 'bg-green-500',
  offline: 'bg-gray-500',
  busy: 'bg-blue-500',
  unhealthy: 'bg-red-500',
};

const STATUS_TEXT_COLORS: Record<string, string> = {
  online: 'text-green-600',
  offline: 'text-gray-600',
  busy: 'text-blue-600',
  unhealthy: 'text-red-600',
};

const API_BASE = 'http://localhost:8000';
const ORG_ID = 'my-org';

export function BYOCWorkersPage() {
  const [workers, setWorkers] = useState<BYOCWorker[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Modal states
  const [showSetupModal, setShowSetupModal] = useState(false);
  const [showJobsModal, setShowJobsModal] = useState(false);
  const [showRegisterModal, setShowRegisterModal] = useState(false);
  const [selectedWorker, setSelectedWorker] = useState<BYOCWorker | null>(null);
  const [workerJobs, setWorkerJobs] = useState<WorkerJob[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [copiedCommand, setCopiedCommand] = useState(false);
  const [registering, setRegistering] = useState(false);

  // Registration form
  const [registerForm, setRegisterForm] = useState({
    worker_id: '',
    max_concurrent_jobs: 2,
    capabilities: '',
    metadata: '{}',
  });

  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  useEffect(() => {
    fetchWorkers();
    // Poll for updates every 10 seconds
    const interval = setInterval(fetchWorkers, 10000);
    return () => clearInterval(interval);
  }, []);

  const fetchWorkers = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/byoc/workers`, {
        headers: { 'X-Organization-Id': ORG_ID },
      });
      if (response.ok) {
        const data = await response.json();
        setWorkers(data);
      }
    } catch (error) {
      console.error('Error fetching workers:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchWorkerJobs = async (workerId: string) => {
    setLoadingJobs(true);
    try {
      const response = await fetch(`${API_BASE}/api/byoc/workers/${workerId}/jobs`, {
        headers: { 'X-Organization-Id': ORG_ID },
      });
      if (response.ok) {
        const data = await response.json();
        setWorkerJobs(data);
      }
    } catch (error) {
      console.error('Error fetching worker jobs:', error);
    } finally {
      setLoadingJobs(false);
    }
  };

  const removeWorker = async (workerId: string) => {
    if (!confirm('Are you sure you want to remove this worker?')) return;

    try {
      const response = await fetch(`${API_BASE}/api/byoc/workers/${workerId}`, {
        method: 'DELETE',
        headers: { 'X-Organization-Id': ORG_ID },
      });

      if (response.ok) {
        setToast({ message: 'Worker removed', type: 'success' });
        fetchWorkers();
      } else {
        setToast({ message: 'Failed to remove worker', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to remove worker', type: 'error' });
    }
  };

  const registerWorker = async () => {
    if (!registerForm.worker_id.trim()) {
      setToast({ message: 'Worker ID is required', type: 'error' });
      return;
    }

    setRegistering(true);
    try {
      const capabilities = registerForm.capabilities
        .split(',')
        .map(c => c.trim())
        .filter(c => c.length > 0);

      let metadata = {};
      try {
        metadata = JSON.parse(registerForm.metadata || '{}');
      } catch {
        // Ignore invalid JSON
      }

      const response = await fetch(`${API_BASE}/api/byoc/workers/register`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Organization-Id': ORG_ID,
        },
        body: JSON.stringify({
          worker_id: registerForm.worker_id,
          max_concurrent_jobs: registerForm.max_concurrent_jobs,
          capabilities: capabilities.length > 0 ? capabilities : null,
          metadata: Object.keys(metadata).length > 0 ? metadata : null,
        }),
      });

      if (response.ok) {
        setToast({ message: 'Worker registered successfully', type: 'success' });
        setShowRegisterModal(false);
        setRegisterForm({
          worker_id: '',
          max_concurrent_jobs: 2,
          capabilities: '',
          metadata: '{}',
        });
        fetchWorkers();
      } else {
        const error = await response.json();
        setToast({ message: error.detail || 'Failed to register worker', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to register worker', type: 'error' });
    } finally {
      setRegistering(false);
    }
  };

  const pingWorker = async (workerId: string) => {
    try {
      // Send a heartbeat on behalf of the worker to check connectivity
      const response = await fetch(`${API_BASE}/api/byoc/workers/${workerId}/heartbeat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Organization-Id': ORG_ID,
        },
        body: JSON.stringify({ status: 'ping' }),
      });

      if (response.ok) {
        setToast({ message: 'Worker pinged successfully', type: 'success' });
        fetchWorkers();
      } else {
        setToast({ message: 'Worker not responding', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to ping worker', type: 'error' });
    }
  };

  const openJobsModal = (worker: BYOCWorker) => {
    setSelectedWorker(worker);
    setShowJobsModal(true);
    fetchWorkerJobs(worker.worker_id);
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'Never';
    return new Date(dateString).toLocaleString();
  };

  const formatDuration = (seconds: number | null) => {
    if (seconds === null || seconds === 0) return '0s';
    if (seconds < 60) return `${seconds.toFixed(1)}s`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.floor(seconds % 60)}s`;
    return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
  };

  const getTimeSinceHeartbeat = (lastHeartbeat: string | null) => {
    if (!lastHeartbeat) return 'Never';
    const diff = Date.now() - new Date(lastHeartbeat).getTime();
    const seconds = Math.floor(diff / 1000);
    if (seconds < 60) return `${seconds}s ago`;
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    return `${Math.floor(seconds / 3600)}h ago`;
  };

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedCommand(true);
    setTimeout(() => setCopiedCommand(false), 2000);
  };

  const setupCommand = `pip install orchestly-worker

# worker.py
from orchestly.byoc import Worker, LLMProviderConfig

worker = Worker(
    api_url="${API_BASE}",
    api_key="YOUR_API_KEY",
    organization_id="${ORG_ID}",
    max_concurrent_jobs=2,
    llm_providers=[
        LLMProviderConfig(
            provider="openai",
            api_key="sk-your-openai-key",
        ),
        LLMProviderConfig(
            provider="anthropic",
            api_key="sk-ant-your-anthropic-key",
        ),
    ],
)

if __name__ == "__main__":
    worker.start()`;

  const dockerCommand = `docker run -d \\
  --name byoc-worker \\
  -e API_URL="${API_BASE}" \\
  -e API_KEY="YOUR_API_KEY" \\
  -e ORG_ID="${ORG_ID}" \\
  -e OPENAI_API_KEY="sk-..." \\
  -e ANTHROPIC_API_KEY="sk-ant-..." \\
  orchestly/byoc-worker:latest`;

  // Calculate stats
  const totalWorkers = workers.length;
  const onlineWorkers = workers.filter(w => w.status === 'online' || w.status === 'busy').length;
  const totalJobsCompleted = workers.reduce((sum, w) => sum + w.jobs_completed, 0);
  const totalDuration = workers.reduce((sum, w) => sum + w.total_duration_seconds, 0);

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Server className="w-8 h-8 text-green-600" />
              BYOC Workers
              <span className="text-sm font-normal text-green-600 bg-green-100 px-2 py-1 rounded">BYOC</span>
            </h1>
            <p className="text-gray-600 mt-1">
              Deploy workers on your infrastructure with your own LLM keys
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setShowRegisterModal(true)}
              className="flex items-center gap-2 px-4 py-2 border border-green-600 text-green-600 rounded-lg hover:bg-green-50"
            >
              <Server className="w-4 h-4" />
              Register Worker
            </button>
            <button
              onClick={() => setShowSetupModal(true)}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
            >
              <Plus className="w-4 h-4" />
              Deploy Worker
            </button>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Workers</p>
              <p className="text-2xl font-bold">{totalWorkers}</p>
            </div>
            <Server className="w-8 h-8 text-green-500" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Online</p>
              <p className="text-2xl font-bold">{onlineWorkers} / {totalWorkers}</p>
            </div>
            <Activity className="w-8 h-8 text-blue-500" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Jobs Completed</p>
              <p className="text-2xl font-bold">{totalJobsCompleted.toLocaleString()}</p>
            </div>
            <CheckCircle className="w-8 h-8 text-emerald-500" />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Runtime</p>
              <p className="text-2xl font-bold">{formatDuration(totalDuration)}</p>
            </div>
            <Clock className="w-8 h-8 text-purple-500" />
          </div>
        </div>
      </div>

      {/* Workers List */}
      <div className="bg-white rounded-lg shadow">
        <div className="p-4 border-b flex items-center justify-between">
          <h2 className="text-lg font-semibold">Registered Workers</h2>
          <button
            onClick={fetchWorkers}
            className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>

        {loading ? (
          <div className="p-8 text-center">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-green-600" />
            <p className="mt-2 text-gray-500">Loading workers...</p>
          </div>
        ) : workers.length === 0 ? (
          <div className="p-8 text-center">
            <Server className="w-12 h-12 mx-auto text-gray-400" />
            <p className="mt-2 text-gray-500">No workers registered</p>
            <p className="text-sm text-gray-400">Deploy a worker to start executing workflows on your infrastructure</p>
            <button
              onClick={() => setShowSetupModal(true)}
              className="mt-4 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
            >
              Deploy Your First Worker
            </button>
          </div>
        ) : (
          <div className="divide-y">
            {workers.map((worker) => (
              <div key={worker.worker_id} className="p-4 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`w-12 h-12 rounded-lg ${STATUS_COLORS[worker.status]} flex items-center justify-center`}>
                      <Server className="w-6 h-6 text-white" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="font-semibold font-mono">{worker.worker_id}</h3>
                        <span className={`text-xs px-2 py-0.5 rounded capitalize ${
                          worker.status === 'online' ? 'bg-green-100 text-green-800' :
                          worker.status === 'busy' ? 'bg-blue-100 text-blue-800' :
                          worker.status === 'offline' ? 'bg-gray-100 text-gray-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {worker.status}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500">
                        Max concurrent: {worker.max_concurrent_jobs} | Last heartbeat: {getTimeSinceHeartbeat(worker.last_heartbeat)}
                      </p>
                      {worker.capabilities && worker.capabilities.length > 0 && (
                        <div className="flex gap-1 mt-1">
                          {worker.capabilities.map((cap) => (
                            <span key={cap} className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">
                              {cap}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="flex items-center gap-6">
                    {/* Stats */}
                    <div className="text-right">
                      <p className="text-sm font-medium text-green-600">
                        {worker.jobs_completed} completed
                      </p>
                      <p className="text-sm text-red-500">
                        {worker.jobs_failed} failed
                      </p>
                    </div>

                    {/* Runtime */}
                    <div className="text-right">
                      <p className="text-sm font-medium">{formatDuration(worker.total_duration_seconds)}</p>
                      <p className="text-xs text-gray-500">total runtime</p>
                    </div>

                    {/* Current Job */}
                    {worker.current_job_id && (
                      <div className="flex items-center gap-2 px-3 py-1.5 bg-blue-50 rounded-lg">
                        <Loader2 className="w-4 h-4 animate-spin text-blue-600" />
                        <span className="text-sm text-blue-700 font-mono">
                          {worker.current_job_id.slice(0, 8)}...
                        </span>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => openJobsModal(worker)}
                        className="p-2 text-gray-500 hover:text-blue-600 hover:bg-blue-50 rounded"
                        title="View Jobs"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => pingWorker(worker.worker_id)}
                        className="p-2 text-gray-500 hover:text-green-600 hover:bg-green-50 rounded"
                        title="Ping Worker"
                      >
                        <Zap className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => removeWorker(worker.worker_id)}
                        className="p-2 text-gray-500 hover:text-red-600 hover:bg-red-50 rounded"
                        title="Remove Worker"
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

      {/* Benefits Section */}
      <div className="mt-8 grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 bg-green-100 rounded-lg flex items-center justify-center">
              <Zap className="w-5 h-5 text-green-600" />
            </div>
            <h3 className="font-semibold">Your Infrastructure</h3>
          </div>
          <p className="text-sm text-gray-600">
            Run workers in your own cloud or on-premises. Data never leaves your environment.
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 bg-blue-100 rounded-lg flex items-center justify-center">
              <Cpu className="w-5 h-5 text-blue-600" />
            </div>
            <h3 className="font-semibold">Your LLM Keys</h3>
          </div>
          <p className="text-sm text-gray-600">
            Use your own OpenAI, Anthropic, or other LLM API keys. Full cost control and visibility.
          </p>
        </div>
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 bg-purple-100 rounded-lg flex items-center justify-center">
              <Activity className="w-5 h-5 text-purple-600" />
            </div>
            <h3 className="font-semibold">Auto-Scaling</h3>
          </div>
          <p className="text-sm text-gray-600">
            Workers auto-scale based on job queue depth. Only pay for what you use.
          </p>
        </div>
      </div>

      {/* Setup Modal */}
      {showSetupModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] overflow-y-auto">
            <div className="p-4 border-b flex items-center justify-between">
              <h2 className="text-lg font-semibold">Deploy a BYOC Worker</h2>
              <button onClick={() => setShowSetupModal(false)} className="text-gray-500 hover:text-gray-700">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-6">
              {/* Introduction */}
              <div className="bg-green-50 rounded-lg p-4">
                <h3 className="font-medium text-green-800 mb-2">What is BYOC?</h3>
                <p className="text-sm text-green-700">
                  BYOC (Bring Your Own Compute) allows you to run workflow execution workers on your own infrastructure.
                  Workers connect to the Orchestly control plane, poll for jobs, and execute them using your own LLM API keys.
                </p>
              </div>

              {/* Python Setup */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold flex items-center gap-2">
                    <Terminal className="w-4 h-4" />
                    Python Setup
                  </h3>
                  <button
                    onClick={() => copyToClipboard(setupCommand)}
                    className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
                  >
                    {copiedCommand ? (
                      <>
                        <CheckCircle className="w-4 h-4 text-green-500" />
                        Copied!
                      </>
                    ) : (
                      <>
                        <Copy className="w-4 h-4" />
                        Copy
                      </>
                    )}
                  </button>
                </div>
                <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg text-sm overflow-x-auto">
                  <code>{setupCommand}</code>
                </pre>
              </div>

              {/* Docker Setup */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h3 className="font-semibold flex items-center gap-2">
                    <Download className="w-4 h-4" />
                    Docker Setup
                  </h3>
                  <button
                    onClick={() => copyToClipboard(dockerCommand)}
                    className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700"
                  >
                    <Copy className="w-4 h-4" />
                    Copy
                  </button>
                </div>
                <pre className="bg-gray-900 text-gray-100 p-4 rounded-lg text-sm overflow-x-auto">
                  <code>{dockerCommand}</code>
                </pre>
              </div>

              {/* Requirements */}
              <div>
                <h3 className="font-semibold mb-3">Requirements</h3>
                <ul className="space-y-2 text-sm">
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-4 h-4 text-green-500 mt-0.5" />
                    <span>Python 3.9+ or Docker</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-4 h-4 text-green-500 mt-0.5" />
                    <span>Network access to the Orchestly API</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-4 h-4 text-green-500 mt-0.5" />
                    <span>Your own LLM API keys (OpenAI, Anthropic, etc.)</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="w-4 h-4 text-green-500 mt-0.5" />
                    <span>A valid Orchestly API key</span>
                  </li>
                </ul>
              </div>

              {/* Links */}
              <div className="flex gap-4">
                <a
                  href="#"
                  className="flex items-center gap-2 text-green-600 hover:text-green-700"
                >
                  <ExternalLink className="w-4 h-4" />
                  Full Documentation
                </a>
                <a
                  href="#"
                  className="flex items-center gap-2 text-green-600 hover:text-green-700"
                >
                  <ExternalLink className="w-4 h-4" />
                  SDK Reference
                </a>
              </div>
            </div>

            <div className="p-4 border-t bg-gray-50 flex justify-end">
              <button
                onClick={() => setShowSetupModal(false)}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
              >
                Got it
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Worker Jobs Modal */}
      {showJobsModal && selectedWorker && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
            <div className="p-4 border-b flex items-center justify-between">
              <h2 className="text-lg font-semibold">
                Jobs - <span className="font-mono">{selectedWorker.worker_id}</span>
              </h2>
              <button onClick={() => setShowJobsModal(false)} className="text-gray-500 hover:text-gray-700">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto">
              {loadingJobs ? (
                <div className="p-8 text-center">
                  <Loader2 className="w-8 h-8 animate-spin mx-auto text-green-600" />
                </div>
              ) : workerJobs.length === 0 ? (
                <div className="p-8 text-center">
                  <Play className="w-12 h-12 mx-auto text-gray-400" />
                  <p className="mt-2 text-gray-500">No jobs executed yet</p>
                </div>
              ) : (
                <table className="w-full">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Job ID</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Status</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Duration</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Tokens</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Cost</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-500">Completed</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {workerJobs.map((job) => (
                      <tr key={job.job_id} className="hover:bg-gray-50">
                        <td className="px-4 py-3">
                          <span className="font-mono text-sm">{job.job_id.slice(0, 12)}...</span>
                        </td>
                        <td className="px-4 py-3">
                          <span className={`text-xs px-2 py-1 rounded ${
                            job.status === 'completed' ? 'bg-green-100 text-green-800' :
                            job.status === 'failed' ? 'bg-red-100 text-red-800' :
                            job.status === 'running' ? 'bg-blue-100 text-blue-800' :
                            'bg-gray-100 text-gray-800'
                          }`}>
                            {job.status}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {formatDuration(job.duration_seconds)}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {job.tokens_used?.toLocaleString() || '-'}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {job.cost ? `$${job.cost.toFixed(4)}` : '-'}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-500">
                          {formatDate(job.completed_at)}
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

      {/* Register Worker Modal */}
      {showRegisterModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-md">
            <div className="p-4 border-b flex items-center justify-between">
              <h2 className="text-lg font-semibold">Register a Worker</h2>
              <button onClick={() => setShowRegisterModal(false)} className="text-gray-500 hover:text-gray-700">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 space-y-4">
              <div className="bg-blue-50 rounded-lg p-3 text-sm text-blue-700">
                <p>
                  Register a worker to reserve a slot. The worker will appear as "offline" until it starts sending heartbeats.
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Worker ID <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={registerForm.worker_id}
                  onChange={(e) => setRegisterForm({ ...registerForm, worker_id: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                  placeholder="worker-prod-1"
                />
                <p className="text-xs text-gray-500 mt-1">Unique identifier for this worker</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Max Concurrent Jobs
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={registerForm.max_concurrent_jobs}
                  onChange={(e) => setRegisterForm({ ...registerForm, max_concurrent_jobs: parseInt(e.target.value) || 1 })}
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                />
                <p className="text-xs text-gray-500 mt-1">Number of jobs this worker can run simultaneously</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Capabilities
                </label>
                <input
                  type="text"
                  value={registerForm.capabilities}
                  onChange={(e) => setRegisterForm({ ...registerForm, capabilities: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500"
                  placeholder="openai, anthropic, gpu"
                />
                <p className="text-xs text-gray-500 mt-1">Comma-separated list of capabilities (optional)</p>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Metadata (JSON)
                </label>
                <textarea
                  value={registerForm.metadata}
                  onChange={(e) => setRegisterForm({ ...registerForm, metadata: e.target.value })}
                  className="w-full border rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-green-500 font-mono text-sm"
                  rows={3}
                  placeholder='{"region": "us-east-1", "instance_type": "t3.large"}'
                />
                <p className="text-xs text-gray-500 mt-1">Additional metadata as JSON (optional)</p>
              </div>
            </div>

            <div className="p-4 border-t bg-gray-50 flex justify-end gap-2">
              <button
                onClick={() => setShowRegisterModal(false)}
                className="px-4 py-2 border rounded-lg hover:bg-gray-100"
              >
                Cancel
              </button>
              <button
                onClick={registerWorker}
                disabled={registering || !registerForm.worker_id.trim()}
                className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
              >
                {registering ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Registering...
                  </>
                ) : (
                  <>
                    <Plus className="w-4 h-4" />
                    Register Worker
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
        } text-white`}>
          {toast.message}
        </div>
      )}
    </div>
  );
}

export default BYOCWorkersPage;
