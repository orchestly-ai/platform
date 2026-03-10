/**
 * Prompt Registry Page - Centralized prompt management with versioning
 *
 * Features:
 * - List view with search/filter
 * - Prompt detail view with version history
 * - Prompt editor with variable detection
 * - Version comparison
 * - Testing panel for rendering prompts
 */

import { useState, useEffect } from 'react'
import {
  Search,
  Plus,
  FileText,
  GitBranch,
  Play,
  Clock,
  TrendingUp,
  Edit2,
  Trash2,
  ChevronRight,
  Code,
  MessageSquare,
  Layers,
  BarChart3,
  Beaker,
  Tag,
  Cpu,
  Calendar,
  AlertCircle,
} from 'lucide-react'
import api from '@/services/api'
import type {
  PromptTemplate,
  PromptVersion,
  PromptUsageStats,
  PromptCategory,
} from '@/types/prompt'
import {
  VersionsTab,
  TestingTab,
  AnalyticsTab,
  CreateTemplateModal,
  CreateVersionModal,
  EditTemplateModal,
} from '@/components/prompt/PromptComponents'

type CategoryMeta = {
  icon: React.ComponentType<{ size?: number; className?: string }>
  color: string
  label: string
}

const CATEGORY_META: Record<string, CategoryMeta> = {
  all: { icon: Layers, color: 'var(--accent)', label: 'All' },
  classification: { icon: Tag, color: 'var(--purple)', label: 'Classification' },
  generation: { icon: MessageSquare, color: 'var(--cyan)', label: 'Generation' },
  extraction: { icon: Code, color: 'var(--orange)', label: 'Extraction' },
  summarization: { icon: FileText, color: 'var(--green)', label: 'Summarization' },
  translation: { icon: ChevronRight, color: 'var(--pink)', label: 'Translation' },
  conversation: { icon: MessageSquare, color: 'var(--yellow)', label: 'Conversation' },
  code: { icon: Code, color: 'var(--orange)', label: 'Code' },
  analysis: { icon: BarChart3, color: 'var(--purple)', label: 'Analysis' },
  other: { icon: Layers, color: 'var(--accent)', label: 'Other' },
}

function getCategoryColor(category?: string): string {
  return CATEGORY_META[category || '']?.color || 'var(--accent)'
}

