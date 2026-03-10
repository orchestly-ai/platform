/**
 * Marketplace Page - Discover and install pre-built agents
 *
 * Shows available agents with proper installed/not-installed states.
 * Prevents duplicate installations and provides uninstall functionality.
 */

import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Search,
  Download,
  Star,
  CheckCircle,
  TrendingUp,
  Trash2,
  Play,
  Plus,
  X,
  Store,
  Shield,
  ArrowRight,
  Bot,
  Briefcase,
  Code2,
  BarChart3,
  Zap,
  FileText,
  Database,
  Users,
  DollarSign,
  Scale,
  Lock,
  Settings,
  Puzzle,
  Workflow,
  GitBranch,
} from 'lucide-react';
import { api } from '@/services/api';

interface MarketplaceAgent {
  id: number;
  name: string;
  tagline: string;
  description: string;
  category: string;
  item_type: string;
  author: string;
  version: string;
  install_count: number;
  avg_rating: number;
  rating_count: number;
  pricing: string;
  verified: boolean;
  agent_config?: Record<string, unknown> | null;
}

interface Installation {
  id: number;
  agent_id: number;
  version: string;
  status: string;
  installed_agent_id: number | null;
  error_message: string | null;
  installed_at: string;
  auto_update: boolean;
}

const defaultPublishForm = {
  name: '',
  slug: '',
  tagline: '',
  description: '',
  category: 'customer_service',
  pricing: 'free',
  price_usd: 0,
  tags: '',
  model: '',
  temperature: 0.7,
  system_prompt: '',
  tools: '',
  version: '1.0.0',
};

const allCategories = [
  'customer_service', 'sales_automation', 'engineering', 'marketing',
  'analytics', 'productivity', 'data_processing', 'hr', 'finance',
  'legal', 'security', 'devops', 'general',
];

// Category metadata for consistent color coding
const categoryMeta: Record<string, { icon: React.ComponentType<{ size?: number; className?: string }>, color: string; label: string }> = {
  customer_service: { icon: Bot, color: 'var(--pink)', label: 'Customer Service' },
  sales_automation: { icon: Briefcase, color: 'var(--green)', label: 'Sales' },
  engineering: { icon: Code2, color: 'var(--orange)', label: 'Engineering' },
  marketing: { icon: TrendingUp, color: 'var(--pink)', label: 'Marketing' },
  analytics: { icon: BarChart3, color: 'var(--purple)', label: 'Analytics' },
  productivity: { icon: Zap, color: 'var(--cyan)', label: 'Productivity' },
  data_processing: { icon: Database, color: 'var(--orange)', label: 'Data Processing' },
  hr: { icon: Users, color: 'var(--purple)', label: 'HR' },
  hr_recruiting: { icon: Users, color: 'var(--purple)', label: 'HR & Recruiting' },
  finance: { icon: DollarSign, color: 'var(--green)', label: 'Finance' },
  finance_accounting: { icon: DollarSign, color: 'var(--green)', label: 'Finance' },
  legal: { icon: Scale, color: 'var(--purple)', label: 'Legal' },
  security: { icon: Lock, color: 'var(--pink)', label: 'Security' },
  devops: { icon: Settings, color: 'var(--orange)', label: 'DevOps' },
  general: { icon: Puzzle, color: 'var(--accent)', label: 'General' },
};

const getCategoryMeta = (category: string) => {
  return categoryMeta[category.toLowerCase()] || {
    icon: Puzzle,
    color: 'var(--accent)',
    label: category.replace(/_/g, ' '),
  };
};

