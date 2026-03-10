import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import {
  FolderOpen,
  Plus,
  Search,
  Copy,
  Trash2,
  Play,
  Clock,
  DollarSign,
  Workflow as WorkflowIcon,
} from 'lucide-react'
import { Workflow } from '../types'

async function fetchWorkflows(): Promise<{ workflows: Workflow[] }> {
  const response = await fetch('/api/workflows')
  if (!response.ok) {
    throw new Error('Failed to fetch workflows')
  }
  return response.json()
}

async function deleteWorkflow(workflowId: string): Promise<void> {
  const response = await fetch(`/api/workflows/${workflowId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error('Failed to delete workflow')
  }
}

async function cloneWorkflow(workflowId: string): Promise<Workflow> {
  const response = await fetch(`/api/workflows/${workflowId}/clone`, {
    method: 'POST',
  })
  if (!response.ok) {
    throw new Error('Failed to clone workflow')
  }
  return response.json()
}

export default function WorkflowGallery() {
  const navigate = useNavigate()
  const [searchQuery, setSearchQuery] = useState('')
  const [filterTemplate, setFilterTemplate] = useState<boolean | null>(null)

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['workflows'],
    queryFn: fetchWorkflows,
    refetchInterval: 10000, // Refresh every 10 seconds
  })

  const handleNewWorkflow = () => {
    navigate('/workflows')
  }

  const handleOpenWorkflow = (workflowId: string) => {
    navigate(`/workflows?id=${workflowId}`)
  }

  const handleCloneWorkflow = async (workflowId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await cloneWorkflow(workflowId)
      refetch()
    } catch (error) {
      console.error('Failed to clone workflow:', error)
      alert('Failed to clone workflow')
    }
  }

  const handleDeleteWorkflow = async (workflowId: string, e: React.MouseEvent) => {
    e.stopPropagation()
    if (!confirm('Are you sure you want to delete this workflow?')) {
      return
    }
    try {
      await deleteWorkflow(workflowId)
      refetch()
    } catch (error) {
      console.error('Failed to delete workflow:', error)
      alert('Failed to delete workflow')
    }
  }

  const filteredWorkflows = data?.workflows.filter((workflow) => {
    const matchesSearch = workflow.name.toLowerCase().includes(searchQuery.toLowerCase())
    const matchesFilter =
      filterTemplate === null ? true : workflow.isTemplate === filterTemplate
    return matchesSearch && matchesFilter
  })

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Workflow Gallery</h1>
            <p className="text-sm text-gray-600 mt-1">
              Browse, create, and manage your agent workflows
            </p>
          </div>
          <button
            onClick={handleNewWorkflow}
            className="px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 rounded-lg flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            New Workflow
          </button>
        </div>

        {/* Search and Filters */}
        <div className="mt-4 flex gap-4">
          <div className="flex-1 relative">
            <Search className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search workflows..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => setFilterTemplate(null)}
              className={`px-4 py-2 rounded-lg border ${
                filterTemplate === null
                  ? 'bg-blue-50 border-blue-500 text-blue-700'
                  : 'border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setFilterTemplate(false)}
              className={`px-4 py-2 rounded-lg border ${
                filterTemplate === false
                  ? 'bg-blue-50 border-blue-500 text-blue-700'
                  : 'border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              My Workflows
            </button>
            <button
              onClick={() => setFilterTemplate(true)}
              className={`px-4 py-2 rounded-lg border ${
                filterTemplate === true
                  ? 'bg-blue-50 border-blue-500 text-blue-700'
                  : 'border-gray-300 text-gray-700 hover:bg-gray-50'
              }`}
            >
              Templates
            </button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-8">
        {isLoading && (
          <div className="text-center py-12">
            <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
            <p className="mt-2 text-gray-600">Loading workflows...</p>
          </div>
        )}

        {error && (
          <div className="text-center py-12">
            <p className="text-red-600">Failed to load workflows</p>
            <button
              onClick={() => refetch()}
              className="mt-2 text-blue-600 hover:text-blue-700"
            >
              Try again
            </button>
          </div>
        )}

        {filteredWorkflows && filteredWorkflows.length === 0 && (
          <div className="text-center py-12">
            <FolderOpen className="w-16 h-16 mx-auto text-gray-400" />
            <h3 className="mt-4 text-lg font-medium text-gray-900">No workflows found</h3>
            <p className="mt-2 text-gray-600">
              {searchQuery
                ? 'Try adjusting your search or filters'
                : 'Get started by creating your first workflow'}
            </p>
            {!searchQuery && (
              <button
                onClick={handleNewWorkflow}
                className="mt-4 px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 rounded-lg inline-flex items-center gap-2"
              >
                <Plus className="w-4 h-4" />
                Create Workflow
              </button>
            )}
          </div>
        )}

        {/* Workflow Grid */}
        {filteredWorkflows && filteredWorkflows.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredWorkflows.map((workflow) => (
              <div
                key={workflow.id}
                onClick={() => handleOpenWorkflow(workflow.id)}
                className="bg-white rounded-lg border border-gray-200 hover:border-blue-500 hover:shadow-lg transition-all cursor-pointer"
              >
                {/* Workflow Preview/Icon */}
                <div className="h-32 bg-gradient-to-br from-blue-50 to-purple-50 rounded-t-lg flex items-center justify-center">
                  <WorkflowIcon className="w-16 h-16 text-blue-400" />
                </div>

                {/* Workflow Info */}
                <div className="p-4">
                  <div className="flex items-start justify-between mb-2">
                    <h3 className="text-lg font-semibold text-gray-900 truncate flex-1">
                      {workflow.name}
                    </h3>
                    {workflow.isTemplate && (
                      <span className="ml-2 px-2 py-0.5 bg-purple-100 text-purple-800 text-xs font-medium rounded">
                        TEMPLATE
                      </span>
                    )}
                  </div>

                  {workflow.description && (
                    <p className="text-sm text-gray-600 line-clamp-2 mb-3">
                      {workflow.description}
                    </p>
                  )}

                  {/* Tags */}
                  {workflow.tags && workflow.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1 mb-3">
                      {workflow.tags.slice(0, 3).map((tag, idx) => (
                        <span
                          key={idx}
                          className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded"
                        >
                          {tag}
                        </span>
                      ))}
                      {workflow.tags.length > 3 && (
                        <span className="px-2 py-0.5 bg-gray-100 text-gray-700 text-xs rounded">
                          +{workflow.tags.length - 3}
                        </span>
                      )}
                    </div>
                  )}

                  {/* Stats */}
                  <div className="flex items-center gap-4 text-xs text-gray-600 mb-3">
                    <div className="flex items-center gap-1">
                      <WorkflowIcon className="w-3 h-3" />
                      <span>{workflow.nodes.length} nodes</span>
                    </div>
                    {workflow.metadata?.executionCount !== undefined && (
                      <div className="flex items-center gap-1">
                        <Play className="w-3 h-3" />
                        <span>{workflow.metadata.executionCount} runs</span>
                      </div>
                    )}
                    {workflow.metadata?.totalCost !== undefined && (
                      <div className="flex items-center gap-1">
                        <DollarSign className="w-3 h-3" />
                        <span>${workflow.metadata.totalCost.toFixed(2)}</span>
                      </div>
                    )}
                  </div>

                  {/* Last Updated */}
                  <div className="flex items-center gap-1 text-xs text-gray-500 mb-3">
                    <Clock className="w-3 h-3" />
                    <span>
                      Updated {new Date(workflow.updatedAt).toLocaleDateString()}
                    </span>
                  </div>

                  {/* Actions */}
                  <div className="flex gap-2 pt-3 border-t border-gray-200">
                    <button
                      onClick={(e) => handleCloneWorkflow(workflow.id, e)}
                      className="flex-1 px-3 py-2 text-sm text-blue-700 hover:bg-blue-50 rounded flex items-center justify-center gap-1"
                    >
                      <Copy className="w-4 h-4" />
                      Clone
                    </button>
                    <button
                      onClick={(e) => handleDeleteWorkflow(workflow.id, e)}
                      className="flex-1 px-3 py-2 text-sm text-red-700 hover:bg-red-50 rounded flex items-center justify-center gap-1"
                    >
                      <Trash2 className="w-4 h-4" />
                      Delete
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