export function PromptRegistryPage() {
  const [view, setView] = useState<'list' | 'detail'>('list')
  const [selectedTemplate, setSelectedTemplate] = useState<PromptTemplate | null>(null)
  const [templates, setTemplates] = useState<PromptTemplate[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [categoryFilter, setCategoryFilter] = useState<string>('all')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)

  const categories: (PromptCategory | 'all')[] = [
    'all',
    'classification',
    'generation',
    'extraction',
    'summarization',
    'translation',
    'conversation',
    'code',
    'analysis',
    'other',
  ]

  useEffect(() => {
    loadTemplates()
  }, [categoryFilter])

  const loadTemplates = async () => {
    try {
      setLoading(true)
      const params: any = {}
      if (categoryFilter !== 'all') {
        params.category = categoryFilter
      }
      const data = await api.listPromptTemplates(params)
      setTemplates(data)
      setError(null)
    } catch (err: any) {
      setError(err.message || 'Failed to load prompt templates')
      console.error('Error loading templates:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSelectTemplate = (template: PromptTemplate) => {
    setSelectedTemplate(template)
    setView('detail')
  }

  const handleBack = () => {
    setView('list')
    setSelectedTemplate(null)
  }

  const handleDeleteTemplate = async (template: PromptTemplate) => {
    if (!confirm(`Are you sure you want to delete "${template.name}"? This will delete all versions and cannot be undone.`)) {
      return
    }

    try {
      await api.deletePromptTemplate(template.slug)
      loadTemplates()
      if (selectedTemplate?.id === template.id) {
        handleBack()
      }
    } catch (err: any) {
      alert(`Failed to delete template: ${err.message}`)
    }
  }

  const filteredTemplates = templates.filter((template) => {
    const matchesSearch =
      template.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
      template.slug.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesSearch
  })

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2" style={{ color: 'var(--text-primary)' }}>
            <FileText className="h-7 w-7" style={{ color: 'var(--accent)' }} />
            Prompt Registry
          </h1>
          <p className="mt-1" style={{ color: 'var(--text-secondary)' }}>
            Centralized prompt management with semantic versioning
          </p>
        </div>
        {view === 'list' && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg"
            style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
          >
            <Plus className="h-4 w-4" />
            New Template
          </button>
        )}
        {view === 'detail' && (
          <button
            onClick={handleBack}
            className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg"
            style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}
          >
            ← Back to List
          </button>
        )}
      </div>

      {view === 'list' ? (
        <PromptListView
          templates={filteredTemplates}
          loading={loading}
          error={error}
          searchQuery={searchQuery}
          setSearchQuery={setSearchQuery}
          categoryFilter={categoryFilter}
          setCategoryFilter={setCategoryFilter}
          categories={categories}
          onSelect={handleSelectTemplate}
        />
      ) : (
        selectedTemplate && (
          <PromptDetailView
            template={selectedTemplate}
            onUpdate={loadTemplates}
            onEdit={() => setShowEditModal(true)}
            onDelete={() => handleDeleteTemplate(selectedTemplate)}
          />
        )
      )}

      {showCreateModal && (
        <CreateTemplateModal
          onClose={() => setShowCreateModal(false)}
          onSuccess={() => {
            setShowCreateModal(false)
            loadTemplates()
          }}
          categories={categories.filter((c) => c !== 'all') as PromptCategory[]}
        />
      )}

      {showEditModal && selectedTemplate && (
        <EditTemplateModal
          template={selectedTemplate}
          onClose={() => setShowEditModal(false)}
          onSuccess={() => {
            setShowEditModal(false)
            loadTemplates()
            // Refresh selected template
            if (selectedTemplate) {
              api.getPromptTemplate(selectedTemplate.slug).then(setSelectedTemplate)
            }
          }}
          categories={categories.filter((c) => c !== 'all') as PromptCategory[]}
        />
      )}
    </div>
  )
}

// ============================================================================
// Prompt List View Component
// ============================================================================

interface PromptListViewProps {
  templates: PromptTemplate[]
  loading: boolean
  error: string | null
  searchQuery: string
  setSearchQuery: (query: string) => void
  categoryFilter: string
  setCategoryFilter: (category: string) => void
  categories: (PromptCategory | 'all')[]
  onSelect: (template: PromptTemplate) => void
}

