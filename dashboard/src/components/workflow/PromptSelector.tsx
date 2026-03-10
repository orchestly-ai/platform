/**
 * Prompt Selector Component
 *
 * Allows users to either:
 * 1. Write a manual prompt
 * 2. Select a prompt from the Prompt Registry
 */

import { useState, useEffect } from 'react'
import { FileText, X, Search, BookOpen } from 'lucide-react'
import api from '@/services/api'
import type { PromptTemplate, PromptVersion } from '@/types/prompt'
import VariablePicker from './VariablePicker'
import { Node, Edge } from 'reactflow'
import { AgentNodeData } from '../../types'

interface PromptSelectorProps {
  // Current values
  promptSlug?: string
  promptVersion?: string
  manualPrompt?: string
  promptVariables?: Record<string, string>

  // Callbacks
  onPromptChange: (config: {
    promptSlug?: string
    promptVersion?: string
    manualPrompt?: string
    promptVariables?: Record<string, string>
  }) => void

  // For variable picker
  nodes: Node<AgentNodeData>[]
  edges: Edge[]
  currentNodeId: string
}

export default function PromptSelector({
  promptSlug,
  promptVersion,
  manualPrompt,
  promptVariables = {},
  onPromptChange,
  nodes,
  edges,
  currentNodeId,
}: PromptSelectorProps) {
  const [mode, setMode] = useState<'manual' | 'registry'>((promptSlug ? 'registry' : 'manual'))
  const [showRegistry, setShowRegistry] = useState(false)
  const [templates, setTemplates] = useState<PromptTemplate[]>([])
  const [selectedTemplate, setSelectedTemplate] = useState<PromptTemplate | null>(null)
  const [versions, setVersions] = useState<PromptVersion[]>([])
  const [loading, setLoading] = useState(false)
  const [searchQuery, setSearchQuery] = useState('')

  // Load templates when registry is opened
  useEffect(() => {
    if (showRegistry && templates.length === 0) {
      loadTemplates()
    }
  }, [showRegistry])

  // Load versions when template is selected
  useEffect(() => {
    if (selectedTemplate) {
      loadVersions(selectedTemplate.slug)
    }
  }, [selectedTemplate?.id])

  // Load template if promptSlug is provided
  useEffect(() => {
    if (promptSlug && mode === 'registry') {
      api.getPromptTemplate(promptSlug)
        .then(setSelectedTemplate)
        .catch(console.error)
    }
  }, [promptSlug, mode])

  const loadTemplates = async () => {
    try {
      setLoading(true)
      const data = await api.listPromptTemplates({ is_active: true })
      setTemplates(data)
    } catch (err) {
      console.error('Failed to load templates:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadVersions = async (slug: string) => {
    try {
      const data = await api.listPromptVersions(slug)
      setVersions(data.filter(v => v.is_published)) // Only show published versions
    } catch (err) {
      console.error('Failed to load versions:', err)
    }
  }

  const handleSelectTemplate = (template: PromptTemplate) => {
    setSelectedTemplate(template)
    setShowRegistry(false)

    // Auto-select the latest published version
    loadVersions(template.slug).then(() => {
      const publishedVersions = versions.filter(v => v.is_published)
      const latestVersion = publishedVersions[0] // Assuming sorted by date desc

      onPromptChange({
        promptSlug: template.slug,
        promptVersion: latestVersion?.version,
        manualPrompt: undefined,
        promptVariables: {},
      })
    })
  }

  const handleVersionChange = (version: string) => {
    onPromptChange({
      promptSlug,
      promptVersion: version,
      promptVariables,
    })
  }

  const handleVariableChange = (variable: string, value: string) => {
    onPromptChange({
      promptSlug,
      promptVersion,
      promptVariables: {
        ...promptVariables,
        [variable]: value,
      },
    })
  }

  const handleModeChange = (newMode: 'manual' | 'registry') => {
    setMode(newMode)
    if (newMode === 'manual') {
      onPromptChange({
        manualPrompt: manualPrompt || '',
        promptSlug: undefined,
        promptVersion: undefined,
        promptVariables: undefined,
      })
    } else {
      setShowRegistry(true)
    }
  }

  const filteredTemplates = templates.filter(t =>
    t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.slug.toLowerCase().includes(searchQuery.toLowerCase()) ||
    t.description?.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const selectedVersion = versions.find(v => v.version === promptVersion)

  return (
    <div className="space-y-3">
      {/* Mode Selector */}
      <div className="flex gap-2 p-1 bg-gray-100 rounded-lg">
        <button
          onClick={() => handleModeChange('manual')}
          className={`flex-1 px-3 py-1.5 text-sm font-medium rounded transition-colors ${
            mode === 'manual'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          Manual Prompt
        </button>
        <button
          onClick={() => handleModeChange('registry')}
          className={`flex-1 px-3 py-1.5 text-sm font-medium rounded transition-colors ${
            mode === 'registry'
              ? 'bg-white text-gray-900 shadow-sm'
              : 'text-gray-600 hover:text-gray-900'
          }`}
        >
          <FileText className="w-4 h-4 inline mr-1" />
          From Registry
        </button>
      </div>

      {/* Manual Mode */}
      {mode === 'manual' && (
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Prompt Text
          </label>
          <VariablePicker
            value={manualPrompt || ''}
            onChange={(value) => onPromptChange({ manualPrompt: value })}
            nodes={nodes}
            edges={edges}
            currentNodeId={currentNodeId}
            placeholder="Enter prompt for this agent. Type {{ to insert variables."
            rows={6}
          />
        </div>
      )}

      {/* Registry Mode */}
      {mode === 'registry' && (
        <div className="space-y-3">
          {/* Selected Template */}
          {selectedTemplate ? (
            <div className="border border-gray-200 rounded-lg p-3 bg-gray-50">
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1">
                  <div className="font-medium text-gray-900">{selectedTemplate.name}</div>
                  <div className="text-xs text-gray-500 font-mono">{selectedTemplate.slug}</div>
                </div>
                <button
                  onClick={() => setShowRegistry(true)}
                  className="text-sm text-blue-600 hover:text-blue-700"
                >
                  Change
                </button>
              </div>

              {selectedTemplate.description && (
                <p className="text-sm text-gray-600 mb-2">{selectedTemplate.description}</p>
              )}

              {/* Version Selector */}
              {versions.length > 0 && (
                <div>
                  <label className="block text-xs font-medium text-gray-700 mb-1">
                    Version
                  </label>
                  <select
                    value={promptVersion || ''}
                    onChange={(e) => handleVersionChange(e.target.value)}
                    className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  >
                    {versions.map((v) => (
                      <option key={v.id} value={v.version}>
                        v{v.version} {v.is_published ? '(Published)' : ''}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Variable Mappings */}
              {selectedVersion && selectedVersion.variables.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-200">
                  <div className="text-xs font-medium text-gray-700 mb-2">
                    Map Variables
                  </div>
                  <div className="space-y-2">
                    {selectedVersion.variables.map((variable) => (
                      <div key={variable}>
                        <label className="block text-xs text-gray-600 mb-1">
                          {`{{${variable}}}`}
                        </label>
                        <VariablePicker
                          value={promptVariables[variable] || ''}
                          onChange={(value) => handleVariableChange(variable, value)}
                          nodes={nodes}
                          edges={edges}
                          currentNodeId={currentNodeId}
                          placeholder={`Value for ${variable}`}
                          rows={2}
                        />
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Preview Button */}
              <div className="mt-3 pt-3 border-t border-gray-200">
                <a
                  href={`/prompts`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1"
                >
                  <BookOpen className="w-3.5 h-3.5" />
                  View in Prompt Registry
                </a>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowRegistry(true)}
              className="w-full px-4 py-3 border-2 border-dashed border-gray-300 rounded-lg text-sm text-gray-600 hover:border-blue-400 hover:text-blue-600 transition-colors flex items-center justify-center gap-2"
            >
              <FileText className="w-4 h-4" />
              Select from Prompt Registry
            </button>
          )}
        </div>
      )}

      {/* Prompt Registry Modal */}
      {showRegistry && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg w-full max-w-3xl max-h-[80vh] flex flex-col m-4">
            {/* Header */}
            <div className="flex items-center justify-between p-4 border-b border-gray-200">
              <h3 className="text-lg font-semibold text-gray-900">Select Prompt Template</h3>
              <button
                onClick={() => setShowRegistry(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Search */}
            <div className="p-4 border-b border-gray-200">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search prompts..."
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>

            {/* Templates List */}
            <div className="flex-1 overflow-y-auto p-4">
              {loading ? (
                <div className="text-center py-8 text-gray-500">Loading templates...</div>
              ) : filteredTemplates.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                  {searchQuery ? 'No templates found matching your search' : 'No active templates available'}
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {filteredTemplates.map((template) => (
                    <button
                      key={template.id}
                      onClick={() => handleSelectTemplate(template)}
                      className="text-left p-3 border border-gray-200 rounded-lg hover:border-blue-400 hover:bg-blue-50 transition-all"
                    >
                      <div className="font-medium text-gray-900 mb-1">{template.name}</div>
                      <div className="text-xs text-gray-500 font-mono mb-2">{template.slug}</div>
                      {template.description && (
                        <div className="text-sm text-gray-600 line-clamp-2">{template.description}</div>
                      )}
                      {template.category && (
                        <div className="mt-2">
                          <span className="inline-block px-2 py-0.5 bg-blue-100 text-blue-800 text-xs rounded">
                            {template.category}
                          </span>
                        </div>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
