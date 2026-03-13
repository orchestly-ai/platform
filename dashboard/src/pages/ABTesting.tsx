/**
 * ABTesting Page - Manage A/B experiments for LLM configurations
 *
 * Features:
 * - View active and completed experiments with tabs
 * - Create new experiments with LLM variant selection
 * - Visual conversion rate comparison
 * - Statistical significance with confidence intervals
 * - Experiment timeline and duration tracking
 * - Cost and latency metrics per variant
 * - Declare winners with rollout
 */

import { useState, useMemo } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { UpgradeBanner } from '@/components/UpgradeBanner'
import {
  GitBranch,
  Activity,
  Play,
  Pause,
  CheckCircle,
  Trophy,
  BarChart3,
  Plus,
  X,
  Clock,
  TrendingUp,
  DollarSign,
  Zap,
  Target,
  ArrowUp,
  ArrowDown,
  Calendar,
  AlertCircle,
  Copy,
  Settings,
  Percent,
} from 'lucide-react'
import type { ABExperiment, ABVariant } from '@/types/llm'

// Tab types
type TabType = 'all' | 'running' | 'completed' | 'draft'

interface ExperimentCardProps {
  experiment: ABExperiment
  onPause: (id: string) => void
  onResume: (id: string) => void
  onComplete: (id: string) => void
  onDuplicate: (id: string) => void
}

