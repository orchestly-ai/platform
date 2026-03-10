/**
 * Prompt Registry Components
 *
 * Supporting components for the Prompt Registry feature
 */

import { useState, useEffect } from 'react'
import { GitBranch, CheckCircle, Play, TrendingUp, X } from 'lucide-react'
import api from '@/services/api'
import type {
  PromptTemplate,
  PromptVersion,
  PromptUsageStats,
  PromptCategory,
  CreateTemplateRequest,
  CreateVersionRequest,
  UpdateTemplateRequest,
  RenderPromptResponse,
} from '@/types/prompt'

// ============================================================================
// Versions Tab
// ============================================================================

interface VersionsTabProps {
  versions: PromptVersion[]
  selectedVersion: PromptVersion | null
  onSelect: (version: PromptVersion) => void
  onPublish: (version: string) => Promise<void>
  onCreateNew: () => void
}

export function VersionsTab({
  versions,
  selectedVersion,
  onSelect,
  onPublish,
  onCreateNew,
}: VersionsTabProps) {
  const [publishing, setPublishing] = useState<string | null>(null)

  const handlePublish = async (version: string) => {
    try {
      setPublishing(version)
      await onPublish(version)
    } catch (err) {
      console.error('Error publishing version:', err)
    } finally {
      setPublishing(null)
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Version History</h3>
        <button className="btn btn-primary" onClick={onCreateNew}>
          <GitBranch className="w-4 h-4" />
          New Version
        </button>
      </div>

      <div className="space-y-3">
        {versions.map((version) => (
          <div
            key={version.id}
            className={`p-4 rounded-lg border-2 cursor-pointer transition-colors ${
              selectedVersion?.id === version.id
                ? 'border-blue-600 bg-blue-50'
                : 'border-gray-200 hover:border-gray-300'
            }`}
            onClick={() => onSelect(version)}
          >
            <div className="flex items-start justify-between">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <span className="text-lg font-semibold text-gray-900">v{version.version}</span>
                  {version.is_published && (
                    <span className="badge badge-green">
                      <CheckCircle className="w-3 h-3" />
                      Published
                    </span>
                  )}
                  {version.model_hint && (
                    <span className="badge badge-blue">{version.model_hint}</span>
                  )}
                </div>

                <div className="text-sm text-gray-600 mb-2">
                  Created {new Date(version.created_at).toLocaleString()}
                  {version.published_at && (
                    <> • Published {new Date(version.published_at).toLocaleString()}</>
                  )}
                </div>

                {version.variables && version.variables.length > 0 && (
                  <div className="flex flex-wrap gap-1">
                    {version.variables.map((variable) => (
                      <code
                        key={variable}
                        className="px-2 py-0.5 bg-gray-100 text-gray-700 rounded text-xs font-mono"
                      >
                        {`{{${variable}}}`}
                      </code>
                    ))}
                  </div>
                )}
              </div>

              {!version.is_published && (
                <button
                  className="btn btn-sm btn-secondary"
                  onClick={(e) => {
                    e.stopPropagation()
                    handlePublish(version.version)
                  }}
                  disabled={publishing === version.version}
                >
                  {publishing === version.version ? 'Publishing...' : 'Publish'}
                </button>
              )}
            </div>
          </div>
        ))}

        {versions.length === 0 && (
          <div className="text-center py-8 text-gray-500">
            <GitBranch className="w-12 h-12 mx-auto mb-3 text-gray-400" />
            <p>No versions yet</p>
            <button className="btn btn-primary mt-4" onClick={onCreateNew}>
              Create First Version
            </button>
          </div>
        )}
      </div>
    </div>
  )
}

// ============================================================================
// Testing Tab
// ============================================================================

interface TestingTabProps {
  template: PromptTemplate
  version: PromptVersion
}

export function TestingTab({ template, version }: TestingTabProps) {
  const [variables, setVariables] = useState<Record<string, string>>({})
  const [rendering, setRendering] = useState(false)
  const [result, setResult] = useState<RenderPromptResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  // Initialize variables with empty strings
  useEffect(() => {
    const vars: Record<string, string> = {}
    version.variables?.forEach((varName) => {
      vars[varName] = ''
    })
    setVariables(vars)
    setResult(null)
    setError(null)
  }, [version.id])

  const handleRender = async () => {
    try {
      setRendering(true)
      setError(null)
      const response = await api.renderPrompt(template.slug, {
        version: version.version,
        variables,
      })
      setResult(response)
    } catch (err: any) {
      setError(err.message || 'Failed to render prompt')
    } finally {
      setRendering(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Test Prompt Rendering</h3>
        <p className="text-sm text-gray-600 mb-4">
          Fill in the variables and click "Render" to see how the prompt will look with your values.
        </p>
      </div>

      {/* Variables Input */}
      {version.variables && version.variables.length > 0 ? (
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-gray-700">Variables</h4>
          <div className="grid grid-cols-1 gap-4">
            {version.variables.map((varName) => (
              <div key={varName}>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  <code className="px-2 py-1 bg-gray-100 rounded text-sm font-mono">
                    {`{{${varName}}}`}
                  </code>
                </label>
                <input
                  type="text"
                  className="input w-full"
                  value={variables[varName] || ''}
                  onChange={(e) =>
                    setVariables((prev) => ({ ...prev, [varName]: e.target.value }))
                  }
                  placeholder={`Enter value for ${varName}...`}
                />
              </div>
            ))}
          </div>

          <button
            className="btn btn-primary"
            onClick={handleRender}
            disabled={rendering}
          >
            <Play className="w-4 h-4" />
            {rendering ? 'Rendering...' : 'Render Prompt'}
          </button>
        </div>
      ) : (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-6 text-center">
          <p className="text-gray-600">This prompt has no variables</p>
          <button className="btn btn-primary mt-4" onClick={handleRender} disabled={rendering}>
            <Play className="w-4 h-4" />
            {rendering ? 'Rendering...' : 'Render Prompt'}
          </button>
        </div>
      )}

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <p className="text-red-800">{error}</p>
        </div>
      )}

      {/* Rendered Output */}
      {result && (
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-gray-700">Rendered Output</h4>
          <pre className="p-4 bg-green-50 rounded-lg text-sm font-mono whitespace-pre-wrap border border-green-200">
            {result.rendered_content}
          </pre>

          {result.model_hint && (
            <div className="text-sm text-gray-600">
              <strong>Suggested Model:</strong> {result.model_hint}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Analytics Tab
// ============================================================================

interface AnalyticsTabProps {
  template: PromptTemplate
  version: PromptVersion
}

export function AnalyticsTab({ template, version }: AnalyticsTabProps) {
  const [stats, setStats] = useState<PromptUsageStats[]>([])
  const [loading, setLoading] = useState(true)
  const [days, setDays] = useState(30)

  useEffect(() => {
    loadStats()
  }, [template.id, version.id, days])

  const loadStats = async () => {
    try {
      setLoading(true)
      const data = await api.getPromptUsageStats(template.slug, version.version, days)
      setStats(data)
    } catch (err) {
      console.error('Error loading stats:', err)
    } finally {
      setLoading(false)
    }
  }

  const totalInvocations = stats.reduce((sum, s) => sum + s.invocations, 0)
  const avgLatency =
    stats.reduce((sum, s) => sum + (s.avg_latency_ms || 0), 0) / (stats.length || 1)
  const avgTokens = Math.round(
    stats.reduce((sum, s) => sum + (s.avg_tokens || 0), 0) / (stats.length || 1)
  )
  const avgSuccessRate =
    stats.reduce((sum, s) => sum + (s.success_rate || 0), 0) / (stats.length || 1)

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900">Usage Analytics</h3>
        <select
          className="input w-32"
          value={days}
          onChange={(e) => setDays(Number(e.target.value))}
        >
          <option value={7}>7 days</option>
          <option value={30}>30 days</option>
          <option value={90}>90 days</option>
        </select>
      </div>

      {loading ? (
        <div className="text-center py-12">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-gray-200 border-t-blue-600" />
          <p className="mt-4 text-gray-600">Loading analytics...</p>
        </div>
      ) : stats.length === 0 ? (
        <div className="bg-gray-50 border border-gray-200 rounded-lg p-12 text-center">
          <TrendingUp className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <p className="text-gray-600">No usage data available yet</p>
        </div>
      ) : (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="card">
              <div className="text-sm text-gray-600 mb-1">Total Invocations</div>
              <div className="text-2xl font-bold text-gray-900">{totalInvocations.toLocaleString()}</div>
            </div>
            <div className="card">
              <div className="text-sm text-gray-600 mb-1">Avg Latency</div>
              <div className="text-2xl font-bold text-gray-900">{avgLatency.toFixed(1)}ms</div>
            </div>
            <div className="card">
              <div className="text-sm text-gray-600 mb-1">Avg Tokens</div>
              <div className="text-2xl font-bold text-gray-900">{avgTokens}</div>
            </div>
            <div className="card">
              <div className="text-sm text-gray-600 mb-1">Success Rate</div>
              <div className="text-2xl font-bold text-gray-900">
                {(avgSuccessRate * 100).toFixed(1)}%
              </div>
            </div>
          </div>

          {/* Daily Stats Table */}
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-3">Daily Statistics</h4>
            <div className="border border-gray-200 rounded-lg overflow-hidden">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Date
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      Invocations
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      Avg Latency
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      Avg Tokens
                    </th>
                    <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">
                      Success Rate
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {stats.map((stat) => (
                    <tr key={stat.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {new Date(stat.date).toLocaleDateString()}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900 text-right">
                        {stat.invocations.toLocaleString()}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900 text-right">
                        {stat.avg_latency_ms?.toFixed(1) || '-'}ms
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900 text-right">
                        {stat.avg_tokens || '-'}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900 text-right">
                        {stat.success_rate ? `${(stat.success_rate * 100).toFixed(1)}%` : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

// ============================================================================
// Create Template Modal
// ============================================================================

interface CreateTemplateModalProps {
  onClose: () => void
  onSuccess: () => void
  categories: PromptCategory[]
}

export function CreateTemplateModal({ onClose, onSuccess, categories }: CreateTemplateModalProps) {
  const [formData, setFormData] = useState<CreateTemplateRequest>({
    name: '',
    description: '',
    category: '',
  })
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setCreating(true)
      setError(null)
      await api.createPromptTemplate(formData)
      onSuccess()
    } catch (err: any) {
      setError(err.message || 'Failed to create template')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold text-gray-900">Create Prompt Template</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3">
            <p className="text-red-800 text-sm">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Template Name *
            </label>
            <input
              type="text"
              className="input w-full"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              placeholder="e.g., Customer Support Agent"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Description</label>
            <textarea
              className="input w-full h-24"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Describe the purpose of this prompt..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Category</label>
            <select
              className="input w-full"
              value={formData.category}
              onChange={(e) => setFormData({ ...formData, category: e.target.value })}
            >
              <option value="">Select a category...</option>
              {categories.map((category) => (
                <option key={category} value={category}>
                  {category.charAt(0).toUpperCase() + category.slice(1).replace('_', ' ')}
                </option>
              ))}
            </select>
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              className="btn btn-secondary flex-1"
              onClick={onClose}
              disabled={creating}
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary flex-1" disabled={creating}>
              {creating ? 'Creating...' : 'Create Template'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// ============================================================================
// Create Version Modal
// ============================================================================

interface CreateVersionModalProps {
  template: PromptTemplate
  onClose: () => void
  onSuccess: () => void
}

export function CreateVersionModal({ template, onClose, onSuccess }: CreateVersionModalProps) {
  const [formData, setFormData] = useState<CreateVersionRequest>({
    version: '',
    content: '',
    model_hint: '',
    metadata: {},
  })
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [detectedVariables, setDetectedVariables] = useState<string[]>([])

  // Detect variables when content changes
  useEffect(() => {
    const regex = /\{\{(\w+)\}\}/g
    const matches = [...formData.content.matchAll(regex)]
    const vars = [...new Set(matches.map((m) => m[1]))]
    setDetectedVariables(vars)
  }, [formData.content])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setCreating(true)
      setError(null)
      await api.createPromptVersion(template.slug, formData)
      onSuccess()
    } catch (err: any) {
      setError(err.message || 'Failed to create version')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold text-gray-900">Create New Version</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3">
            <p className="text-red-800 text-sm">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Version (Semantic Versioning) *
            </label>
            <input
              type="text"
              className="input w-full"
              value={formData.version}
              onChange={(e) => setFormData({ ...formData, version: e.target.value })}
              required
              placeholder="e.g., 1.0.0, 1.1.0, 2.0.0"
              pattern="^\d+\.\d+\.\d+$"
              title="Version must follow semantic versioning (e.g., 1.0.0)"
            />
            <p className="mt-1 text-xs text-gray-500">
              Format: MAJOR.MINOR.PATCH (e.g., 1.0.0)
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Prompt Content *
            </label>
            <textarea
              className="input w-full h-48 font-mono text-sm"
              value={formData.content}
              onChange={(e) => setFormData({ ...formData, content: e.target.value })}
              required
              placeholder="Enter your prompt here. Use {{variable_name}} for variables..."
            />
            <p className="mt-1 text-xs text-gray-500">
              Use {`{{variable_name}}`} syntax for variables
            </p>
          </div>

          {detectedVariables.length > 0 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Detected Variables
              </label>
              <div className="flex flex-wrap gap-2">
                {detectedVariables.map((variable) => (
                  <code
                    key={variable}
                    className="px-3 py-1 bg-blue-50 text-blue-700 rounded text-sm font-mono"
                  >
                    {`{{${variable}}}`}
                  </code>
                ))}
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Model Hint (Optional)
            </label>
            <input
              type="text"
              className="input w-full"
              value={formData.model_hint}
              onChange={(e) => setFormData({ ...formData, model_hint: e.target.value })}
              placeholder="e.g., gpt-4o, claude-3-opus, etc."
            />
            <p className="mt-1 text-xs text-gray-500">
              Suggest which model works best with this prompt
            </p>
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              className="btn btn-secondary flex-1"
              onClick={onClose}
              disabled={creating}
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary flex-1" disabled={creating}>
              {creating ? 'Creating...' : 'Create Version'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
// ============================================================================
// Edit Template Modal
// ============================================================================

interface EditTemplateModalProps {
  template: PromptTemplate
  onClose: () => void
  onSuccess: () => void
  categories: PromptCategory[]
}

export function EditTemplateModal({ template, onClose, onSuccess, categories }: EditTemplateModalProps) {
  const [formData, setFormData] = useState<UpdateTemplateRequest>({
    name: template.name,
    description: template.description || '',
    category: template.category || '',
    is_active: template.is_active,
  })
  const [updating, setUpdating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    try {
      setUpdating(true)
      setError(null)
      await api.updatePromptTemplate(template.slug, formData)
      onSuccess()
    } catch (err: any) {
      setError(err.message || 'Failed to update template')
    } finally {
      setUpdating(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full mx-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-xl font-semibold text-gray-900">Edit Template</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mb-4 bg-red-50 border border-red-200 rounded-lg p-3">
            <p className="text-red-800 text-sm">{error}</p>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Template Name *
            </label>
            <input
              type="text"
              className="input w-full"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              required
              placeholder="e.g., Customer Support Agent"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Description</label>
            <textarea
              className="input w-full h-24"
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="Describe the purpose of this prompt..."
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">Category</label>
            <select
              className="input w-full"
              value={formData.category}
              onChange={(e) => setFormData({ ...formData, category: e.target.value })}
            >
              <option value="">Select a category...</option>
              {categories.map((category) => (
                <option key={category} value={category}>
                  {category.charAt(0).toUpperCase() + category.slice(1).replace('_', ' ')}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center">
            <input
              type="checkbox"
              id="is_active"
              className="mr-2"
              checked={formData.is_active}
              onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
            />
            <label htmlFor="is_active" className="text-sm font-medium text-gray-700">
              Active
            </label>
          </div>

          <div className="flex gap-3 pt-4">
            <button
              type="button"
              className="btn btn-secondary flex-1"
              onClick={onClose}
              disabled={updating}
            >
              Cancel
            </button>
            <button type="submit" className="btn btn-primary flex-1" disabled={updating}>
              {updating ? 'Updating...' : 'Update Template'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