function PromptListView({
  templates,
  loading,
  error,
  searchQuery,
  setSearchQuery,
  categoryFilter,
  setCategoryFilter,
  categories,
  onSelect,
}: PromptListViewProps) {
  return (
    <div className="space-y-4">
      {/* Search and Category Filter Pills */}
      <div className="rounded-lg p-4" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
        <div className="relative mb-3">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4" style={{ color: 'var(--text-tertiary)' }} />
          <input
            type="text"
            placeholder="Search prompts by name, description, or slug..."
            className="w-full px-3 py-2 pl-10 rounded-lg text-sm"
            style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-primary)' }}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
        <div className="flex flex-wrap gap-2">
          {categories.map((category) => {
            const meta = CATEGORY_META[category] || CATEGORY_META.other
            const IconComp = meta.icon
            const isActive = categoryFilter === category
            return (
              <button
                key={category}
                onClick={() => setCategoryFilter(category)}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                style={
                  isActive
                    ? { background: 'var(--accent)', color: 'var(--bg-primary)' }
                    : { background: 'var(--bg-primary)', border: '1px solid var(--border-primary)', color: 'var(--text-secondary)' }
                }
              >
                <IconComp size={12} />
                {meta.label}
              </button>
            )
          })}
        </div>
      </div>

      {/* Templates Grid */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <FileText className="h-12 w-12 mx-auto mb-3 animate-pulse" style={{ color: 'var(--accent)' }} />
            <p style={{ color: 'var(--text-secondary)' }}>Loading prompts...</p>
          </div>
        </div>
      ) : error ? (
        <div className="rounded-lg p-4" style={{ background: 'color-mix(in srgb, var(--error) 10%, var(--bg-primary))', border: '1px solid var(--error)' }}>
          <div className="flex items-center gap-3">
            <AlertCircle className="h-5 w-5 flex-shrink-0" style={{ color: 'var(--error)' }} />
            <div>
              <h3 className="text-sm font-semibold" style={{ color: 'var(--text-primary)' }}>Error Loading Prompts</h3>
              <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>{error}</p>
            </div>
          </div>
        </div>
      ) : templates.length === 0 ? (
        <div className="rounded-lg p-6" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
          <div className="text-center py-12">
            <FileText className="h-12 w-12 mx-auto mb-3" style={{ color: 'var(--text-tertiary)' }} />
            <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--text-primary)' }}>No prompts found</h3>
            <p className="text-sm mb-5" style={{ color: 'var(--text-secondary)' }}>
              {searchQuery || categoryFilter !== 'all'
                ? 'Try adjusting your filters'
                : 'Create your first prompt template to get started'}
            </p>
            {(searchQuery || categoryFilter !== 'all') && (
              <button
                onClick={() => { setSearchQuery(''); setCategoryFilter('all') }}
                className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg mx-auto"
                style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
              >
                Clear Filters
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((template) => {
            const catColor = getCategoryColor(template.category)
            return (
              <div
                key={template.id}
                className="rounded-lg p-4 cursor-pointer transition-all"
                style={{
                  background: 'var(--bg-secondary)',
                  border: '1px solid var(--border-primary)',
                  borderLeft: `3px solid ${catColor}`,
                }}
                onClick={() => onSelect(template)}
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold truncate" style={{ color: 'var(--text-primary)' }}>
                      {template.name}
                    </h3>
                    <p className="text-xs font-mono mt-1" style={{ color: 'var(--text-tertiary)' }}>{template.slug}</p>
                  </div>
                  <span
                    className="px-2 py-0.5 text-xs font-medium rounded-md ml-2 flex-shrink-0"
                    style={
                      template.is_active
                        ? { background: 'color-mix(in srgb, var(--green) 15%, transparent)', color: 'var(--green)' }
                        : { background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }
                    }
                  >
                    {template.is_active ? 'Active' : 'Inactive'}
                  </span>
                </div>

                {template.description && (
                  <p className="text-sm mb-3 line-clamp-2" style={{ color: 'var(--text-secondary)' }}>
                    {template.description}
                  </p>
                )}

                <div className="flex items-center justify-between pt-3" style={{ borderTop: '1px solid var(--border-primary)' }}>
                  <div className="flex items-center gap-2">
                    {template.category && (
                      <span
                        className="px-2 py-0.5 text-xs font-medium rounded-md"
                        style={{ background: `color-mix(in srgb, ${catColor} 15%, transparent)`, color: catColor }}
                      >
                        {template.category}
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-1 text-xs" style={{ color: 'var(--text-tertiary)' }}>
                    <Calendar className="w-3.5 h-3.5" />
                    {new Date(template.updated_at).toLocaleDateString()}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Prompt Detail View Component
// ============================================================================

interface PromptDetailViewProps {
  template: PromptTemplate
  onUpdate: () => void
  onEdit: () => void
  onDelete: () => void
}

function PromptDetailView({ template, onUpdate, onEdit, onDelete }: PromptDetailViewProps) {
  const [activeTab, setActiveTab] = useState<'editor' | 'versions' | 'testing' | 'analytics'>('editor')
  const [versions, setVersions] = useState<PromptVersion[]>([])
  const [selectedVersion, setSelectedVersion] = useState<PromptVersion | null>(null)
  const [loading, setLoading] = useState(false)
  const [showCreateVersionModal, setShowCreateVersionModal] = useState(false)

  const catColor = getCategoryColor(template.category)

  useEffect(() => {
    loadVersions()
  }, [template.id])

  const loadVersions = async () => {
    try {
      setLoading(true)
      const data = await api.listPromptVersions(template.slug)
      setVersions(data)
      if (data.length > 0 && !selectedVersion) {
        // Select the published version or the first version
        const published = data.find((v) => v.is_published)
        setSelectedVersion(published || data[0])
      }
    } catch (err) {
      console.error('Error loading versions:', err)
    } finally {
      setLoading(false)
    }
  }

  const handlePublishVersion = async (version: string) => {
    try {
      await api.publishPromptVersion(template.slug, version)
      await loadVersions()
      onUpdate()
    } catch (err: any) {
      alert(`Failed to publish version: ${err.message}`)
    }
  }

  const tabs = [
    { key: 'editor' as const, label: 'Editor', icon: FileText },
    { key: 'versions' as const, label: `Versions (${versions.length})`, icon: GitBranch },
    { key: 'testing' as const, label: 'Testing', icon: Beaker },
    { key: 'analytics' as const, label: 'Analytics', icon: BarChart3 },
  ]

  return (
    <div className="space-y-6">
      {/* Template Header */}
      <div className="rounded-lg p-6" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)', borderLeft: `3px solid ${catColor}` }}>
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <h2 className="text-2xl font-bold mb-2" style={{ color: 'var(--text-primary)' }}>{template.name}</h2>
            <p className="mb-4" style={{ color: 'var(--text-secondary)' }}>{template.description}</p>
            <div className="flex items-center gap-3">
              <code
                className="px-3 py-1 rounded text-sm font-mono"
                style={{ background: 'var(--bg-tertiary)', color: 'var(--text-secondary)' }}
              >
                {template.slug}
              </code>
              {template.category && (
                <span
                  className="px-2 py-0.5 text-xs font-medium rounded-md"
                  style={{ background: `color-mix(in srgb, ${catColor} 15%, transparent)`, color: catColor }}
                >
                  {template.category}
                </span>
              )}
              <span
                className="px-2 py-0.5 text-xs font-medium rounded-md"
                style={
                  template.is_active
                    ? { background: 'color-mix(in srgb, var(--green) 15%, transparent)', color: 'var(--green)' }
                    : { background: 'var(--bg-tertiary)', color: 'var(--text-tertiary)' }
                }
              >
                {template.is_active ? 'Active' : 'Inactive'}
              </span>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={onEdit}
              className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg"
              style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}
            >
              <Edit2 className="w-4 h-4" />
              Edit
            </button>
            <button
              onClick={onDelete}
              className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg"
              style={{ background: 'color-mix(in srgb, var(--error) 10%, transparent)', color: 'var(--error)', border: '1px solid color-mix(in srgb, var(--error) 25%, transparent)' }}
            >
              <Trash2 className="w-4 h-4" />
              Delete
            </button>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="rounded-lg overflow-hidden" style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-primary)' }}>
        <div className="flex" style={{ borderBottom: '1px solid var(--border-primary)', background: 'var(--bg-tertiary)' }}>
          {tabs.map((tab) => {
            const TabIcon = tab.icon
            const isActive = activeTab === tab.key
            return (
              <button
                key={tab.key}
                className="px-5 py-3 font-medium text-sm flex items-center gap-2 transition-colors"
                style={
                  isActive
                    ? { color: 'var(--accent)', borderBottom: '2px solid var(--accent)', background: 'var(--bg-secondary)' }
                    : { color: 'var(--text-tertiary)', borderBottom: '2px solid transparent' }
                }
                onClick={() => setActiveTab(tab.key)}
              >
                <TabIcon className="w-4 h-4" />
                {tab.label}
              </button>
            )
          })}
        </div>

        <div className="p-6">
          {activeTab === 'editor' && selectedVersion && (
            <PromptEditorTab
              version={selectedVersion}
              onCreateVersion={() => setShowCreateVersionModal(true)}
            />
          )}
          {activeTab === 'versions' && (
            <VersionsTab
              versions={versions}
              selectedVersion={selectedVersion}
              onSelect={setSelectedVersion}
              onPublish={handlePublishVersion}
              onCreateNew={() => setShowCreateVersionModal(true)}
            />
          )}
          {activeTab === 'testing' && selectedVersion && (
            <TestingTab template={template} version={selectedVersion} />
          )}
          {activeTab === 'analytics' && selectedVersion && (
            <AnalyticsTab template={template} version={selectedVersion} />
          )}
        </div>
      </div>

      {showCreateVersionModal && (
        <CreateVersionModal
          template={template}
          onClose={() => setShowCreateVersionModal(false)}
          onSuccess={() => {
            setShowCreateVersionModal(false)
            loadVersions()
          }}
        />
      )}
    </div>
  )
}

// ============================================================================
// Prompt Editor Tab
// ============================================================================

interface PromptEditorTabProps {
  version: PromptVersion
  onCreateVersion: () => void
}

function PromptEditorTab({ version, onCreateVersion }: PromptEditorTabProps) {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold" style={{ color: 'var(--text-primary)' }}>Version {version.version}</h3>
          <p className="text-sm" style={{ color: 'var(--text-secondary)' }}>
            {version.is_published ? 'Published' : 'Draft'} &bull; Created {new Date(version.created_at).toLocaleString()}
          </p>
        </div>
        <button
          onClick={onCreateVersion}
          className="flex items-center gap-1 px-3 py-1.5 text-sm font-medium rounded-lg"
          style={{ background: 'var(--accent)', color: 'var(--bg-primary)' }}
        >
          <Plus className="w-4 h-4" />
          New Version
        </button>
      </div>

      {/* Variables */}
      {version.variables && version.variables.length > 0 && (
        <div className="rounded-lg p-4" style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-primary)' }}>
          <h4 className="text-sm font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
            <Code size={14} />
            Variables
          </h4>
          <div className="flex flex-wrap gap-2">
            {version.variables.map((variable) => (
              <code
                key={variable}
                className="px-3 py-1 rounded text-sm font-mono"
                style={{ background: 'color-mix(in srgb, var(--accent) 15%, transparent)', color: 'var(--accent)' }}
              >
                {`{{${variable}}}`}
              </code>
            ))}
          </div>
        </div>
      )}

      {/* Content */}
      <div>
        <h4 className="text-sm font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
          <FileText size={14} />
          Prompt Content
        </h4>
        <pre
          className="p-4 rounded-lg text-sm font-mono whitespace-pre-wrap"
          style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}
        >
          {version.content}
        </pre>
      </div>

      {/* Model Hint */}
      {version.model_hint && (
        <div>
          <h4 className="text-sm font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
            <Cpu size={14} />
            Suggested Model
          </h4>
          <span
            className="px-3 py-1 rounded-md text-sm font-mono"
            style={{ background: 'color-mix(in srgb, var(--purple) 15%, transparent)', color: 'var(--purple)' }}
          >
            {version.model_hint}
          </span>
        </div>
      )}

      {/* Metadata */}
      {version.metadata && Object.keys(version.metadata).length > 0 && (
        <div>
          <h4 className="text-sm font-medium mb-2 flex items-center gap-2" style={{ color: 'var(--text-secondary)' }}>
            <Tag size={14} />
            Metadata
          </h4>
          <pre
            className="p-4 rounded-lg text-sm font-mono whitespace-pre-wrap"
            style={{ background: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border-primary)' }}
          >
            {JSON.stringify(version.metadata, null, 2)}
          </pre>
        </div>
      )}
    </div>
  )
}