function ExperimentCard({ experiment, onPause, onResume, onComplete, onDuplicate }: ExperimentCardProps) {
  const statusConfig = {
    draft: { color: 'text-gray-500', bg: 'bg-gray-100', label: 'Draft', dotColor: 'bg-gray-400' },
    running: { color: 'text-blue-500', bg: 'bg-blue-100', label: 'Running', dotColor: 'bg-blue-500' },
    paused: { color: 'text-yellow-500', bg: 'bg-yellow-100', label: 'Paused', dotColor: 'bg-yellow-500' },
    completed: { color: 'text-green-500', bg: 'bg-green-100', label: 'Completed', dotColor: 'bg-green-500' },
  }

  const config = statusConfig[experiment.status]

  // Calculate conversion rates and determine leader
  const variants: (ABVariant & { conversionRate: number })[] = experiment.variants.map(
    (v) => ({
      ...v,
      conversionRate: v.totalRequests > 0 ? (v.conversions / v.totalRequests) * 100 : 0,
    })
  )

  const maxConversionRate = Math.max(...variants.map((v) => v.conversionRate))
  const controlVariant = variants[0]
  const totalRequests = variants.reduce((sum, v) => sum + v.totalRequests, 0)

  // Calculate experiment duration
  const startDate = new Date(experiment.startDate)
  const endDate = experiment.endDate ? new Date(experiment.endDate) : new Date()
  const durationDays = Math.ceil((endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24))

  // Estimate time to significance (simplified)
  const estimatedDaysRemaining = experiment.significanceLevel < 0.95
    ? Math.ceil((0.95 - experiment.significanceLevel) / 0.05 * 3)
    : 0

  return (
    <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
      {/* Header */}
      <div className="p-5 border-b border-gray-100">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <div className="flex items-center gap-3">
              <h3 className="font-semibold text-gray-900 text-lg">{experiment.name}</h3>
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${config.bg} ${config.color}`}>
                <span className={`w-1.5 h-1.5 rounded-full ${config.dotColor}`} />
                {config.label}
              </span>
              {experiment.winner && (
                <span className="inline-flex items-center gap-1 px-2 py-1 bg-yellow-100 text-yellow-700 rounded-full text-xs font-medium">
                  <Trophy className="h-3 w-3" />
                  Winner: {experiment.winner}
                </span>
              )}
            </div>
            <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
              <span className="flex items-center gap-1">
                <Calendar className="h-4 w-4" />
                Started {startDate.toLocaleDateString()}
              </span>
              <span className="flex items-center gap-1">
                <Clock className="h-4 w-4" />
                {durationDays} day{durationDays !== 1 ? 's' : ''} running
              </span>
              <span className="flex items-center gap-1">
                <Target className="h-4 w-4" />
                {totalRequests.toLocaleString()} total requests
              </span>
              {/* Show targeting info */}
              {experiment.taskType && (
                <span className="flex items-center gap-1 px-2 py-0.5 bg-purple-50 text-purple-700 rounded text-xs">
                  {experiment.targetWorkflowIds && experiment.targetWorkflowIds.length > 0 ? (
                    <>
                      <GitBranch className="h-3 w-3" />
                      {experiment.targetWorkflowIds.length === 1 ? (
                        <>Workflow: {experiment.targetWorkflowName || experiment.targetWorkflowIds[0].slice(0, 8)}...</>
                      ) : (
                        <>{experiment.targetWorkflowIds.length} Workflows</>
                      )}
                    </>
                  ) : (
                    <>
                      <Settings className="h-3 w-3" />
                      Task: {experiment.taskType}
                    </>
                  )}
                </span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* Variants Comparison */}
      <div className="p-5">
        <div className="grid gap-4">
          {variants.map((variant, index) => {
            const isWinner = experiment.winner === variant.name
            const isLeading = variant.conversionRate === maxConversionRate && variants.length > 1 && variant.conversionRate > 0
            const isControl = index === 0
            const lift = isControl ? 0 : controlVariant.conversionRate > 0
              ? ((variant.conversionRate - controlVariant.conversionRate) / controlVariant.conversionRate) * 100
              : 0

            return (
              <div
                key={variant.name}
                className={`relative p-4 rounded-lg border-2 transition-all ${
                  isWinner
                    ? 'border-yellow-300 bg-yellow-50'
                    : isLeading
                    ? 'border-green-200 bg-green-50'
                    : 'border-gray-100 bg-gray-50'
                }`}
              >
                {/* Variant Header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-900">{variant.name}</span>
                    {isControl && (
                      <span className="text-xs bg-gray-200 text-gray-600 px-2 py-0.5 rounded">Control</span>
                    )}
                    {isWinner && <Trophy className="h-4 w-4 text-yellow-500" />}
                    {!isWinner && isLeading && (
                      <span className="flex items-center gap-1 text-xs text-green-600 font-medium">
                        <TrendingUp className="h-3 w-3" />
                        Leading
                      </span>
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-gray-600">{variant.traffic}% traffic</span>
                    {!isControl && lift !== 0 && (
                      <span className={`flex items-center gap-0.5 text-xs font-medium ${lift > 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {lift > 0 ? <ArrowUp className="h-3 w-3" /> : <ArrowDown className="h-3 w-3" />}
                        {Math.abs(lift).toFixed(1)}% lift
                      </span>
                    )}
                  </div>
                </div>

                {/* Metrics Grid */}
                <div className="grid grid-cols-5 gap-4">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-gray-900">
                      {variant.totalRequests.toLocaleString()}
                    </p>
                    <p className="text-xs text-gray-500">Requests</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-gray-900">
                      {variant.conversions.toLocaleString()}
                    </p>
                    <p className="text-xs text-gray-500">Conversions</p>
                  </div>
                  <div className="text-center">
                    <p className={`text-2xl font-bold ${isLeading ? 'text-green-600' : 'text-gray-900'}`}>
                      {variant.conversionRate.toFixed(2)}%
                    </p>
                    <p className="text-xs text-gray-500">Conv. Rate</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-gray-900">
                      {variant.avgLatency}ms
                    </p>
                    <p className="text-xs text-gray-500">Avg Latency</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-gray-900">
                      ${variant.costPer1k}
                    </p>
                    <p className="text-xs text-gray-500">Cost/1k</p>
                  </div>
                </div>

                {/* Conversion Rate Bar */}
                <div className="mt-4">
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div
                      className={`h-2 rounded-full transition-all ${
                        isWinner ? 'bg-yellow-500' : isLeading ? 'bg-green-500' : 'bg-blue-500'
                      }`}
                      style={{
                        width: `${
                          maxConversionRate > 0
                            ? (variant.conversionRate / maxConversionRate) * 100
                            : 0
                        }%`,
                      }}
                    />
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Statistical Significance */}
      <div className="px-5 py-4 bg-gray-50 border-t border-gray-100">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-gray-400" />
              <span className="text-sm text-gray-600">Statistical Significance</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-32 bg-gray-200 rounded-full h-2.5">
                <div
                  className={`h-2.5 rounded-full transition-all ${
                    experiment.significanceLevel >= 0.95
                      ? 'bg-green-500'
                      : experiment.significanceLevel >= 0.9
                      ? 'bg-yellow-500'
                      : 'bg-gray-400'
                  }`}
                  style={{ width: `${experiment.significanceLevel * 100}%` }}
                />
              </div>
              <span
                className={`text-sm font-semibold ${
                  experiment.significanceLevel >= 0.95
                    ? 'text-green-600'
                    : experiment.significanceLevel >= 0.9
                    ? 'text-yellow-600'
                    : 'text-gray-500'
                }`}
              >
                {(experiment.significanceLevel * 100).toFixed(0)}%
              </span>
            </div>
            {experiment.status === 'running' && experiment.significanceLevel < 0.95 && (
              <span className="text-xs text-gray-500 flex items-center gap-1">
                <Clock className="h-3 w-3" />
                ~{estimatedDaysRemaining} days to 95%
              </span>
            )}
          </div>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={() => onDuplicate(experiment.id)}
              className="p-2 text-gray-500 hover:text-gray-700 hover:bg-gray-200 rounded-lg transition-colors"
              title="Duplicate"
            >
              <Copy className="h-4 w-4" />
            </button>
            {experiment.status === 'draft' && (
              <button
                onClick={() => onResume(experiment.id)}
                className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-green-600 hover:bg-green-100 rounded-lg transition-colors"
              >
                <Play className="h-4 w-4" />
                Start
              </button>
            )}
            {experiment.status === 'running' && (
              <button
                onClick={() => onPause(experiment.id)}
                className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-yellow-600 hover:bg-yellow-100 rounded-lg transition-colors"
              >
                <Pause className="h-4 w-4" />
                Pause
              </button>
            )}
            {experiment.status === 'paused' && (
              <button
                onClick={() => onResume(experiment.id)}
                className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-blue-600 hover:bg-blue-100 rounded-lg transition-colors"
              >
                <Play className="h-4 w-4" />
                Resume
              </button>
            )}
            {(experiment.status === 'running' || experiment.status === 'paused') && experiment.significanceLevel >= 0.95 && (
              <button
                onClick={() => onComplete(experiment.id)}
                className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-white bg-green-600 hover:bg-green-700 rounded-lg transition-colors"
              >
                <Trophy className="h-4 w-4" />
                Declare Winner
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// Common model options
const MODEL_OPTIONS = [
  { value: '', label: 'No model override' },
  // OpenAI models
  { value: 'openai/gpt-4o', label: 'OpenAI GPT-4o' },
  { value: 'openai/gpt-4o-mini', label: 'OpenAI GPT-4o Mini' },
  // Anthropic models
  { value: 'anthropic/claude-3-5-sonnet-20241022', label: 'Claude 3.5 Sonnet' },
  { value: 'anthropic/claude-3-5-haiku-20241022', label: 'Claude 3.5 Haiku' },
  // Groq models (fast inference)
  { value: 'groq/llama-3.3-70b-versatile', label: 'Groq Llama 3.3 70B' },
  { value: 'groq/llama-3.1-70b-versatile', label: 'Groq Llama 3.1 70B' },
  { value: 'groq/llama-3.1-8b-instant', label: 'Groq Llama 3.1 8B (Fast)' },
  { value: 'groq/llama-guard-3-8b', label: 'Groq Llama Guard 3 8B' },
  { value: 'groq/mixtral-8x7b-32768', label: 'Groq Mixtral 8x7B' },
  { value: 'groq/gemma2-9b-it', label: 'Groq Gemma 2 9B' },
]

// Create Experiment Modal
function CreateExperimentModal({
  isOpen,
  onClose,
  onCreate,
}: {
  isOpen: boolean
  onClose: () => void
  onCreate: (data: { name: string; description: string; task_type?: string; variants: Array<{ name: string; traffic_percentage: number; model_name?: string }> }) => void
}) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [taskType, setTaskType] = useState('')
  const [targetMode, setTargetMode] = useState<'workflows' | 'task_type'>('workflows')
  const [selectedWorkflowIds, setSelectedWorkflowIds] = useState<string[]>([])
  const [variants, setVariants] = useState([
    { name: 'Control (GPT-4)', traffic_percentage: 50, model_name: 'openai/gpt-4o' },
    { name: 'Treatment (Claude)', traffic_percentage: 50, model_name: 'anthropic/claude-3-5-sonnet-20241022' },
  ])

  // Fetch available workflows
  const { data: workflows } = useQuery({
    queryKey: ['workflows'],
    queryFn: () => api.getWorkflows(),
  })

  // Toggle workflow selection
  const toggleWorkflow = (workflowId: string) => {
    setSelectedWorkflowIds(prev =>
      prev.includes(workflowId)
        ? prev.filter(id => id !== workflowId)
        : [...prev, workflowId]
    )
  }

  const totalTraffic = variants.reduce((sum, v) => sum + v.traffic_percentage, 0)
  const trafficError = totalTraffic !== 100

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (trafficError) return

    // Determine the task_type based on targeting mode
    let effectiveTaskType: string | undefined
    if (targetMode === 'workflows' && selectedWorkflowIds.length > 0) {
      // Use workflows:{uuid1,uuid2,...} format for multiple workflow binding
      effectiveTaskType = `workflows:${selectedWorkflowIds.join(',')}`
    } else if (targetMode === 'task_type' && taskType) {
      effectiveTaskType = taskType
    }

    onCreate({ name, description, task_type: effectiveTaskType, variants })
    setName('')
    setDescription('')
    setTaskType('')
    setTargetMode('workflows')
    setSelectedWorkflowIds([])
    setVariants([
      { name: 'Control (GPT-4)', traffic_percentage: 50, model_name: 'openai/gpt-4o' },
      { name: 'Treatment (Claude)', traffic_percentage: 50, model_name: 'anthropic/claude-3-5-sonnet-20241022' },
    ])
  }

  const updateVariant = (index: number, field: 'name' | 'traffic_percentage' | 'model_name', value: string | number) => {
    setVariants((prev) =>
      prev.map((v, i) => (i === index ? { ...v, [field]: value } : v))
    )
  }

  const addVariant = () => {
    const newTraffic = Math.floor(100 / (variants.length + 1))
    setVariants((prev) => [
      ...prev.map((v) => ({ ...v, traffic_percentage: newTraffic })),
      { name: `Variant ${prev.length}`, traffic_percentage: newTraffic, model_name: '' },
    ])
  }

  const removeVariant = (index: number) => {
    if (variants.length <= 2) return
    setVariants((prev) => prev.filter((_, i) => i !== index))
  }

  const equalizeTraffic = () => {
    const equalTraffic = Math.floor(100 / variants.length)
    const remainder = 100 - (equalTraffic * variants.length)
    setVariants((prev) =>
      prev.map((v, i) => ({
        ...v,
        traffic_percentage: equalTraffic + (i === 0 ? remainder : 0)
      }))
    )
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-lg mx-4">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Create New Experiment</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <X className="h-5 w-5" />
          </button>
        </div>
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Experiment Name
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="e.g., GPT-4 vs Claude-3 for Code Tasks"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description (optional)
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Describe what this experiment tests..."
              rows={2}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
            />
          </div>
          {/* Targeting Mode Selector */}
          <div className="bg-gray-50 p-4 rounded-lg border border-gray-200">
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Target (where to apply this experiment)
            </label>
            <div className="flex gap-4 mb-3">
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="targetMode"
                  value="workflows"
                  checked={targetMode === 'workflows'}
                  onChange={() => setTargetMode('workflows')}
                  className="text-purple-600 focus:ring-purple-500"
                />
                <span className="text-sm text-gray-700">Specific Workflow(s)</span>
              </label>
              <label className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="targetMode"
                  value="task_type"
                  checked={targetMode === 'task_type'}
                  onChange={() => setTargetMode('task_type')}
                  className="text-purple-600 focus:ring-purple-500"
                />
                <span className="text-sm text-gray-700">Task Type (category)</span>
              </label>
            </div>

            {targetMode === 'workflows' ? (
              <div>
                {/* Selected count */}
                {selectedWorkflowIds.length > 0 && (
                  <div className="mb-2 flex items-center gap-2">
                    <span className="text-sm font-medium text-purple-600">
                      {selectedWorkflowIds.length} workflow{selectedWorkflowIds.length !== 1 ? 's' : ''} selected
                    </span>
                    <button
                      type="button"
                      onClick={() => setSelectedWorkflowIds([])}
                      className="text-xs text-gray-500 hover:text-gray-700"
                    >
                      Clear all
                    </button>
                  </div>
                )}
                {/* Workflow list with checkboxes */}
                <div className="max-h-48 overflow-y-auto border border-gray-200 rounded-lg bg-white">
                  {workflows && workflows.length > 0 ? (
                    workflows.map((w) => (
                      <label
                        key={w.id}
                        className={`flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-gray-50 border-b border-gray-100 last:border-b-0 ${
                          selectedWorkflowIds.includes(w.id) ? 'bg-purple-50' : ''
                        }`}
                      >
                        <input
                          type="checkbox"
                          checked={selectedWorkflowIds.includes(w.id)}
                          onChange={() => toggleWorkflow(w.id)}
                          className="h-4 w-4 text-purple-600 focus:ring-purple-500 rounded"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="font-medium text-gray-900 truncate">{w.name}</span>
                            <span className={`text-xs px-1.5 py-0.5 rounded ${
                              w.status === 'active' ? 'bg-green-100 text-green-700' :
                              w.status === 'template' ? 'bg-blue-100 text-blue-700' :
                              'bg-gray-100 text-gray-600'
                            }`}>
                              {w.status}
                            </span>
                          </div>
                          <div className="text-xs text-gray-500 font-mono truncate">
                            ID: {w.id}
                          </div>
                        </div>
                      </label>
                    ))
                  ) : (
                    <div className="px-3 py-4 text-center text-gray-500 text-sm">
                      No workflows available. Create a workflow first.
                    </div>
                  )}
                </div>
                <p className="mt-2 text-xs text-gray-500">
                  Select one or more workflows. Experiment will apply to executions of selected workflows only.
                </p>
              </div>
            ) : (
              <div>
                <input
                  type="text"
                  value={taskType}
                  onChange={(e) => setTaskType(e.target.value)}
                  placeholder="e.g., ticket_summarization, code_review, customer_response"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                />
                <p className="mt-1 text-xs text-gray-500">
                  Experiment will apply to any LLM node with this task_type
                </p>
              </div>
            )}
          </div>
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">Variants</label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={equalizeTraffic}
                  className="text-xs text-gray-500 hover:text-gray-700 flex items-center gap-1"
                >
                  <Percent className="h-3 w-3" />
                  Equalize
                </button>
                <button
                  type="button"
                  onClick={addVariant}
                  className="text-sm text-purple-600 hover:text-purple-700"
                >
                  + Add Variant
                </button>
              </div>
            </div>
            <div className="space-y-3">
              {variants.map((variant, index) => (
                <div key={index} className="p-3 border border-gray-200 rounded-lg bg-gray-50">
                  <div className="flex items-center gap-2 mb-2">
                    <div className="w-6 h-6 flex items-center justify-center bg-purple-100 rounded text-xs font-medium text-purple-600">
                      {index === 0 ? 'C' : index}
                    </div>
                    <input
                      type="text"
                      value={variant.name}
                      onChange={(e) => updateVariant(index, 'name', e.target.value)}
                      placeholder="Variant name"
                      className="flex-1 px-3 py-2 border border-gray-300 rounded-lg text-sm"
                    />
                    <div className="flex items-center gap-1">
                      <input
                        type="number"
                        value={variant.traffic_percentage}
                        onChange={(e) => updateVariant(index, 'traffic_percentage', parseInt(e.target.value) || 0)}
                        min={1}
                        max={100}
                        className="w-16 px-2 py-2 border border-gray-300 rounded-lg text-sm text-center"
                      />
                      <span className="text-sm text-gray-500">%</span>
                    </div>
                    {variants.length > 2 && (
                      <button
                        type="button"
                        onClick={() => removeVariant(index)}
                        className="text-gray-400 hover:text-red-500"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                  </div>
                  <div className="ml-8">
                    <select
                      value={variant.model_name}
                      onChange={(e) => updateVariant(index, 'model_name', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm bg-white"
                    >
                      {MODEL_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
              ))}
            </div>
            {/* Traffic validation */}
            <div className={`mt-2 text-xs flex items-center gap-1 ${trafficError ? 'text-red-500' : 'text-green-500'}`}>
              {trafficError ? (
                <>
                  <AlertCircle className="h-3 w-3" />
                  Traffic must total 100% (currently {totalTraffic}%)
                </>
              ) : (
                <>
                  <CheckCircle className="h-3 w-3" />
                  Traffic allocation is valid
                </>
              )}
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-200">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded-lg"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={
                !name.trim() ||
                trafficError ||
                (targetMode === 'workflows' && selectedWorkflowIds.length === 0) ||
                (targetMode === 'task_type' && !taskType.trim())
              }
              className="px-4 py-2 text-sm font-medium text-white bg-purple-600 hover:bg-purple-700 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Create Experiment
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export function ABTestingPage() {
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [activeTab, setActiveTab] = useState<TabType>('all')
  const queryClient = useQueryClient()

  const { data: experiments, isLoading } = useQuery({
    queryKey: ['experiments'],
    queryFn: () => api.getExperiments(),
  })

  const filteredExperiments = useMemo(() => {
    if (!experiments) return []
    if (activeTab === 'all') return experiments
    return experiments.filter((e) => e.status === activeTab)
  }, [experiments, activeTab])

  const createMutation = useMutation({
    mutationFn: (data: { name: string; description: string; variants: Array<{ name: string; traffic_percentage: number }> }) =>
      api.createExperiment(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['experiments'] })
      setIsCreateModalOpen(false)
    },
  })

  const pauseMutation = useMutation({
    mutationFn: (id: string) => api.pauseExperiment(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['experiments'] }),
  })

  const startMutation = useMutation({
    mutationFn: (id: string) => api.startExperiment(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['experiments'] }),
  })

  const completeMutation = useMutation({
    mutationFn: (id: string) => api.completeExperiment(id, true),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['experiments'] }),
  })

  // Check if feature is gated (must be before any early return to satisfy Rules of Hooks)
  const { data: orgPlan } = useQuery({
    queryKey: ['orgPlan'],
    queryFn: () => api.getOrgPlan(),
    staleTime: 60_000,
  })
  const isFeatureGated = orgPlan && !orgPlan.enabled_features.includes('ab_testing')

  const handleDuplicate = (id: string) => {
    // Would duplicate the experiment configuration
    console.log('Duplicating experiment:', id)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Activity className="h-12 w-12 mx-auto mb-3 text-purple-600 animate-pulse" />
          <p className="text-gray-600">Loading experiments...</p>
        </div>
      </div>
    )
  }

  // Stats
  const stats = {
    total: experiments?.length || 0,
    running: experiments?.filter((e) => e.status === 'running').length || 0,
    completed: experiments?.filter((e) => e.status === 'completed').length || 0,
    draft: experiments?.filter((e) => e.status === 'draft').length || 0,
    paused: experiments?.filter((e) => e.status === 'paused').length || 0,
    significantCount: experiments?.filter((e) => e.significanceLevel >= 0.95).length || 0,
    totalRequests: experiments?.reduce((sum, e) =>
      sum + e.variants.reduce((vSum, v) => vSum + v.totalRequests, 0), 0
    ) || 0,
  }

  const tabs: { id: TabType; label: string; count: number }[] = [
    { id: 'all', label: 'All', count: stats.total },
    { id: 'running', label: 'Running', count: stats.running },
    { id: 'completed', label: 'Completed', count: stats.completed },
    { id: 'draft', label: 'Draft', count: stats.draft },
  ]

  return (
    <div className="space-y-6">
      {isFeatureGated && <UpgradeBanner feature="A/B Testing" />}
      {/* Create Experiment Modal */}
      <CreateExperimentModal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        onCreate={(data) => createMutation.mutate(data)}
      />

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <GitBranch className="h-7 w-7 text-purple-600" />
            A/B Testing
          </h1>
          <p className="text-gray-600 mt-1">
            Run experiments to optimize LLM configurations and prompts
          </p>
        </div>
        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700 transition-colors"
        >
          <Plus className="h-4 w-4" />
          New Experiment
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Running</p>
              <p className="text-2xl font-bold text-blue-600">{stats.running}</p>
            </div>
            <div className="p-2 bg-blue-100 rounded-lg">
              <Play className="h-5 w-5 text-blue-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Completed</p>
              <p className="text-2xl font-bold text-green-600">{stats.completed}</p>
            </div>
            <div className="p-2 bg-green-100 rounded-lg">
              <CheckCircle className="h-5 w-5 text-green-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Significant</p>
              <p className="text-2xl font-bold text-purple-600">{stats.significantCount}</p>
            </div>
            <div className="p-2 bg-purple-100 rounded-lg">
              <BarChart3 className="h-5 w-5 text-purple-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Requests</p>
              <p className="text-2xl font-bold text-gray-900">{stats.totalRequests.toLocaleString()}</p>
            </div>
            <div className="p-2 bg-gray-100 rounded-lg">
              <Zap className="h-5 w-5 text-gray-600" />
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
            </div>
            <div className="p-2 bg-gray-100 rounded-lg">
              <GitBranch className="h-5 w-5 text-gray-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-purple-600 text-purple-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
              }`}
            >
              {tab.label}
              <span className={`px-2 py-0.5 rounded-full text-xs ${
                activeTab === tab.id ? 'bg-purple-100 text-purple-600' : 'bg-gray-100 text-gray-500'
              }`}>
                {tab.count}
              </span>
            </button>
          ))}
        </nav>
      </div>

      {/* Experiments List */}
      <div className="space-y-4">
        {filteredExperiments.length === 0 ? (
          <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
            <GitBranch className="h-12 w-12 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500 mb-2">No experiments found</p>
            <p className="text-sm text-gray-400">
              {activeTab === 'all'
                ? 'Create your first experiment to start testing'
                : `No ${activeTab} experiments`}
            </p>
            {activeTab === 'all' && (
              <button
                onClick={() => setIsCreateModalOpen(true)}
                className="mt-4 px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-700"
              >
                Create Experiment
              </button>
            )}
          </div>
        ) : (
          filteredExperiments.map((experiment) => (
            <ExperimentCard
              key={experiment.id}
              experiment={experiment}
              onPause={(id) => pauseMutation.mutate(id)}
              onResume={(id) => startMutation.mutate(id)}
              onComplete={(id) => completeMutation.mutate(id)}
              onDuplicate={handleDuplicate}
            />
          ))
        )}
      </div>

      {/* Help Section - How It Works */}
      <div className="bg-gradient-to-r from-purple-50 to-indigo-50 rounded-lg p-6 border border-purple-100">
        <div className="flex items-start gap-4">
          <div className="p-2 bg-purple-100 rounded-lg">
            <Settings className="h-5 w-5 text-purple-600" />
          </div>
          <div className="flex-1">
            <h3 className="font-semibold text-purple-900 mb-3">How A/B Testing Works</h3>
            <div className="grid md:grid-cols-2 gap-6">
              <div>
                <h4 className="font-medium text-purple-800 mb-2">Creating Experiments</h4>
                <ul className="text-sm text-purple-700 space-y-2">
                  <li className="flex items-start gap-2">
                    <CheckCircle className="h-4 w-4 text-purple-500 mt-0.5 flex-shrink-0" />
                    <span><strong>Target a specific workflow</strong> to ensure the experiment only affects that workflow's LLM calls</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="h-4 w-4 text-purple-500 mt-0.5 flex-shrink-0" />
                    <span><strong>Define variants</strong> with different models (GPT-4o vs Claude), prompts, or temperature settings</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle className="h-4 w-4 text-purple-500 mt-0.5 flex-shrink-0" />
                    <span><strong>Traffic split</strong> determines what percentage of requests go to each variant</span>
                  </li>
                </ul>
              </div>
              <div>
                <h4 className="font-medium text-purple-800 mb-2">Understanding Metrics</h4>
                <ul className="text-sm text-purple-700 space-y-2">
                  <li className="flex items-start gap-2">
                    <BarChart3 className="h-4 w-4 text-purple-500 mt-0.5 flex-shrink-0" />
                    <span><strong>Conversion Rate:</strong> % of successful LLM calls (no errors, valid output)</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <Clock className="h-4 w-4 text-purple-500 mt-0.5 flex-shrink-0" />
                    <span><strong>Avg Latency:</strong> Response time - lower is better for user experience</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <DollarSign className="h-4 w-4 text-purple-500 mt-0.5 flex-shrink-0" />
                    <span><strong>Cost/1k:</strong> Average cost per 1000 requests - helps optimize spend</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <Target className="h-4 w-4 text-purple-500 mt-0.5 flex-shrink-0" />
                    <span><strong>95% Significance:</strong> Wait for this before declaring a winner (reduces false positives)</span>
                  </li>
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ABTestingPage
