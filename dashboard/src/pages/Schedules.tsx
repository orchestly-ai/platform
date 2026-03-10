/**
 * Schedules Management Page
 *
 * Create, manage, and monitor scheduled workflow executions.
 * Supports cron, interval, and one-time schedules.
 */

import { useState, useEffect } from 'react';
import {
  Calendar,
  Clock,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Plus,
  Trash2,
  Play,
  Pause,
  Copy,
  Eye,
  X,
  Loader2,
  Settings,
  Zap,
  ExternalLink,
  History,
} from 'lucide-react';

// Types
interface Schedule {
  schedule_id: string;
  workflow_id: string;
  organization_id: string;
  name: string;
  description: string | null;
  schedule_type: 'cron' | 'interval' | 'once';
  cron_expression: string | null;
  interval_seconds: number | null;
  run_at: string | null;
  timezone: string;
  status: 'active' | 'paused' | 'disabled' | 'error';
  input_data: Record<string, unknown>;
  last_run_at: string | null;
  last_run_status: string | null;
  next_run_at: string | null;
  total_runs: number;
  successful_runs: number;
  failed_runs: number;
  total_cost: number;
  external_scheduler: boolean;
  external_trigger_url: string | null;
  created_at: string;
  updated_at: string;
}

interface ScheduleHistory {
  history_id: string;
  schedule_id: string;
  workflow_id: string;
  execution_id: string | null;
  scheduled_for: string;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  status: string;
  trigger_source: string;
  error_message: string | null;
  cost: number;
  tokens_used: number | null;
  created_at: string;
}

interface OrganizationLimits {
  organization_id: string;
  tier: string;
  max_schedules: number;
  min_interval_seconds: number;
  max_concurrent_executions: number;
  current_schedule_count: number;
  executions_this_month: number;
  cost_this_month: number;
  per_execution_cost: number;
}

interface CronHelpers {
  expressions: Record<string, string>;
  tier_limits: Record<string, {
    max_schedules: number;
    min_interval_seconds: number;
    max_concurrent_executions: number;
    per_execution_cost: number;
  }>;
}

interface Workflow {
  id: string;
  workflow_id?: string;
  name: string;
  description?: string;
  status?: string;
}

// Common cron presets for UI
const CRON_PRESETS = [
  { label: 'Every hour', value: '0 * * * *' },
  { label: 'Every day at 9 AM', value: '0 9 * * *' },
  { label: 'Every day at midnight', value: '0 0 * * *' },
  { label: 'Every Monday at 9 AM', value: '0 9 * * 1' },
  { label: 'Weekdays at 9 AM', value: '0 9 * * 1-5' },
  { label: 'First of month', value: '0 0 1 * *' },
];

const API_BASE = 'http://localhost:8000';
const ORG_ID = 'my-org'; // TODO: Get from auth context

