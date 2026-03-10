import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { AgentStatusGrid } from '@/components/AgentStatusGrid'
import { useNavigate } from 'react-router-dom'
import { Bot, Package, Clock, Trash2, Play, Store, AlertCircle, Plus, X, Upload } from 'lucide-react'
import { format } from 'date-fns'

interface InstalledAgent {
  installation_id: number
  agent_id: number
  name: string
  slug: string
  tagline: string
  description: string
  category: string
  author: string
  version: string
  agent_config: Record<string, unknown>
  status: string
  installed_at: string | null
  last_used_at: string | null
  usage_count: number
  config_overrides: Record<string, unknown>
}

const defaultAgentForm = {
  name: '',
  description: '',
  model: 'gpt-4',
  system_prompt: '',
  temperature: 0.7,
  tools: '',
  category: 'general',
}

const agentCategories = [
  'customer_service', 'sales_automation', 'engineering', 'marketing',
  'analytics', 'productivity', 'data_processing', 'hr', 'finance',
  'legal', 'security', 'devops', 'general',
]

export function AgentsPage() {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [agentForm, setAgentForm] = useState({ ...defaultAgentForm })
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)

  // Publish to marketplace state
  const [publishAgent, setPublishAgent] = useState<InstalledAgent | null>(null)
  const [publishForm, setPublishForm] = useState({ tagline: '', category: 'general', tags: '' })
  const [publishing, setPublishing] = useState(false)
  const [publishError, setPublishError] = useState<string | null>(null)

  const { data: agents, isLoading: loadingWorkers, error: workersError } = useQuery({
    queryKey: ['agents'],
    queryFn: () => api.getAgents(),
    refetchInterval: 5000,
  })

  const { data: installedData, isLoading: loadingInstalled } = useQuery({
    queryKey: ['installed-agents'],
    queryFn: () => api.getInstalledAgentsWithDetails(),
    refetchInterval: 10000,
  })

  const installedAgents = installedData?.installed_agents || []

  const handleUninstall = async (installationId: number, agentName: string) => {
    if (!window.confirm(`Are you sure you want to uninstall "${agentName}"?`)) {
      return
    }
    try {
      await api.uninstallAgent(installationId)
      window.location.reload()
    } catch (err) {
      alert(`Failed to uninstall: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleUseInWorkflow = (agent: InstalledAgent) => {
    const template = {
      id: `marketplace-agent-${agent.agent_id}`,
      name: `${agent.name} Workflow`,
      description: agent.description || agent.tagline,
      category: 'agent' as const,
      tags: [agent.category, agent.author],
      icon: '🤖',
      color: '#6366f1',
      nodes: [
        {
          id: `worker-${Date.now()}`,
          type: 'worker',
          position: { x: 250, y: 200 },
          data: {
            label: agent.name,
            type: 'worker',
            llmModel: agent.agent_config?.model || 'gpt-4',
            prompt: agent.agent_config?.system_prompt || '',
            temperature: agent.agent_config?.temperature || 0.7,
            capabilities: agent.agent_config?.tools || ['processing'],
            status: 'idle',
            marketplaceAgentId: agent.agent_id,
            marketplaceAgentSlug: agent.slug,
          },
        },
      ],
      edges: [],
    }

    navigate('/workflows/builder', { state: { template } })
  }

  const handleCreateAgent = async () => {
    if (!agentForm.name.trim() || !agentForm.system_prompt.trim()) {
      setCreateError('Name and system prompt are required.')
      return
    }
    try {
      setCreating(true)
      setCreateError(null)
      const tools = agentForm.tools.split(',').map(t => t.trim()).filter(Boolean)
      await api.publishAgent({
        name: agentForm.name.trim(),
        slug: agentForm.name.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''),
        tagline: agentForm.description.trim() || agentForm.name.trim(),
        description: agentForm.description.trim() || agentForm.name.trim(),
        category: agentForm.category,
        pricing: 'free',
        tags: [agentForm.category],
        agent_config: {
          model: agentForm.model || 'gpt-4',
          temperature: agentForm.temperature,
          system_prompt: agentForm.system_prompt,
          tools,
        },
        version: '1.0.0',
      })
      setShowCreateModal(false)
      setAgentForm({ ...defaultAgentForm })
      alert('Agent created and published! You can find it in the Marketplace.')
    } catch (err) {
      setCreateError(err instanceof Error ? err.message : 'Failed to create agent.')
    } finally {
      setCreating(false)
    }
  }

  const handlePublishToMarketplace = async () => {
    if (!publishAgent) return
    if (!publishForm.tagline.trim()) {
      setPublishError('Tagline is required.')
      return
    }
    try {
      setPublishing(true)
      setPublishError(null)
      const tags = publishForm.tags.split(',').map(t => t.trim()).filter(Boolean)
      await api.publishAgent({
        name: publishAgent.name,
        slug: publishAgent.slug || publishAgent.name.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
        tagline: publishForm.tagline.trim(),
        description: publishAgent.description || publishForm.tagline.trim(),
        category: publishForm.category,
        pricing: 'free',
        tags,
        agent_config: publishAgent.agent_config || {},
        version: publishAgent.version || '1.0.0',
      })
      setPublishAgent(null)
      setPublishForm({ tagline: '', category: 'general', tags: '' })
      alert(`"${publishAgent.name}" published to Marketplace!`)
    } catch (err) {
      const msg = err instanceof Error ? err.message : 'Failed to publish.'
      if (msg.includes('duplicate key') || msg.includes('already')) {
        setPublishError('This agent is already published in the Marketplace.')
      } else {
        setPublishError(msg)
      }
    } finally {
      setPublishing(false)
    }
  }

  const isLoading = loadingWorkers || loadingInstalled

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Bot className="h-12 w-12 mx-auto mb-3 animate-pulse" style={{ color: 'var(--accent)' }} />
          <p style={{ color: 'var(--text-secondary)' }}>Loading agents...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
            <Bot className="h-7 w-7" style={{ color: 'var(--accent)' }} />
            Agents
          </h1>
          <p className="mt-1" style={{ color: 'var(--text-secondary)' }}>
            Create, install, and monitor your AI agents
          </p>
        </div>
        <div className="flex gap-2">
          <button
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors"
            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)' }}
            onClick={() => navigate('/marketplace?type=agent')}
          >
            <Store size={16} /> Browse Marketplace
          </button>
          <button
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors"
            style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
            onClick={() => { setCreateError(null); setShowCreateModal(true) }}
          >
            <Plus size={16} /> Create Agent
          </button>
        </div>
      </div>

      {/* Installed Marketplace Agents Section */}
      <div className="rounded-lg p-6" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
        <div className="flex items-center gap-2 mb-4">
          <Package className="h-5 w-5" style={{ color: 'var(--cyan)' }} />
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Installed Agents</h2>
          <span
            className="text-xs font-normal px-2 py-0.5 rounded-full"
            style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}
          >
            {installedAgents.length}
          </span>
        </div>

        {installedAgents.length === 0 ? (
          <div className="text-center py-12">
            <Package className="h-12 w-12 mx-auto mb-3" style={{ color: 'var(--text-tertiary)' }} />
            <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>No agents installed</h3>
            <p className="text-sm mb-5" style={{ color: 'var(--text-secondary)' }}>
              Visit the Marketplace to discover and install pre-built agents
            </p>
            <button
              onClick={() => navigate('/marketplace')}
              className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg mx-auto"
              style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
            >
              <Store size={14} /> Browse Marketplace
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {installedAgents.map((agent: InstalledAgent) => (
              <div
                key={agent.installation_id}
                className="rounded-lg p-4"
                style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}
              >
                <div className="flex items-start justify-between mb-3">
                  <div>
                    <h3 className="font-semibold" style={{ color: 'var(--text-primary)' }}>{agent.name}</h3>
                    <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>v{agent.version} &bull; by {agent.author}</p>
                  </div>
                  <span
                    className="px-2 py-0.5 text-xs font-medium rounded-md"
                    style={{ background: 'color-mix(in srgb, var(--green) 15%, transparent)', color: 'var(--green)' }}
                  >
                    Installed
                  </span>
                </div>

                <p className="text-sm mb-3 line-clamp-2" style={{ color: 'var(--text-secondary)' }}>{agent.tagline}</p>

                <div className="flex flex-wrap gap-2 mb-3">
                  <span
                    className="px-2 py-0.5 text-xs font-medium rounded-md"
                    style={{ background: 'color-mix(in srgb, var(--cyan) 15%, transparent)', color: 'var(--cyan)' }}
                  >
                    {agent.category.replace('_', ' ')}
                  </span>
                  {agent.agent_config?.model && (
                    <span
                      className="px-2 py-0.5 text-xs font-medium rounded-md"
                      style={{ background: 'color-mix(in srgb, var(--purple) 15%, transparent)', color: 'var(--purple)' }}
                    >
                      {String(agent.agent_config.model)}
                    </span>
                  )}
                </div>

                <div className="space-y-1 text-sm mb-3" style={{ color: 'var(--text-tertiary)' }}>
                  <div className="flex items-center gap-2">
                    <Clock className="h-3 w-3" />
                    <span>Installed: {agent.installed_at ? format(new Date(agent.installed_at), 'MMM d, yyyy') : 'Unknown'}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Play className="h-3 w-3" />
                    <span>Used {agent.usage_count} times</span>
                  </div>
                </div>

                <div className="flex gap-2 pt-3" style={{ borderTop: '1px solid var(--border-primary)' }}>
                  <button
                    onClick={() => handleUseInWorkflow(agent)}
                    className="flex-1 flex items-center justify-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg transition-colors"
                    style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
                  >
                    <Play className="h-4 w-4" />
                    Use in Workflow
                  </button>
                  <button
                    onClick={() => {
                      setPublishError(null)
                      setPublishForm({ tagline: agent.tagline || '', category: agent.category || 'general', tags: '' })
                      setPublishAgent(agent)
                    }}
                    className="flex items-center justify-center p-1.5 rounded-lg transition-colors"
                    style={{ background: 'color-mix(in srgb, var(--cyan) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--cyan) 25%, transparent)' }}
                    title="Publish to Marketplace"
                  >
                    <Upload className="h-4 w-4" style={{ color: 'var(--cyan)' }} />
                  </button>
                  <button
                    onClick={() => handleUninstall(agent.installation_id, agent.name)}
                    className="flex items-center justify-center p-1.5 rounded-lg transition-colors"
                    style={{ background: 'color-mix(in srgb, var(--error) 10%, transparent)', border: '1px solid color-mix(in srgb, var(--error) 25%, transparent)' }}
                    title="Uninstall"
                  >
                    <Trash2 className="h-4 w-4" style={{ color: 'var(--error)' }} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Runtime Workers Section */}
      <div className="rounded-lg p-6" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
        <div className="flex items-center gap-2 mb-4">
          <Bot className="h-5 w-5" style={{ color: 'var(--green)' }} />
          <h2 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Runtime Workers</h2>
          <span
            className="text-xs font-normal px-2 py-0.5 rounded-full"
            style={{ background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }}
          >
            {agents?.length || 0}
          </span>
        </div>

        {workersError ? (
          <div className="rounded-lg p-4" style={{ background: 'color-mix(in srgb, var(--error) 10%, var(--bg-primary))', border: '1px solid var(--error)' }}>
            <div className="flex items-center gap-3">
              <AlertCircle className="h-5 w-5 flex-shrink-0" style={{ color: 'var(--error)' }} />
              <div>
                <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Error Loading Workers</h3>
                <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
                  {workersError instanceof Error ? workersError.message : 'Failed to load workers'}
                </p>
              </div>
            </div>
          </div>
        ) : (
          <AgentStatusGrid agents={agents || []} />
        )}
      </div>

      {/* Create Agent Modal */}
      {showCreateModal && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)' }}
          onClick={() => setShowCreateModal(false)}
        >
          <div
            className="rounded-2xl w-full max-w-lg max-h-[85vh] flex flex-col"
            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-between items-center px-6 py-4" style={{ borderBottom: '1px solid var(--border-primary)' }}>
              <h2 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <Bot className="h-5 w-5" style={{ color: 'var(--accent)' }} />
                Create Agent
              </h2>
              <button onClick={() => setShowCreateModal(false)} className="p-1" style={{ color: 'var(--text-tertiary)' }}>
                <X size={20} />
              </button>
            </div>
            <div className="px-6 py-4 overflow-y-auto flex flex-col gap-4">
              {createError && (
                <div className="p-3 rounded-lg text-sm" style={{ background: 'color-mix(in srgb, var(--error) 15%, transparent)', border: '1px solid var(--error)', color: 'var(--error)' }}>
                  {createError}
                </div>
              )}
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Name *</label>
                <input
                  type="text" value={agentForm.name}
                  onChange={e => setAgentForm(p => ({ ...p, name: e.target.value }))}
                  placeholder="My Support Agent"
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Description</label>
                <input
                  type="text" value={agentForm.description}
                  onChange={e => setAgentForm(p => ({ ...p, description: e.target.value }))}
                  placeholder="A short description of what this agent does"
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Model</label>
                  <select
                    value={agentForm.model}
                    onChange={e => setAgentForm(p => ({ ...p, model: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg text-sm"
                    style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                  >
                    <option value="gpt-4">GPT-4</option>
                    <option value="gpt-4o">GPT-4o</option>
                    <option value="gpt-3.5-turbo">GPT-3.5 Turbo</option>
                    <option value="claude-sonnet-4-5-20250929">Claude Sonnet 4.5</option>
                    <option value="claude-haiku-4-5-20251001">Claude Haiku 4.5</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Category</label>
                  <select
                    value={agentForm.category}
                    onChange={e => setAgentForm(p => ({ ...p, category: e.target.value }))}
                    className="w-full px-3 py-2 rounded-lg text-sm"
                    style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                  >
                    {agentCategories.map(c => (
                      <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>System Prompt *</label>
                <textarea
                  value={agentForm.system_prompt}
                  onChange={e => setAgentForm(p => ({ ...p, system_prompt: e.target.value }))}
                  placeholder="You are a helpful assistant that..."
                  rows={5}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)', resize: 'vertical' }}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Tools (comma-separated)</label>
                <input
                  type="text" value={agentForm.tools}
                  onChange={e => setAgentForm(p => ({ ...p, tools: e.target.value }))}
                  placeholder="web_search, calculator, code_interpreter"
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 px-6 py-4" style={{ borderTop: '1px solid var(--border-primary)' }}>
              <button
                onClick={() => setShowCreateModal(false)} disabled={creating}
                className="px-4 py-2 text-sm font-medium rounded-lg"
                style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)' }}
              >Cancel</button>
              <button
                onClick={handleCreateAgent} disabled={creating}
                className="flex items-center gap-1 px-4 py-2 text-sm font-medium rounded-lg disabled:opacity-50"
                style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
              >{creating ? 'Creating...' : 'Create Agent'}</button>
            </div>
          </div>
        </div>
      )}

      {/* Publish to Marketplace Modal */}
      {publishAgent && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: 'rgba(0,0,0,0.5)', backdropFilter: 'blur(4px)' }}
          onClick={() => setPublishAgent(null)}
        >
          <div
            className="rounded-2xl w-full max-w-md max-h-[85vh] flex flex-col"
            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}
            onClick={e => e.stopPropagation()}
          >
            <div className="flex justify-between items-center px-6 py-4" style={{ borderBottom: '1px solid var(--border-primary)' }}>
              <h2 className="text-lg font-semibold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
                <Upload className="h-5 w-5" style={{ color: 'var(--cyan)' }} />
                Publish to Marketplace
              </h2>
              <button onClick={() => setPublishAgent(null)} className="p-1" style={{ color: 'var(--text-tertiary)' }}>
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
                <p className="font-semibold text-sm" style={{ color: 'var(--text-primary)' }}>{publishAgent.name}</p>
                <p className="text-xs" style={{ color: 'var(--text-tertiary)' }}>v{publishAgent.version} by {publishAgent.author}</p>
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
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Category</label>
                <select
                  value={publishForm.category}
                  onChange={e => setPublishForm(p => ({ ...p, category: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                >
                  {agentCategories.map(c => (
                    <option key={c} value={c}>{c.replace(/_/g, ' ')}</option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--text-secondary)' }}>Tags (comma-separated)</label>
                <input
                  type="text" value={publishForm.tags}
                  onChange={e => setPublishForm(p => ({ ...p, tags: e.target.value }))}
                  placeholder="chatbot, support, automation"
                  className="w-full px-3 py-2 rounded-lg text-sm"
                  style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 px-6 py-4" style={{ borderTop: '1px solid var(--border-primary)' }}>
              <button
                onClick={() => setPublishAgent(null)} disabled={publishing}
                className="px-4 py-2 text-sm font-medium rounded-lg"
                style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)' }}
              >Cancel</button>
              <button
                onClick={handlePublishToMarketplace} disabled={publishing}
                className="flex items-center gap-1 px-4 py-2 text-sm font-medium rounded-lg disabled:opacity-50"
                style={{ background: 'var(--cyan)', color: 'var(--bg-primary)' }}
              >{publishing ? 'Publishing...' : 'Publish'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
