/**
 * WorkflowsList Page - List all workflows
 * Shows workflows with stats, filters, and quick actions
 * Links to WorkflowDesigner for visual building
 */

import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Search,
  Plus,
  MoreVertical,
  Play,
  Pause,
  Edit,
  Clock,
  CheckCircle,
  ArrowUpRight,
  GitBranch,
  Users,
  Wand2,
  AlertCircle,
  Activity,
  BarChart3,
  Zap,
  Store,
  Upload,
  X,
} from 'lucide-react';
import { api } from '@/services/api';

interface WorkflowItem {
  id: string;
  name: string;
  description: string;
  team: string;
  status: 'active' | 'paused' | 'draft';
  executions: number;
  successRate: number;
  avgDuration: string;
  lastRun: string;
  createdBy: string;
  tags: string[];
  monthlyCost: number;
}

const workflowCategories = [
  'customer_service', 'sales_automation', 'engineering', 'marketing',
  'analytics', 'productivity', 'data_processing', 'hr', 'finance',
  'legal', 'security', 'devops', 'general',
];

export function WorkflowsListPage() {
  const navigate = useNavigate();
  const [workflows, setWorkflows] = useState<WorkflowItem[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'active' | 'paused' | 'draft'>('all');
  const [openMenu, setOpenMenu] = useState<string | null>(null);

  // Publish as template state
  const [publishWorkflow, setPublishWorkflow] = useState<WorkflowItem | null>(null);
  const [publishForm, setPublishForm] = useState({ tagline: '', description: '', category: 'general', tags: '' });
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);

  const handlePublishAsTemplate = async () => {
    if (!publishWorkflow) return;
    if (!publishForm.tagline.trim()) {
      setPublishError('Tagline is required.');
      return;
    }
    try {
      setPublishing(true);
      setPublishError(null);
      const tags = publishForm.tags.split(',').map(t => t.trim()).filter(Boolean);
      await api.publishWorkflowAsTemplate({
        workflow_id: publishWorkflow.id,
        name: publishWorkflow.name,
        tagline: publishForm.tagline.trim(),
        description: publishForm.description.trim() || publishForm.tagline.trim(),
        category: publishForm.category,
        tags,
      });
      setPublishWorkflow(null);
      setPublishForm({ tagline: '', description: '', category: 'general', tags: '' });
      alert(`"${publishWorkflow.name}" published as a template in the Marketplace!`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to publish.';
      setPublishError(msg);
    } finally {
      setPublishing(false);
    }
  };

  useEffect(() => {
    async function fetchWorkflows() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await api.getWorkflows();
        const transformedWorkflows: WorkflowItem[] = data.map(w => ({
          id: w.id,
          name: w.name,
          description: 'Workflow description',
          team: 'General',
          status: w.status === 'template' ? 'draft' : 'active' as const,
          executions: 0,
          successRate: 0,
          avgDuration: '-',
          lastRun: 'Never',
          createdBy: 'Unknown',
          tags: [],
          monthlyCost: 0,
        }));
        setWorkflows(transformedWorkflows);
      } catch (err) {
        console.error('Error fetching workflows:', err);
        setError(err instanceof Error ? err.message : 'Failed to fetch workflows');
      } finally {
        setIsLoading(false);
      }
    }

    fetchWorkflows();
  }, []);

  const filteredWorkflows = workflows.filter((wf) => {
    const matchesSearch = wf.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      wf.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      wf.team.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || wf.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const getStatusIcon = (status: WorkflowItem['status']) => {
    switch (status) {
      case 'active': return <CheckCircle size={14} />;
      case 'paused': return <Pause size={14} />;
      case 'draft': return <Edit size={14} />;
    }
  };

  const getStatusCount = (status: 'all' | 'active' | 'paused' | 'draft') => {
    if (status === 'all') return workflows.length;
    return workflows.filter(w => w.status === status).length;
  };

  // Stats
  const totalWorkflows = workflows.length;
  const activeWorkflows = workflows.filter(w => w.status === 'active').length;
  const avgSuccessRate = workflows.length > 0
    ? (workflows.reduce((sum, w) => sum + w.successRate, 0) / workflows.length).toFixed(0)
    : '0';
  const totalExecutions = workflows.reduce((sum, w) => sum + w.executions, 0);

  // Loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <GitBranch className="h-12 w-12 mx-auto mb-3 animate-pulse" style={{ color: 'var(--accent)' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Loading workflows...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
            <GitBranch className="h-7 w-7" style={{ color: 'var(--accent)' }} />
            Workflows
          </h1>
          <p className="mt-1" style={{ color: 'var(--text-secondary)' }}>
            Manage and monitor your automation workflows
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            to="/marketplace?type=workflow_template"
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors"
            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)', textDecoration: 'none' }}
          >
            <Store size={16} /> Browse Templates
          </Link>
          <Link
            to="/workflows/builder"
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors"
            style={{ background: 'var(--accent)', color: 'var(--bg-primary)', textDecoration: 'none' }}
          >
            <Plus size={16} /> Blank Canvas
          </Link>
        </div>
      </div>

      {/* Stats Section */}
      <div className="rounded-lg p-6" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[
            { value: totalWorkflows, label: 'Total Workflows', Icon: GitBranch, iconColor: 'var(--accent)' },
            { value: activeWorkflows, label: 'Active', Icon: Zap, iconColor: 'var(--green)' },
            { value: `${avgSuccessRate}%`, label: 'Avg Success Rate', Icon: BarChart3, iconColor: 'var(--cyan)' },
            { value: totalExecutions.toLocaleString(), label: 'Total Executions', Icon: Activity, iconColor: 'var(--purple)' },
          ].map((stat) => (
            <div key={stat.label} className="rounded-lg p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}>
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 rounded-lg" style={{ background: 'var(--bg-tertiary)' }}>
                  <stat.Icon className="h-5 w-5" style={{ color: stat.iconColor }} />
                </div>
                <span className="text-sm" style={{ color: 'var(--text-secondary)' }}>{stat.label}</span>
              </div>
              <p className="text-2xl font-bold" style={{ color: 'var(--text-primary)' }}>{stat.value}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="rounded-lg p-4" style={{ background: 'color-mix(in srgb, var(--error) 10%, var(--bg-secondary))', border: '1px solid var(--error)' }}>
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 flex-shrink-0" style={{ color: 'var(--error)' }} />
            <div>
              <p className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Failed to load workflows</p>
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Filters */}
      {!error && (
        <div className="flex gap-4 items-center flex-wrap">
          {/* Search */}
          <div className="relative flex-1 max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
            <input
              type="text"
              placeholder="Search workflows..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 px-3 py-2 rounded-lg text-sm"
              style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
            />
          </div>

          {/* Status filter */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium" style={{ color: 'var(--text-tertiary)' }}>Status:</span>
            {(['all', 'active', 'paused', 'draft'] as const).map((status) => {
              const isActive = statusFilter === status;
              const statusColor = status === 'active' ? 'var(--green)' : status === 'paused' ? 'var(--yellow)' : 'var(--accent)';
              return (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors capitalize"
                  style={{
                    border: isActive ? `1px solid ${statusColor}` : '1px solid var(--border-primary)',
                    background: isActive ? statusColor : 'var(--bg-primary)',
                    color: isActive ? 'var(--bg-primary)' : 'var(--text-secondary)',
                  }}
                >
                  {status} ({getStatusCount(status)})
                </button>
              );
            })}
          </div>
        </div>
      )}

      {/* Workflows Grid */}
      {!error && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {filteredWorkflows.map((workflow) => (
            <div
              key={workflow.id}
              className="rounded-lg overflow-hidden"
              style={{
                background: 'var(--bg-secondary)',
                border: '1px solid var(--border-primary)',
                borderLeft: '3px solid var(--green)',
              }}
            >
              {/* Header */}
              <div className="flex items-center justify-between p-4" style={{ borderBottom: '1px solid var(--border-primary)' }}>
                <div className="flex items-center gap-3">
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center"
                    style={{
                      background: 'color-mix(in srgb, var(--green) 15%, transparent)',
                      color: 'var(--green)',
                    }}
                  >
                    <GitBranch size={16} />
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-md capitalize"
                      style={{
                        background: workflow.status === 'active'
                          ? 'color-mix(in srgb, var(--green) 15%, transparent)'
                          : workflow.status === 'paused'
                          ? 'color-mix(in srgb, var(--yellow) 15%, transparent)'
                          : 'var(--bg-tertiary)',
                        color: workflow.status === 'active'
                          ? 'var(--green)'
                          : workflow.status === 'paused'
                          ? 'var(--yellow)'
                          : 'var(--text-tertiary)',
                      }}
                    >
                      {getStatusIcon(workflow.status)} {workflow.status}
                    </span>
                  </div>
                </div>
                <div className="relative">
                  <button
                    className="p-1"
                    style={{ color: 'var(--text-tertiary)' }}
                    onClick={(e) => { e.stopPropagation(); setOpenMenu(openMenu === workflow.id ? null : workflow.id); }}
                  >
                    <MoreVertical size={16} />
                  </button>
                  {openMenu === workflow.id && (
                    <div
                      className="absolute right-0 top-8 z-10 rounded-lg py-1 min-w-[180px] shadow-lg"
                      style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}
                    >
                      <button
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-opacity-10"
                        style={{ color: 'var(--text-secondary)' }}
                        onClick={(e) => { e.stopPropagation(); navigate(`/workflows/builder?id=${workflow.id}`); setOpenMenu(null); }}
                      >
                        <Edit size={14} /> Edit Workflow
                      </button>
                      <button
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm text-left hover:bg-opacity-10"
                        style={{ color: 'var(--cyan)' }}
                        onClick={(e) => {
                          e.stopPropagation();
                          setPublishError(null);
                          setPublishForm({ tagline: '', description: '', category: 'general', tags: '' });
                          setPublishWorkflow(workflow);
                          setOpenMenu(null);
                        }}
                      >
                        <Upload size={14} /> Publish as Template
                      </button>
                    </div>
                  )}
                </div>
              </div>

              {/* Content */}
              <div
                className="p-4 cursor-pointer"
                onClick={() => navigate(`/workflows/builder?id=${workflow.id}`)}
              >
                <h3 className="text-base font-semibold mb-1" style={{ color: 'var(--text-primary)' }}>{workflow.name}</h3>
                <p className="text-xs font-mono mb-2" style={{ color: 'var(--text-tertiary)' }}>
                  ID: {workflow.id}
                </p>
                <p className="text-sm mb-3 line-clamp-2" style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}>{workflow.description}</p>

                <div className="flex gap-2 mb-3">
                  <span
                    className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-md"
                    style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}
                  >
                    <Users size={12} /> {workflow.team}
                  </span>
                  <span
                    className="text-xs font-semibold px-2 py-0.5 rounded-md"
                    style={{ background: 'color-mix(in srgb, var(--green) 15%, transparent)', color: 'var(--green)' }}
                  >
                    ${workflow.monthlyCost.toFixed(0)}/mo
                  </span>
                </div>

                {workflow.tags.length > 0 && (
                  <div className="flex gap-1.5 flex-wrap">
                    {workflow.tags.slice(0, 3).map((tag) => (
                      <span
                        key={tag}
                        className="text-xs px-2 py-0.5 rounded-md"
                        style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              {/* Stats */}
              <div className="grid grid-cols-3 gap-px" style={{ borderTop: '1px solid var(--border-primary)', background: 'var(--border-primary)' }}>
                {[
                  { value: workflow.executions.toLocaleString(), label: 'Executions' },
                  { value: `${workflow.successRate}%`, label: 'Success' },
                  { value: workflow.avgDuration, label: 'Avg Duration' },
                ].map((stat) => (
                  <div key={stat.label} className="text-center p-3" style={{ background: 'var(--bg-primary)' }}>
                    <div className="text-base font-bold" style={{ color: 'var(--text-primary)' }}>{stat.value}</div>
                    <div className="text-xs" style={{ color: 'var(--text-tertiary)' }}>{stat.label}</div>
                  </div>
                ))}
              </div>

              {/* Footer */}
              <div
                className="flex items-center justify-between px-4 py-3"
                style={{ background: 'var(--bg-tertiary)', borderTop: '1px solid var(--border-primary)' }}
              >
                <span className="flex items-center gap-1.5 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                  <Clock size={14} />
                  {workflow.lastRun}
                </span>
                <div className="flex gap-2">
                  <button
                    className="flex items-center gap-1 px-2 py-1 text-sm rounded-lg transition-colors"
                    style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)' }}
                    onClick={(e) => { e.stopPropagation(); navigate(`/workflows/builder?id=${workflow.id}`); }}
                    title="Edit workflow"
                  >
                    <Edit size={14} />
                  </button>
                  {workflow.status === 'active' ? (
                    <button
                      className="flex items-center p-1 rounded-lg"
                      style={{ background: 'color-mix(in srgb, var(--yellow) 15%, transparent)', color: 'var(--yellow)' }}
                      title="Pause workflow"
                    >
                      <Pause size={14} />
                    </button>
                  ) : (
                    <button
                      className="flex items-center p-1 rounded-lg"
                      style={{ background: 'color-mix(in srgb, var(--green) 15%, transparent)', color: 'var(--green)' }}
                      title="Resume workflow"
                    >
                      <Play size={14} />
                    </button>
                  )}
                  <button
                    className="flex items-center p-1 rounded-lg"
                    style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)' }}
                    title="View details"
                  >
                    <ArrowUpRight size={14} />
                  </button>
                </div>
              </div>
            </div>
          ))}

          {/* Create New Card */}
          <div
            className="rounded-lg flex flex-col items-center justify-center p-10 cursor-pointer transition-colors"
            style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}
            onClick={() => navigate('/workflows/builder')}
          >
            <div
              className="w-14 h-14 rounded-xl flex items-center justify-center mb-4"
              style={{ background: 'var(--bg-tertiary)' }}
            >
              <Plus size={24} style={{ color: 'var(--text-tertiary)' }} />
            </div>
            <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>Create New</h3>
            <p className="text-sm text-center" style={{ color: 'var(--text-tertiary)' }}>Start from a blank canvas or browse templates</p>
            <div className="mt-4 flex gap-2">
              <Link
                to="/workflows/builder"
                className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg"
                style={{ background: 'var(--accent)', color: 'var(--bg-primary)', textDecoration: 'none' }}
                onClick={(e) => e.stopPropagation()}
              >
                <Wand2 size={14} /> Blank Canvas
              </Link>
              <Link
                to="/marketplace?type=workflow_template"
                className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg"
                style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)', textDecoration: 'none' }}
                onClick={(e) => e.stopPropagation()}
              >
                <Store size={14} /> Templates
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Empty state (no workflows at all after filtering) */}
      {!error && filteredWorkflows.length === 0 && workflows.length > 0 && (
        <div className="rounded-lg p-6" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
          <div className="text-center py-12">
            <GitBranch className="h-12 w-12 mx-auto mb-3" style={{ color: 'var(--text-tertiary)' }} />
            <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
              No matching workflows
            </h3>
            <p className="text-sm mb-5 max-w-sm mx-auto" style={{ color: 'var(--text-secondary)' }}>
              Try adjusting your search or filters.
            </p>
            <button
              className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg mx-auto"
              style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)' }}
              onClick={() => { setSearchQuery(''); setStatusFilter('all'); }}
            >
              Clear Filters
            </button>
          </div>
        </div>
      )}

      {/* Publish as Template Modal */}
      {publishWorkflow && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)' }}
          onClick={() => setPublishWorkflow(null)}
        >
          <div
            className="rounded-2xl w-full max-w-md max-h-[85vh] flex flex-col"
            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-between items-center px-6 py-4" style={{ borderBottom: '1px solid var(--border-primary)' }}>
              <h2 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <Upload className="h-5 w-5" style={{ color: 'var(--cyan)' }} />
                Publish as Template
              </h2>
              <button onClick={() => setPublishWorkflow(null)} className="p-1" style={{ color: 'var(--text-tertiary)' }}>
                <X size={20} />
              </button>
            </div>
            <div className="px-6 py-4 flex flex-col gap-4">
              {publishError && (
                <div className="p-3 rounded-lg text-sm" style={{ background: 'color-mix(in srgb, var(--error) 15%, transparent)', border: '1px solid var(--error)', color: 'var(--error)' }}>
                  {publishError}
                </div>
              )}
              <div className="p-3 rounded-lg" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
                <p className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>{publishWorkflow.name}</p>
                <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>ID: {publishWorkflow.id}</p>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Tagline *</label>
                <input
                  type="text" value={publishForm.tagline}
                  onChange={e => setPublishForm(p => ({ ...p, tagline: e.target.value }))}
                  placeholder="A short description for the marketplace listing"
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Description</label>
                <textarea
                  value={publishForm.description}
                  onChange={e => setPublishForm(p => ({ ...p, description: e.target.value }))}
                  placeholder="Detailed description of what this workflow does..."
                  rows={3}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)', resize: 'vertical' }}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Category</label>
                <select
                  value={publishForm.category}
                  onChange={e => setPublishForm(p => ({ ...p, category: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                >
                  {workflowCategories.map(c => (
                    <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Tags (comma-separated)</label>
                <input
                  type="text" value={publishForm.tags}
                  onChange={e => setPublishForm(p => ({ ...p, tags: e.target.value }))}
                  placeholder="onboarding, automation, multi-step"
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 px-6 py-4" style={{ borderTop: '1px solid var(--border-primary)' }}>
              <button
                onClick={() => setPublishWorkflow(null)} disabled={publishing}
                className="px-4 py-2 text-sm font-medium rounded-lg"
                style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)' }}
              >Cancel</button>
              <button
                onClick={handlePublishAsTemplate} disabled={publishing}
                className="flex items-center gap-1 px-4 py-2 text-sm font-medium rounded-lg disabled:opacity-50"
                style={{ background: 'var(--cyan)', color: 'var(--bg-primary)' }}
              >{publishing ? 'Publishing...' : 'Publish Template'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default WorkflowsListPage;