export function MarketplacePage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const initialType = searchParams.get('type') || 'all';
  const [typeFilter, setTypeFilter] = useState<'all' | 'agent' | 'workflow_template'>(
    initialType as 'all' | 'agent' | 'workflow_template'
  );
  const [agents, setAgents] = useState<MarketplaceAgent[]>([]);
  const [featuredAgents, setFeaturedAgents] = useState<MarketplaceAgent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [installingAgents, setInstallingAgents] = useState<Set<number>>(new Set());
  const [uninstallingAgents, setUninstallingAgents] = useState<Set<number>>(new Set());
  const [installedAgents, setInstalledAgents] = useState<Map<number, Installation>>(new Map());
  const [showPublishModal, setShowPublishModal] = useState(false);
  const [publishForm, setPublishForm] = useState({ ...defaultPublishForm });
  const [publishing, setPublishing] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [usingTemplate, setUsingTemplate] = useState<Set<number>>(new Set());
  const [publishType, setPublishType] = useState<'agent' | 'workflow_template'>('agent');
  const [userWorkflows, setUserWorkflows] = useState<Array<{ id: string; name: string; status: string }>>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string>('');
  const [loadingWorkflows, setLoadingWorkflows] = useState(false);

  const categories = ['all', 'customer_service', 'sales_automation', 'engineering', 'marketing', 'analytics', 'productivity', 'data_processing', 'hr_recruiting', 'finance_accounting', 'legal'];

  const handleUseAgent = (agentName: string) => {
    navigate('/agents');
  };

  const handleUseTemplate = async (agentId: number) => {
    try {
      setUsingTemplate(prev => new Set(prev).add(agentId));
      const result = await api.useWorkflowTemplate(agentId);
      navigate(`/workflows/builder?id=${result.workflow_id}`);
    } catch (err) {
      console.error('Failed to use template:', err);
      alert(`Failed to create workflow from template: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setUsingTemplate(prev => {
        const next = new Set(prev);
        next.delete(agentId);
        return next;
      });
    }
  };

  useEffect(() => {
    loadFeaturedAgents();
    loadInstalledAgents();
  }, []);

  useEffect(() => {
    loadAgents();
  }, [searchQuery, categoryFilter, typeFilter]);

  const loadInstalledAgents = async () => {
    try {
      const installations = await api.getInstalledAgents();
      const installMap = new Map<number, Installation>();
      for (const inst of installations) {
        installMap.set(inst.agent_id, inst);
      }
      setInstalledAgents(installMap);
    } catch (err) {
      console.error('Failed to load installed agents:', err);
    }
  };

  const loadFeaturedAgents = async () => {
    try {
      const featured = await api.getFeaturedAgents(6);
      setFeaturedAgents(featured);
    } catch (err) {
      console.error('Failed to load featured agents:', err);
      setFeaturedAgents([]);
    }
  };

  const loadAgents = async () => {
    try {
      setLoading(true);
      setError(null);
      const query = searchQuery || undefined;
      const category = categoryFilter !== 'all' ? categoryFilter : undefined;
      const itemType = typeFilter !== 'all' ? typeFilter : undefined;
      const results = await api.searchAgents(query, category, itemType);
      setAgents(results);
    } catch (err) {
      console.error('Failed to load agents:', err);
      setError('Failed to load marketplace items. Please try again.');
      setAgents([]);
    } finally {
      setLoading(false);
    }
  };

  const loadUserWorkflows = async () => {
    try {
      setLoadingWorkflows(true);
      const workflows = await api.getWorkflows();
      setUserWorkflows(workflows.filter(w => w.status !== 'template'));
    } catch (err) {
      console.error('Failed to load workflows:', err);
      setUserWorkflows([]);
    } finally {
      setLoadingWorkflows(false);
    }
  };

  const handleInstall = async (agentId: number) => {
    if (installedAgents.has(agentId)) {
      alert('This agent is already installed. Use the Manage button to configure or uninstall.');
      return;
    }

    try {
      setInstallingAgents(prev => new Set(prev).add(agentId));
      await api.installAgent(agentId);
      await loadInstalledAgents();
      alert('Agent installed! Go to Agents page to use it in workflows.');
    } catch (err) {
      console.error('Failed to install agent:', err);
      const message = err instanceof Error ? err.message : 'Unknown error';
      if (message.includes('already installed')) {
        await loadInstalledAgents();
        alert('This agent is already installed.');
      } else {
        alert(`Failed to install agent: ${message}`);
      }
    } finally {
      setInstallingAgents(prev => {
        const next = new Set(prev);
        next.delete(agentId);
        return next;
      });
    }
  };

  const handleUninstall = async (agentId: number, agentName: string) => {
    const installation = installedAgents.get(agentId);
    if (!installation) {
      alert('Agent is not installed.');
      return;
    }

    const confirmed = window.confirm(
      `Are you sure you want to uninstall "${agentName}"?\n\n` +
      `This will remove the agent from your account.`
    );

    if (!confirmed) return;

    try {
      setUninstallingAgents(prev => new Set(prev).add(agentId));
      await api.uninstallAgent(installation.id);
      await loadInstalledAgents();
      alert(`"${agentName}" has been uninstalled.`);
    } catch (err) {
      console.error('Failed to uninstall agent:', err);
      alert(`Failed to uninstall agent: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setUninstallingAgents(prev => {
        const next = new Set(prev);
        next.delete(agentId);
        return next;
      });
    }
  };

  const [deletingAgents, setDeletingAgents] = useState<Set<number>>(new Set());

  const handleDeleteAgent = async (agentId: number, agentName: string) => {
    const confirmed = window.confirm(
      `Are you sure you want to delete "${agentName}" from the marketplace?\n\nThis will unpublish it and remove it from listings.`
    );
    if (!confirmed) return;

    try {
      setDeletingAgents(prev => new Set(prev).add(agentId));
      await api.deleteMarketplaceAgent(agentId);
      await loadAgents();
      await loadFeaturedAgents();
    } catch (err) {
      alert(`Failed to delete agent: ${err instanceof Error ? err.message : 'Unknown error'}`);
    } finally {
      setDeletingAgents(prev => {
        const next = new Set(prev);
        next.delete(agentId);
        return next;
      });
    }
  };

  const generateSlug = (name: string) =>
    name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');

  const updatePublishField = (field: string, value: string | number) => {
    setPublishForm(prev => {
      const updated = { ...prev, [field]: value };
      if (field === 'name') {
        updated.slug = generateSlug(value as string);
      }
      return updated;
    });
  };

  const handlePublish = async () => {
    if (!publishForm.name.trim() || !publishForm.tagline.trim() || !publishForm.description.trim()) {
      setPublishError('Name, tagline, and description are required.');
      return;
    }

    if (publishType === 'workflow_template') {
      if (!selectedWorkflowId) {
        setPublishError('Please select a workflow to publish as a template.');
        return;
      }
      try {
        setPublishing(true);
        setPublishError(null);
        const tags = publishForm.tags
          .split(',')
          .map(t => t.trim())
          .filter(Boolean);
        await api.publishWorkflowAsTemplate({
          workflow_id: selectedWorkflowId,
          name: publishForm.name.trim(),
          tagline: publishForm.tagline.trim(),
          description: publishForm.description.trim(),
          category: publishForm.category,
          tags,
        });
        setShowPublishModal(false);
        setPublishForm({ ...defaultPublishForm });
        setSelectedWorkflowId('');
        setPublishType('agent');
        await loadAgents();
        alert('Workflow template published successfully!');
      } catch (err) {
        const raw = err instanceof Error ? err.message : 'Failed to publish template.';
        setPublishError(raw);
      } finally {
        setPublishing(false);
      }
      return;
    }

    try {
      setPublishing(true);
      setPublishError(null);
      const tags = publishForm.tags
        .split(',')
        .map(t => t.trim())
        .filter(Boolean);
      const tools = publishForm.tools
        .split(',')
        .map(t => t.trim())
        .filter(Boolean);
      await api.publishAgent({
        name: publishForm.name.trim(),
        slug: publishForm.slug || generateSlug(publishForm.name),
        tagline: publishForm.tagline.trim(),
        description: publishForm.description.trim(),
        category: publishForm.category,
        pricing: publishForm.pricing,
        price_usd: publishForm.pricing === 'paid' ? publishForm.price_usd : undefined,
        tags,
        agent_config: {
          model: publishForm.model || 'gpt-4',
          temperature: publishForm.temperature,
          system_prompt: publishForm.system_prompt,
          tools,
        },
        version: publishForm.version || '1.0.0',
      });
      setShowPublishModal(false);
      setPublishForm({ ...defaultPublishForm });
      await loadAgents();
      alert('Agent published successfully!');
    } catch (err) {
      const raw = err instanceof Error ? err.message : 'Failed to publish agent.';
      if (raw.includes('duplicate key') && raw.includes('slug')) {
        const suffix = Math.random().toString(36).substring(2, 6);
        const newSlug = `${publishForm.slug}-${suffix}`;
        setPublishForm(prev => ({ ...prev, slug: newSlug }));
        setPublishError(`Slug "${publishForm.slug}" is already taken. We've suggested "${newSlug}" — edit it or re-submit.`);
      } else if (raw.includes('duplicate key')) {
        setPublishError('An agent with these details already exists. Please change the name or slug.');
      } else {
        setPublishError(raw);
      }
    } finally {
      setPublishing(false);
    }
  };

  const renderStars = (rating: number) => {
    return (
      <div className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((star) => (
          <Star
            key={star}
            size={14}
            fill={star <= Math.round(rating) ? 'var(--yellow)' : 'none'}
            style={{ color: star <= Math.round(rating) ? 'var(--yellow)' : 'var(--text-tertiary)' }}
          />
        ))}
      </div>
    );
  };

  // Loading state
  if (loading && agents.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Store className="h-12 w-12 mx-auto mb-3 animate-pulse" style={{ color: 'var(--accent)' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Loading marketplace...</p>
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
            <Store className="h-7 w-7" style={{ color: 'var(--accent)' }} />
            Marketplace
          </h1>
          <p className="mt-1" style={{ color: 'var(--text-secondary)' }}>
            Discover pre-built agents and workflow templates
          </p>
        </div>
        <button
          onClick={() => { setPublishError(null); setPublishType(typeFilter === 'workflow_template' ? 'workflow_template' : 'agent'); if (typeFilter === 'workflow_template' && userWorkflows.length === 0) loadUserWorkflows(); setShowPublishModal(true); }}
          className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors"
          style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
        >
          <Plus className="h-4 w-4" />
          Publish
        </button>
      </div>

      {/* Type Tabs */}
      <div className="flex gap-1 p-1 rounded-lg" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
        {([
          { key: 'all', label: 'All', icon: Store },
          { key: 'agent', label: 'Agents', icon: Bot },
          { key: 'workflow_template', label: 'Workflow Templates', icon: Workflow },
        ] as const).map(({ key, label, icon: TabIcon }) => {
          const isActive = typeFilter === key;
          return (
            <button
              key={key}
              onClick={() => setTypeFilter(key)}
              className="flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-md transition-colors flex-1 justify-center"
              style={{
                background: isActive ? 'var(--accent)' : 'transparent',
                color: isActive ? 'var(--bg-primary)' : 'var(--text-secondary)',
              }}
            >
              <TabIcon size={15} />
              {label}
            </button>
          );
        })}
      </div>

      {/* Featured Agents */}
      {featuredAgents.length > 0 && (
        <div
          className="rounded-lg p-6"
          style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderLeft: '3px solid var(--accent)' }}
        >
          <h2 className="text-lg font-semibold flex items-center gap-2 mb-4" style={{ color: 'var(--text-primary)' }}>
            <TrendingUp className="h-5 w-5" style={{ color: 'var(--accent)' }} />
            Featured Agents
            <span className="text-xs font-normal px-2 py-0.5 rounded-full" style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}>Popular</span>
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {featuredAgents.map((agent) => {
              const meta = getCategoryMeta(agent.category);
              const IconComp = meta.icon;
              return (
                <div
                  key={agent.id}
                  className="rounded-lg p-4"
                  style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', borderTop: '2px solid var(--accent)' }}
                >
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex items-center gap-2">
                      <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{agent.name}</h3>
                      {agent.verified && <Shield size={14} style={{ color: 'var(--accent)' }} />}
                    </div>
                  </div>
                  <p className="text-sm mb-3 line-clamp-2" style={{ color: 'var(--text-secondary)' }}>
                    {agent.tagline}
                  </p>
                  <div className="flex gap-2 mb-3 flex-wrap">
                    <span
                      className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-md"
                      style={{ background: `color-mix(in srgb, ${meta.color} 15%, transparent)`, color: meta.color }}
                    >
                      <IconComp size={12} /> {meta.label}
                    </span>
                    <span
                      className="text-xs font-medium px-2 py-0.5 rounded-md"
                      style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}
                    >
                      {agent.pricing}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-xs" style={{ color: 'var(--text-tertiary)' }}>
                    <div className="flex items-center gap-1">
                      {renderStars(agent.avg_rating)}
                      <span className="ml-1">({agent.rating_count})</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Download size={12} />
                      <span>{agent.install_count.toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Search and Category Filters */}
      <div className="flex gap-3 items-center flex-wrap">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4" style={{ color: 'var(--text-tertiary)' }} />
          <input
            type="text"
            placeholder={typeFilter === 'workflow_template' ? 'Search templates...' : typeFilter === 'agent' ? 'Search agents...' : 'Search marketplace...'}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 px-3 py-2 rounded-lg text-sm"
            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
          />
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
                {category === 'all' ? 'All' : (meta?.label || category.replace('_', ' '))}
              </button>
            );
          })}
        </div>
      </div>

      {/* Error State */}
      {error && (
        <div className="rounded-lg p-4" style={{ background: 'color-mix(in srgb, var(--error) 10%, var(--bg-secondary))', border: '1px solid var(--error)' }}>
          <p className="text-sm" style={{ color: 'var(--error)' }}>{error}</p>
        </div>
      )}

      {/* Agents Grid */}
      {!loading && agents.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {agents.map((agent) => {
            const meta = getCategoryMeta(agent.category);
            const IconComp = meta.icon;
            const isInstalled = installedAgents.has(agent.id);
            const isTemplate = agent.item_type === 'workflow_template';
            const nodeCount = isTemplate && agent.agent_config ? (agent.agent_config as Record<string, unknown>).node_count as number || 0 : 0;
            const triggerType = isTemplate && agent.agent_config ? (agent.agent_config as Record<string, unknown>).trigger_type as string || 'manual' : '';

            return (
              <div
                key={agent.id}
                className="rounded-lg overflow-hidden"
                style={{
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-primary)',
                  borderLeft: isInstalled ? '3px solid var(--green)' : isTemplate ? '3px solid var(--cyan)' : undefined,
                }}
              >
                <div className="p-5">
                  <div className="flex justify-between items-start mb-3">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
                        style={{ background: isTemplate ? 'color-mix(in srgb, var(--cyan) 15%, transparent)' : `color-mix(in srgb, ${meta.color} 15%, transparent)` }}
                      >
                        {isTemplate
                          ? <Workflow size={20} style={{ color: 'var(--cyan)' }} />
                          : <IconComp size={20} style={{ color: meta.color }} />
                        }
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <h3 className="text-base font-semibold" style={{ color: 'var(--text-primary)' }}>{agent.name}</h3>
                          {agent.verified && <Shield size={14} style={{ color: 'var(--accent)' }} />}
                        </div>
                        <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>
                          by {agent.author} &bull; v{agent.version}
                        </p>
                      </div>
                    </div>
                  </div>

                  <p className="text-sm mb-3 line-clamp-3" style={{ color: 'var(--text-secondary)', lineHeight: '1.5' }}>
                    {agent.description}
                  </p>

                  <div className="flex gap-2 mb-3 flex-wrap">
                    {isTemplate && (
                      <span
                        className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-md"
                        style={{ background: 'color-mix(in srgb, var(--cyan) 15%, transparent)', color: 'var(--cyan)' }}
                      >
                        <Workflow size={11} /> Template
                      </span>
                    )}
                    <span
                      className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-md"
                      style={{ background: `color-mix(in srgb, ${meta.color} 15%, transparent)`, color: meta.color }}
                    >
                      <IconComp size={11} /> {meta.label}
                    </span>
                    {isTemplate && nodeCount > 0 && (
                      <span
                        className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-md"
                        style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}
                      >
                        <GitBranch size={11} /> {nodeCount} nodes
                      </span>
                    )}
                    {isTemplate && triggerType && (
                      <span
                        className="text-xs font-medium px-2 py-0.5 rounded-md"
                        style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}
                      >
                        {triggerType}
                      </span>
                    )}
                    {!isTemplate && (
                      <span
                        className="text-xs font-medium px-2 py-0.5 rounded-md"
                        style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}
                      >
                        {agent.pricing}
                      </span>
                    )}
                  </div>

                  <div className="flex justify-between items-center text-xs" style={{ color: 'var(--text-tertiary)' }}>
                    <div className="flex items-center gap-1.5">
                      {renderStars(agent.avg_rating)}
                      <span>{agent.avg_rating.toFixed(1)} ({agent.rating_count})</span>
                    </div>
                    <div className="flex items-center gap-1">
                      <Download size={12} />
                      <span>{agent.install_count.toLocaleString()}</span>
                    </div>
                  </div>
                </div>

                {/* Installed badge (agents only) */}
                {isInstalled && !isTemplate && (
                  <div
                    className="flex items-center gap-2 px-5 py-2"
                    style={{ background: 'color-mix(in srgb, var(--green) 10%, transparent)', borderTop: '1px solid var(--border-primary)' }}
                  >
                    <CheckCircle size={14} style={{ color: 'var(--green)' }} />
                    <span className="text-xs font-medium" style={{ color: 'var(--green)' }}>Installed</span>
                  </div>
                )}

                {/* Action bar */}
                <div
                  className="flex gap-2 px-5 py-3"
                  style={{ borderTop: '1px solid var(--border-primary)', background: 'var(--bg-tertiary)' }}
                >
                  {isTemplate ? (
                    <>
                      <button
                        className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors"
                        style={{ background: 'var(--cyan)', color: 'var(--bg-primary)' }}
                        onClick={() => handleUseTemplate(agent.id)}
                        disabled={usingTemplate.has(agent.id)}
                      >
                        <Workflow size={14} />
                        {usingTemplate.has(agent.id) ? 'Creating...' : 'Use Template'}
                        <ArrowRight size={14} style={{ opacity: 0.7 }} />
                      </button>
                      <button
                        className="flex items-center justify-center p-1.5 rounded-lg transition-colors"
                        style={{ background: 'color-mix(in srgb, var(--error) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--error) 25%, transparent)' }}
                        onClick={() => handleDeleteAgent(agent.id, agent.name)}
                        disabled={deletingAgents.has(agent.id)}
                        title="Delete this template from marketplace"
                      >
                        <Trash2 size={14} style={{ color: 'var(--error)' }} />
                      </button>
                    </>
                  ) : isInstalled ? (
                    <>
                      <button
                        className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors"
                        style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)' }}
                        onClick={() => handleUseAgent(agent.name)}
                        title="View and manage this agent"
                      >
                        <Play size={14} /> Use
                      </button>
                      <button
                        className="flex items-center justify-center p-1.5 rounded-lg transition-colors"
                        style={{ background: 'color-mix(in srgb, var(--error) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--error) 25%, transparent)' }}
                        onClick={() => handleUninstall(agent.id, agent.name)}
                        disabled={uninstallingAgents.has(agent.id)}
                        title="Uninstall this agent"
                      >
                        <Trash2 size={14} style={{ color: 'var(--error)' }} />
                      </button>
                    </>
                  ) : (
                    <>
                      <button
                        className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors"
                        style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
                        onClick={() => handleInstall(agent.id)}
                        disabled={installingAgents.has(agent.id)}
                      >
                        <Download size={14} />
                        {installingAgents.has(agent.id) ? 'Installing...' : 'Install'}
                        <ArrowRight size={14} style={{ opacity: 0.7 }} />
                      </button>
                      <button
                        className="flex items-center justify-center p-1.5 rounded-lg transition-colors"
                        style={{ background: 'color-mix(in srgb, var(--error) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--error) 25%, transparent)' }}
                        onClick={() => handleDeleteAgent(agent.id, agent.name)}
                        disabled={deletingAgents.has(agent.id)}
                        title="Delete this agent from marketplace"
                      >
                        <Trash2 size={14} style={{ color: 'var(--error)' }} />
                      </button>
                    </>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Empty State */}
      {!loading && agents.length === 0 && !error && (
        <div className="rounded-lg p-6" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
          <div className="text-center py-12">
            <Store className="h-12 w-12 mx-auto mb-3" style={{ color: 'var(--text-tertiary)' }} />
            <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>
              {typeFilter === 'workflow_template' ? 'No templates found' : typeFilter === 'agent' ? 'No agents found' : 'No items found'}
            </h3>
            <p className="text-sm mb-5 max-w-sm mx-auto" style={{ color: 'var(--text-secondary)' }}>
              Try adjusting your search or filters to discover available {typeFilter === 'workflow_template' ? 'templates' : typeFilter === 'agent' ? 'agents' : 'items'}.
            </p>
            <button
              className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg mx-auto"
              style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
              onClick={() => { setSearchQuery(''); setCategoryFilter('all'); setTypeFilter('all'); }}
            >
              Clear Filters
            </button>
          </div>
        </div>
      )}

      {/* Publish Agent Modal */}
      {showPublishModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)' }}
          onClick={() => setShowPublishModal(false)}
        >
          <div
            className="rounded-2xl w-full max-w-xl max-h-[85vh] flex flex-col"
            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}
            onClick={e => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex justify-between items-center px-6 py-4" style={{ borderBottom: '1px solid var(--border-primary)' }}>
              <h2 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <Plus className="h-5 w-5" style={{ color: 'var(--accent)' }} />
                Publish to Marketplace
              </h2>
              <button
                onClick={() => setShowPublishModal(false)}
                className="p-1"
                style={{ color: 'var(--text-tertiary)' }}
              >
                <X size={20} />
              </button>
            </div>

            {/* Modal Body */}
            <div className="px-6 py-4 overflow-y-auto flex flex-col gap-5">
              {publishError && (
                <div className="p-3 rounded-lg text-sm" style={{ background: 'color-mix(in srgb, var(--error) 15%, transparent)', border: '1px solid var(--error)', color: 'var(--error)' }}>
                  {publishError}
                </div>
              )}

              {/* Type Selector */}
              <div>
                <label className="block text-sm font-semibold mb-2" style={{ color: 'var(--text-secondary)' }}>What are you publishing?</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => { setPublishType('agent'); setPublishError(null); }}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors"
                    style={{
                      background: publishType === 'agent' ? 'var(--accent)' : 'var(--bg-secondary)',
                      color: publishType === 'agent' ? 'var(--bg-primary)' : 'var(--text-secondary)',
                      border: publishType === 'agent' ? '1px solid var(--accent)' : '1px solid var(--border-primary)',
                    }}
                  >
                    <Bot size={16} /> Agent
                  </button>
                  <button
                    onClick={() => { setPublishType('workflow_template'); setPublishError(null); if (userWorkflows.length === 0) loadUserWorkflows(); }}
                    className="flex-1 flex items-center justify-center gap-2 px-3 py-2.5 text-sm font-medium rounded-lg transition-colors"
                    style={{
                      background: publishType === 'workflow_template' ? 'var(--cyan)' : 'var(--bg-secondary)',
                      color: publishType === 'workflow_template' ? 'var(--bg-primary)' : 'var(--text-secondary)',
                      border: publishType === 'workflow_template' ? '1px solid var(--cyan)' : '1px solid var(--border-primary)',
                    }}
                  >
                    <Workflow size={16} /> Workflow Template
                  </button>
                </div>
              </div>

              {/* Workflow Picker (only for workflow templates) */}
              {publishType === 'workflow_template' && (
                <div>
                  <h3 className="text-sm font-semibold flex items-center gap-2 mb-3" style={{ color: 'var(--text-secondary)' }}>
                    <Workflow size={14} /> Select Workflow
                  </h3>
                  {loadingWorkflows ? (
                    <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>Loading workflows...</p>
                  ) : userWorkflows.length === 0 ? (
                    <p className="text-sm" style={{ color: 'var(--text-tertiary)' }}>No workflows found. Create a workflow first.</p>
                  ) : (
                    <select
                      value={selectedWorkflowId}
                      onChange={e => setSelectedWorkflowId(e.target.value)}
                      className="w-full px-3 py-2 rounded-lg text-sm"
                      style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                    >
                      <option value="">Choose a workflow...</option>
                      {userWorkflows.map(w => (
                        <option key={w.id} value={w.id}>{w.name}</option>
                      ))}
                    </select>
                  )}
                </div>
              )}

              {/* Basic Info */}
              <div>
                <h3 className="text-sm font-semibold flex items-center gap-2 mb-3" style={{ color: 'var(--text-secondary)' }}>
                  <FileText size={14} /> Basic Info
                </h3>
                <div className="flex flex-col gap-3">
                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Name *</label>
                    <input
                      type="text"
                      value={publishForm.name}
                      onChange={e => updatePublishField('name', e.target.value)}
                      placeholder={publishType === 'workflow_template' ? 'My Workflow Template' : 'My Awesome Agent'}
                      className="w-full px-3 py-2 rounded-lg text-sm"
                      style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                    />
                  </div>
                  {publishType === 'agent' && (
                    <div>
                      <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Slug</label>
                      <input
                        type="text"
                        value={publishForm.slug}
                        onChange={e => updatePublishField('slug', e.target.value)}
                        placeholder="my-awesome-agent"
                        className="w-full px-3 py-2 rounded-lg text-sm"
                        style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                      />
                    </div>
                  )}
                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Tagline *</label>
                    <input
                      type="text"
                      value={publishForm.tagline}
                      onChange={e => updatePublishField('tagline', e.target.value)}
                      placeholder={publishType === 'workflow_template' ? 'A short description of this template' : 'A short description of what this agent does'}
                      className="w-full px-3 py-2 rounded-lg text-sm"
                      style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Description *</label>
                    <textarea
                      value={publishForm.description}
                      onChange={e => updatePublishField('description', e.target.value)}
                      placeholder={publishType === 'workflow_template' ? 'Describe what this workflow template does and when to use it...' : "Detailed description of the agent's capabilities..."}
                      rows={3}
                      className="w-full px-3 py-2 rounded-lg text-sm"
                      style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)', resize: 'vertical' }}
                    />
                  </div>
                </div>
              </div>

              {/* Classification */}
              <div>
                <h3 className="text-sm font-semibold flex items-center gap-2 mb-3" style={{ color: 'var(--text-secondary)' }}>
                  <BarChart3 size={14} /> Classification
                </h3>
                <div className="flex flex-col gap-3">
                  <div className={publishType === 'agent' ? 'grid grid-cols-2 gap-3' : ''}>
                    <div>
                      <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Category</label>
                      <select
                        value={publishForm.category}
                        onChange={e => updatePublishField('category', e.target.value)}
                        className="w-full px-3 py-2 rounded-lg text-sm"
                        style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                      >
                        {allCategories.map(cat => (
                          <option key={cat} value={cat}>{cat.replace(/_/g, ' ')}</option>
                        ))}
                      </select>
                    </div>
                    {publishType === 'agent' && (
                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Pricing</label>
                        <select
                          value={publishForm.pricing}
                          onChange={e => updatePublishField('pricing', e.target.value)}
                          className="w-full px-3 py-2 rounded-lg text-sm"
                          style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                        >
                          <option value="free">Free</option>
                          <option value="freemium">Freemium</option>
                          <option value="paid">Paid</option>
                        </select>
                      </div>
                    )}
                  </div>
                  {publishType === 'agent' && publishForm.pricing === 'paid' && (
                    <div>
                      <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Price (USD)</label>
                      <input
                        type="number"
                        min="0"
                        step="0.01"
                        value={publishForm.price_usd}
                        onChange={e => updatePublishField('price_usd', parseFloat(e.target.value) || 0)}
                        className="w-full px-3 py-2 rounded-lg text-sm"
                        style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                      />
                    </div>
                  )}
                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Tags (comma-separated)</label>
                    <input
                      type="text"
                      value={publishForm.tags}
                      onChange={e => updatePublishField('tags', e.target.value)}
                      placeholder={publishType === 'workflow_template' ? 'onboarding, automation, ops' : 'chatbot, support, automation'}
                      className="w-full px-3 py-2 rounded-lg text-sm"
                      style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                    />
                  </div>
                </div>
              </div>

              {/* Agent Config (only for agents) */}
              {publishType === 'agent' && (
                <div>
                  <h3 className="text-sm font-semibold flex items-center gap-2 mb-3" style={{ color: 'var(--text-secondary)' }}>
                    <Settings size={14} /> Agent Configuration
                  </h3>
                  <div className="flex flex-col gap-3">
                    <div className="grid grid-cols-2 gap-3">
                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Model</label>
                        <input
                          type="text"
                          value={publishForm.model}
                          onChange={e => updatePublishField('model', e.target.value)}
                          placeholder="gpt-4"
                          className="w-full px-3 py-2 rounded-lg text-sm"
                          style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Temperature (0-1)</label>
                        <input
                          type="number"
                          min="0"
                          max="1"
                          step="0.1"
                          value={publishForm.temperature}
                          onChange={e => updatePublishField('temperature', parseFloat(e.target.value) || 0)}
                          className="w-full px-3 py-2 rounded-lg text-sm"
                          style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                        />
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>System Prompt</label>
                      <textarea
                        value={publishForm.system_prompt}
                        onChange={e => updatePublishField('system_prompt', e.target.value)}
                        placeholder="You are a helpful assistant that..."
                        rows={5}
                        className="w-full px-3 py-2 rounded-lg text-sm"
                        style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)', resize: 'vertical' }}
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Tools (comma-separated)</label>
                      <input
                        type="text"
                        value={publishForm.tools}
                        onChange={e => updatePublishField('tools', e.target.value)}
                        placeholder="web_search, calculator, code_interpreter"
                        className="w-full px-3 py-2 rounded-lg text-sm"
                        style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                      />
                    </div>
                  </div>
                </div>
              )}

              {/* Metadata (only for agents) */}
              {publishType === 'agent' && (
                <div>
                  <h3 className="text-sm font-semibold flex items-center gap-2 mb-3" style={{ color: 'var(--text-secondary)' }}>
                    <Code2 size={14} /> Metadata
                  </h3>
                  <div>
                    <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Version</label>
                    <input
                      type="text"
                      value={publishForm.version}
                      onChange={e => updatePublishField('version', e.target.value)}
                      placeholder="1.0.0"
                      className="w-48 px-3 py-2 rounded-lg text-sm"
                      style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end gap-2 px-6 py-4" style={{ borderTop: '1px solid var(--border-primary)' }}>
              <button
                onClick={() => setShowPublishModal(false)}
                disabled={publishing}
                className="px-4 py-2 text-sm font-medium rounded-lg"
                style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)' }}
              >
                Cancel
              </button>
              <button
                onClick={handlePublish}
                disabled={publishing}
                className="flex items-center gap-1 px-4 py-2 text-sm font-medium rounded-lg disabled:opacity-50"
                style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
              >
                {publishing ? 'Publishing...' : publishType === 'workflow_template' ? 'Publish Template' : 'Publish Agent'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default MarketplacePage;