export function SchedulesPage() {
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  const [limits, setLimits] = useState<OrganizationLimits | null>(null);
  const [workflows, setWorkflows] = useState<Workflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null);

  // Modal states
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showHistoryModal, setShowHistoryModal] = useState(false);
  const [selectedSchedule, setSelectedSchedule] = useState<Schedule | null>(null);
  const [history, setHistory] = useState<ScheduleHistory[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(false);

  // Form state
  const [form, setForm] = useState({
    name: '',
    description: '',
    workflow_id: '',
    schedule_type: 'cron' as 'cron' | 'interval' | 'once',
    cron_expression: '0 9 * * *',
    interval_seconds: 3600,
    run_at: '',
    timezone: 'UTC',
    external_scheduler: false,
    input_data: '{}',
  });

  // Toast auto-dismiss
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [toast]);

  // Fetch schedules, limits, and workflows
  useEffect(() => {
    fetchSchedules();
    fetchLimits();
    fetchWorkflows();
  }, []);

  const fetchWorkflows = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/workflows`, {
        headers: { 'X-API-Key': 'debug' },
      });
      if (response.ok) {
        const data = await response.json();
        setWorkflows(data.workflows || data || []);
      }
    } catch (error) {
      console.error('Failed to fetch workflows:', error);
    }
  };

  const fetchSchedules = async () => {
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE}/api/schedules`, {
        headers: { 'X-Organization-Id': ORG_ID },
      });
      if (response.ok) {
        const data = await response.json();
        setSchedules(data);
      }
    } catch (error) {
      console.error('Failed to fetch schedules:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchLimits = async () => {
    try {
      const response = await fetch(`${API_BASE}/api/schedules/limits`, {
        headers: { 'X-Organization-Id': ORG_ID },
      });
      if (response.ok) {
        const data = await response.json();
        setLimits(data);
      }
    } catch (error) {
      console.error('Failed to fetch limits:', error);
    }
  };

  const fetchHistory = async (scheduleId: string) => {
    setLoadingHistory(true);
    try {
      const response = await fetch(`${API_BASE}/api/schedules/${scheduleId}/history`, {
        headers: { 'X-Organization-Id': ORG_ID },
      });
      if (response.ok) {
        const data = await response.json();
        setHistory(data);
      }
    } catch (error) {
      console.error('Failed to fetch history:', error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const createSchedule = async () => {
    try {
      let inputData = {};
      try {
        inputData = JSON.parse(form.input_data);
      } catch {
        // Invalid JSON, use empty object
      }

      const payload: Record<string, unknown> = {
        workflow_id: form.workflow_id,
        name: form.name,
        description: form.description || null,
        schedule_type: form.schedule_type,
        timezone: form.timezone,
        external_scheduler: form.external_scheduler,
        input_data: inputData,
      };

      if (form.schedule_type === 'cron') {
        payload.cron_expression = form.cron_expression;
      } else if (form.schedule_type === 'interval') {
        payload.interval_seconds = form.interval_seconds;
      } else if (form.schedule_type === 'once') {
        payload.run_at = form.run_at;
      }

      const response = await fetch(`${API_BASE}/api/schedules`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Organization-Id': ORG_ID,
        },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        setToast({ message: 'Schedule created successfully', type: 'success' });
        setShowCreateModal(false);
        resetForm();
        fetchSchedules();
        fetchLimits();
      } else {
        const error = await response.json();
        setToast({ message: error.detail || 'Failed to create schedule', type: 'error' });
      }
    } catch (error) {
      setToast({ message: 'Failed to create schedule', type: 'error' });
    }
  };

  const deleteSchedule = async (scheduleId: string) => {
    if (!confirm('Are you sure you want to delete this schedule?')) return;

    try {
      const response = await fetch(`${API_BASE}/api/schedules/${scheduleId}`, {
        method: 'DELETE',
        headers: { 'X-Organization-Id': ORG_ID },
      });

      if (response.ok) {
        setToast({ message: 'Schedule deleted', type: 'success' });
        fetchSchedules();
        fetchLimits();
      }
    } catch (error) {
      setToast({ message: 'Failed to delete schedule', type: 'error' });
    }
  };

  const toggleSchedule = async (schedule: Schedule) => {
    const action = schedule.status === 'active' ? 'pause' : 'resume';
    try {
      const response = await fetch(`${API_BASE}/api/schedules/${schedule.schedule_id}/${action}`, {
        method: 'POST',
        headers: { 'X-Organization-Id': ORG_ID },
      });

      if (response.ok) {
        setToast({ message: `Schedule ${action}d`, type: 'success' });
        fetchSchedules();
      }
    } catch (error) {
      setToast({ message: `Failed to ${action} schedule`, type: 'error' });
    }
  };

  const copyTriggerUrl = (url: string) => {
    navigator.clipboard.writeText(`${API_BASE}${url}`);
    setToast({ message: 'Trigger URL copied to clipboard', type: 'success' });
  };

  const resetForm = () => {
    setForm({
      name: '',
      description: '',
      workflow_id: '',
      schedule_type: 'cron',
      cron_expression: '0 9 * * *',
      interval_seconds: 3600,
      run_at: '',
      timezone: 'UTC',
      external_scheduler: false,
      input_data: '{}',
    });
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'active':
        return <CheckCircle size={14} className="text-green-500" />;
      case 'paused':
        return <Pause size={14} className="text-yellow-500" />;
      case 'disabled':
        return <XCircle size={14} className="text-gray-400" />;
      case 'error':
        return <AlertTriangle size={14} className="text-red-500" />;
      default:
        return <Clock size={14} className="text-gray-400" />;
    }
  };

  const formatNextRun = (nextRun: string | null) => {
    if (!nextRun) return 'Not scheduled';
    const date = new Date(nextRun);
    const now = new Date();
    const diff = date.getTime() - now.getTime();

    if (diff < 0) return 'Overdue';
    if (diff < 60000) return 'In less than a minute';
    if (diff < 3600000) return `In ${Math.round(diff / 60000)} minutes`;
    if (diff < 86400000) return `In ${Math.round(diff / 3600000)} hours`;
    return date.toLocaleString();
  };

  const getWorkflowName = (workflowId: string) => {
    const workflow = workflows.find(w => w.id === workflowId);
    return workflow?.name || workflowId.slice(0, 8) + '...';
  };

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Toast */}
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 ${
            toast.type === 'success' ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
          }`}
        >
          {toast.type === 'success' ? <CheckCircle size={16} /> : <XCircle size={16} />}
          {toast.message}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <Calendar className="h-7 w-7 text-blue-600" />
            Scheduled Workflows
          </h1>
          <p className="text-gray-600 mt-1">
            Create and manage cron-based workflow schedules
          </p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={fetchSchedules}
            className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <Plus size={16} />
            New Schedule
          </button>
        </div>
      </div>

      {/* Limits Card */}
      {limits && (
        <div className="bg-white rounded-lg border border-gray-200 p-4 mb-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <div>
                <span className="text-sm text-gray-500">Tier</span>
                <p className="text-lg font-semibold capitalize">{limits.tier}</p>
              </div>
              <div className="h-8 border-l border-gray-200" />
              <div>
                <span className="text-sm text-gray-500">Schedules Used</span>
                <p className="text-lg font-semibold">
                  {limits.current_schedule_count} / {limits.max_schedules === -1 ? '∞' : limits.max_schedules}
                </p>
              </div>
              <div className="h-8 border-l border-gray-200" />
              <div>
                <span className="text-sm text-gray-500">Min Interval</span>
                <p className="text-lg font-semibold">
                  {limits.min_interval_seconds >= 3600
                    ? `${limits.min_interval_seconds / 3600}h`
                    : `${limits.min_interval_seconds / 60}m`}
                </p>
              </div>
              <div className="h-8 border-l border-gray-200" />
              <div>
                <span className="text-sm text-gray-500">Executions This Month</span>
                <p className="text-lg font-semibold">{limits.executions_this_month}</p>
              </div>
              <div className="h-8 border-l border-gray-200" />
              <div>
                <span className="text-sm text-gray-500">Cost This Month</span>
                <p className="text-lg font-semibold">${limits.cost_this_month.toFixed(2)}</p>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Schedules List */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <Loader2 className="h-8 w-8 animate-spin text-blue-600" />
        </div>
      ) : schedules.length === 0 ? (
        <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
          <Calendar className="h-12 w-12 mx-auto text-gray-300 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No schedules yet</h3>
          <p className="text-gray-500 mb-4">Create your first scheduled workflow to automate tasks</p>
          <button
            onClick={() => setShowCreateModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            <Plus size={16} />
            Create Schedule
          </button>
        </div>
      ) : (
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
          <table className="w-full">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Schedule</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Next Run</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Last Run</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Stats</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {schedules.map((schedule) => (
                <tr key={schedule.schedule_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <div>
                      <div className="font-medium text-gray-900">{schedule.name}</div>
                      <div className="text-xs text-gray-500">
                        Workflow: {getWorkflowName(schedule.workflow_id)}
                      </div>
                      {schedule.external_scheduler && (
                        <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 bg-purple-50 text-purple-600 rounded mt-1">
                          <ExternalLink size={10} />
                          BYOS
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {schedule.schedule_type === 'cron' && (
                      <div>
                        <div className="font-mono text-sm">{schedule.cron_expression}</div>
                        <div className="text-xs text-gray-500">{schedule.timezone}</div>
                      </div>
                    )}
                    {schedule.schedule_type === 'interval' && (
                      <div className="text-sm">
                        Every {schedule.interval_seconds! / 60} minutes
                      </div>
                    )}
                    {schedule.schedule_type === 'once' && (
                      <div className="text-sm">
                        One-time: {schedule.run_at ? new Date(schedule.run_at).toLocaleString() : 'N/A'}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-sm">{formatNextRun(schedule.next_run_at)}</div>
                  </td>
                  <td className="px-4 py-3">
                    {schedule.last_run_at ? (
                      <div>
                        <div className="text-sm">{new Date(schedule.last_run_at).toLocaleString()}</div>
                        <div className={`text-xs ${schedule.last_run_status === 'completed' ? 'text-green-600' : 'text-red-600'}`}>
                          {schedule.last_run_status}
                        </div>
                      </div>
                    ) : (
                      <span className="text-sm text-gray-400">Never</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <div className="text-sm">
                      <span className="text-green-600">{schedule.successful_runs}</span>
                      {' / '}
                      <span className="text-red-600">{schedule.failed_runs}</span>
                      {' / '}
                      <span className="text-gray-600">{schedule.total_runs}</span>
                    </div>
                    <div className="text-xs text-gray-500">${schedule.total_cost.toFixed(4)}</div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      {getStatusIcon(schedule.status)}
                      <span className="text-sm capitalize">{schedule.status}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      {schedule.external_trigger_url && (
                        <button
                          onClick={() => copyTriggerUrl(schedule.external_trigger_url!)}
                          className="p-1.5 text-gray-400 hover:text-gray-600"
                          title="Copy trigger URL"
                        >
                          <Copy size={16} />
                        </button>
                      )}
                      <button
                        onClick={() => {
                          setSelectedSchedule(schedule);
                          fetchHistory(schedule.schedule_id);
                          setShowHistoryModal(true);
                        }}
                        className="p-1.5 text-gray-400 hover:text-gray-600"
                        title="View history"
                      >
                        <History size={16} />
                      </button>
                      <button
                        onClick={() => toggleSchedule(schedule)}
                        className="p-1.5 text-gray-400 hover:text-gray-600"
                        title={schedule.status === 'active' ? 'Pause' : 'Resume'}
                      >
                        {schedule.status === 'active' ? <Pause size={16} /> : <Play size={16} />}
                      </button>
                      <button
                        onClick={() => deleteSchedule(schedule.schedule_id)}
                        className="p-1.5 text-red-400 hover:text-red-600"
                        title="Delete"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Create Schedule Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold">Create Schedule</h2>
              <button onClick={() => setShowCreateModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Name</label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  placeholder="Daily Report Generator"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Workflow</label>
                <select
                  value={form.workflow_id}
                  onChange={(e) => setForm({ ...form, workflow_id: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="">Select a workflow...</option>
                  {workflows.map((workflow) => (
                    <option key={workflow.id} value={workflow.id}>
                      {workflow.name} ({workflow.id.slice(0, 8)}...)
                    </option>
                  ))}
                </select>
                {workflows.length === 0 && (
                  <p className="text-xs text-amber-600 mt-1">
                    No workflows found. Create a workflow first in the Workflows page.
                  </p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Schedule Type</label>
                <select
                  value={form.schedule_type}
                  onChange={(e) => setForm({ ...form, schedule_type: e.target.value as 'cron' | 'interval' | 'once' })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  <option value="cron">Cron Expression</option>
                  <option value="interval">Fixed Interval</option>
                  <option value="once">One-Time</option>
                </select>
              </div>

              {form.schedule_type === 'cron' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Cron Expression</label>
                    <input
                      type="text"
                      value={form.cron_expression}
                      onChange={(e) => setForm({ ...form, cron_expression: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono"
                      placeholder="0 9 * * *"
                    />
                    <div className="mt-2 flex flex-wrap gap-2">
                      {CRON_PRESETS.map((preset) => (
                        <button
                          key={preset.value}
                          type="button"
                          onClick={() => setForm({ ...form, cron_expression: preset.value })}
                          className={`px-2 py-1 text-xs rounded ${
                            form.cron_expression === preset.value
                              ? 'bg-blue-100 text-blue-700'
                              : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                          }`}
                        >
                          {preset.label}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">Timezone</label>
                    <select
                      value={form.timezone}
                      onChange={(e) => setForm({ ...form, timezone: e.target.value })}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    >
                      <option value="UTC">UTC</option>
                      <option value="America/New_York">America/New_York</option>
                      <option value="America/Los_Angeles">America/Los_Angeles</option>
                      <option value="Europe/London">Europe/London</option>
                      <option value="Asia/Tokyo">Asia/Tokyo</option>
                    </select>
                  </div>
                </>
              )}

              {form.schedule_type === 'interval' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Interval (seconds)</label>
                  <input
                    type="number"
                    value={form.interval_seconds}
                    onChange={(e) => setForm({ ...form, interval_seconds: parseInt(e.target.value) || 3600 })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                    min={limits?.min_interval_seconds || 60}
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Minimum: {limits?.min_interval_seconds || 3600} seconds for your tier
                  </p>
                </div>
              )}

              {form.schedule_type === 'once' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">Run At</label>
                  <input
                    type="datetime-local"
                    value={form.run_at}
                    onChange={(e) => setForm({ ...form, run_at: e.target.value })}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  />
                </div>
              )}

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="external_scheduler"
                  checked={form.external_scheduler}
                  onChange={(e) => setForm({ ...form, external_scheduler: e.target.checked })}
                  className="rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                />
                <label htmlFor="external_scheduler" className="text-sm text-gray-700">
                  Use external scheduler (BYOS mode)
                </label>
              </div>
              {form.external_scheduler && (
                <p className="text-xs text-gray-500 bg-purple-50 p-2 rounded">
                  You'll receive a trigger URL to call from your own scheduler (AWS EventBridge, GCP Cloud Scheduler, etc.)
                </p>
              )}

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Input Data (JSON)</label>
                <textarea
                  value={form.input_data}
                  onChange={(e) => setForm({ ...form, input_data: e.target.value })}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
                  rows={3}
                  placeholder='{"key": "value"}'
                />
              </div>
            </div>
            <div className="flex justify-end gap-3 p-4 border-t border-gray-200">
              <button
                onClick={() => setShowCreateModal(false)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg"
              >
                Cancel
              </button>
              <button
                onClick={createSchedule}
                disabled={!form.name || !form.workflow_id}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Create Schedule
              </button>
            </div>
          </div>
        </div>
      )}

      {/* History Modal */}
      {showHistoryModal && selectedSchedule && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <div>
                <h2 className="text-lg font-semibold">Execution History</h2>
                <p className="text-sm text-gray-500">{selectedSchedule.name}</p>
              </div>
              <button onClick={() => setShowHistoryModal(false)} className="text-gray-400 hover:text-gray-600">
                <X size={20} />
              </button>
            </div>
            <div className="p-4">
              {loadingHistory ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
                </div>
              ) : history.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  No execution history yet
                </div>
              ) : (
                <div className="space-y-3">
                  {history.map((item) => (
                    <div key={item.history_id} className="border border-gray-200 rounded-lg p-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          {item.status === 'completed' ? (
                            <CheckCircle size={16} className="text-green-500" />
                          ) : item.status === 'failed' ? (
                            <XCircle size={16} className="text-red-500" />
                          ) : (
                            <Clock size={16} className="text-yellow-500" />
                          )}
                          <span className="font-medium capitalize">{item.status}</span>
                        </div>
                        <span className="text-sm text-gray-500">
                          {new Date(item.scheduled_for).toLocaleString()}
                        </span>
                      </div>
                      {item.duration_seconds && (
                        <div className="text-sm text-gray-600 mt-1">
                          Duration: {item.duration_seconds.toFixed(2)}s | Cost: ${item.cost.toFixed(4)}
                          {item.tokens_used && ` | Tokens: ${item.tokens_used}`}
                        </div>
                      )}
                      {item.error_message && (
                        <div className="text-sm text-red-600 mt-1 bg-red-50 p-2 rounded">
                          {item.error_message}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default SchedulesPage;
