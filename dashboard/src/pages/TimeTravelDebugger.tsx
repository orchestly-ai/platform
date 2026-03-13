/**
 * TimeTravelDebugger Page - Debug workflow executions with time-travel
 *
 * Features like the public demo:
 * - Interactive timeline with clickable steps
 * - Step-by-step navigation
 * - State inspection with JSON viewer
 * - Compare mode for side-by-side comparison
 * - Replay from any point with modified input
 * - Export execution trace
 */

import { useState, useCallback, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import type { ExecutionStep } from '@/types/llm'
import { WorkflowVisualization } from '@/components/WorkflowVisualization'
import { UpgradeBanner } from '@/components/UpgradeBanner'
import {
  Bug,
  Activity,
  CheckCircle,
  XCircle,
  ChevronRight,
  ChevronLeft,
  Play,
  RotateCcw,
  DollarSign,
  Clock,
  Search,
  RefreshCw,
  AlertCircle,
  Download,
  Sparkles,
  GitBranch,
  Loader2,
  Lock,
} from 'lucide-react'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export function TimeTravelDebuggerPage() {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<'all' | 'completed' | 'failed' | 'running'>('all')
  const [selectedExecutionId, setSelectedExecutionId] = useState<string | null>(null)
  const [currentStep, setCurrentStep] = useState(0)
  const [isReplaying, setIsReplaying] = useState(false)
  const [compareMode, setCompareMode] = useState(false)
  const [compareStep, setCompareStep] = useState<number | null>(null)
  const [showModifyModal, setShowModifyModal] = useState(false)
  const [showWorkflowView, setShowWorkflowView] = useState(true)
  const [modifiedInput, setModifiedInput] = useState('')
  const [isReExecuting, setIsReExecuting] = useState(false)
  const [reExecutionStatus, setReExecutionStatus] = useState<string | null>(null)
  const [reExecutionSteps, setReExecutionSteps] = useState<ExecutionStep[]>([])
  const wsRef = useRef<WebSocket | null>(null)

  const { data: executions, isLoading } = useQuery({
    queryKey: ['executions'],
    queryFn: () => api.getExecutions(),
  })

  // Check if advanced time-travel features require enterprise license
  const { data: orgPlan } = useQuery({
    queryKey: ['orgPlan'],
    queryFn: () => api.getOrgPlan(),
    staleTime: 60_000,
  })
  const isAdvancedGated = orgPlan && !orgPlan.enabled_features.includes('time_travel')

  // Fetch workflow definition for selected execution
  const selectedExecution = executions?.find((e) => e.id === selectedExecutionId)
  const { data: workflowData } = useQuery({
    queryKey: ['workflow', selectedExecution?.workflowId],
    queryFn: () => selectedExecution?.workflowId ? api.getWorkflowById(selectedExecution.workflowId) : null,
    enabled: !!selectedExecution?.workflowId,
  })

  const filteredExecutions = executions?.filter((exec) => {
    const matchesStatus = statusFilter === 'all' || exec.status === statusFilter
    const matchesSearch = exec.workflowName.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         exec.id.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesStatus && matchesSearch
  }) || []

  // Use execution steps from backend, or empty array if none
  const executionSteps: ExecutionStep[] = selectedExecution?.nodeExecutions || []

  const step = executionSteps[currentStep]
  const compareStepData = compareStep !== null ? executionSteps[compareStep] : null

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle size={14} className="text-green-500" />
      case 'failed': return <XCircle size={14} className="text-red-500" />
      case 'running': return <RefreshCw size={14} className="text-blue-500 animate-spin" />
      default: return <Clock size={14} className="text-gray-400" />
    }
  }

  const goToStep = (stepIndex: number) => {
    if (stepIndex >= 0 && stepIndex < executionSteps.length) {
      setCurrentStep(stepIndex)
    }
  }

  const replay = () => {
    setIsReplaying(true)
    setCurrentStep(0)

    let step = 0
    const interval = setInterval(() => {
      step++
      if (step >= executionSteps.length) {
        clearInterval(interval)
        setIsReplaying(false)
      } else {
        setCurrentStep(step)
      }
    }, 800)
  }

  const replayFromHere = () => {
    setIsReplaying(true)
    const startStep = currentStep

    let step = startStep
    const interval = setInterval(() => {
      step++
      if (step >= executionSteps.length) {
        clearInterval(interval)
        setIsReplaying(false)
      } else {
        setCurrentStep(step)
      }
    }, 800)
  }

  // Re-execute workflow with modified input
  const executeWithModifiedInput = useCallback(async () => {
    if (!workflowData || !selectedExecution) {
      alert('No workflow data available')
      return
    }

    // Parse the modified input
    let inputData: Record<string, unknown>
    try {
      inputData = JSON.parse(modifiedInput)
    } catch (e) {
      alert('Invalid JSON input. Please check your input format.')
      return
    }

    setIsReExecuting(true)
    setReExecutionStatus('Connecting...')
    setReExecutionSteps([])

    // Connect to WebSocket for temp workflow execution
    const wsUrl = `${API_BASE_URL.replace('http', 'ws')}/api/workflows/temp/execute`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws

    ws.onopen = () => {
      setReExecutionStatus('Starting execution...')
      // Send the workflow with modified input
      ws.send(JSON.stringify({
        action: 'start',
        workflow: {
          nodes: workflowData.nodes,
          edges: workflowData.edges,
        },
        inputData,
      }))
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.event_type === 'node_started') {
          setReExecutionStatus(`Running: ${data.message || data.node_id}`)
          setReExecutionSteps(prev => [...prev, {
            id: prev.length,
            name: data.message || data.node_id,
            timestamp: new Date().toISOString(),
            duration: '-',
            status: 'running',
            state: { input: JSON.stringify(data.data) }
          }])
        } else if (data.event_type === 'node_completed') {
          setReExecutionStatus(`Completed: ${data.message || data.node_id}`)

          // 🔍 NODE OUTPUT CONSOLE LOGGING - for faster development debugging
          if (data.data) {
            const nodeLabel = data.message || data.node_id
            console.group(`📦 Node Output: ${nodeLabel}`)
            console.log('%cNode ID:', 'font-weight: bold; color: #6366f1', data.node_id)
            if (data.cost != null) {
              console.log('%cCost:', 'font-weight: bold; color: #f59e0b', `$${data.cost.toFixed(4)}`)
            }
            if (data.execution_time != null) {
              console.log('%cDuration:', 'font-weight: bold; color: #3b82f6', `${data.execution_time}ms`)
            }
            console.log('%cOutput Data:', 'font-weight: bold; color: #8b5cf6')
            console.dir(data.data, { depth: null })
            console.groupEnd()
          }

          setReExecutionSteps(prev => {
            const updated = [...prev]
            const lastIdx = updated.length - 1
            if (lastIdx >= 0) {
              updated[lastIdx] = {
                ...updated[lastIdx],
                status: 'completed',
                duration: data.execution_time ? `${data.execution_time}ms` : '-',
                state: {
                  ...updated[lastIdx].state,
                  output: JSON.stringify(data.data),
                  model: data.actual_model,
                  cost: data.cost,
                }
              }
            }
            return updated
          })
        } else if (data.event_type === 'execution_completed' || data.event_type === 'workflow_completed') {
          setReExecutionStatus('Workflow completed successfully!')
          setIsReExecuting(false)
          // Refresh executions list
          queryClient.invalidateQueries({ queryKey: ['executions'] })
        } else if (data.event_type === 'execution_failed' || data.event_type === 'error') {
          setReExecutionStatus(`Error: ${data.message}`)
          setIsReExecuting(false)
        }
      } catch (e) {
        console.error('Failed to parse WebSocket message:', e)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
      setReExecutionStatus('Connection error')
      setIsReExecuting(false)
    }

    ws.onclose = () => {
      // Only show error if we didn't complete successfully
      if (isReExecuting && !reExecutionStatus?.includes('completed')) {
        // Check if we have steps - if so, likely completed but missed the event
        if (reExecutionSteps.length > 0) {
          setReExecutionStatus('Workflow completed successfully!')
          queryClient.invalidateQueries({ queryKey: ['executions'] })
        } else {
          setReExecutionStatus('Connection closed unexpectedly')
        }
        setIsReExecuting(false)
      }
    }
  }, [workflowData, selectedExecution, modifiedInput, queryClient, isReExecuting, reExecutionStatus, reExecutionSteps])

  // Initialize modified input when opening modal
  const openModifyModal = useCallback(() => {
    // Get the original input from the execution
    const originalInput = selectedExecution?.nodeExecutions?.[0]?.state?.input
    try {
      // Try to parse and re-format the JSON for better display
      const parsed = originalInput ? JSON.parse(originalInput) : {}
      setModifiedInput(JSON.stringify(parsed, null, 2))
    } catch {
      setModifiedInput(originalInput || '{}')
    }
    setShowModifyModal(true)
    setReExecutionSteps([])
    setReExecutionStatus(null)
  }, [selectedExecution])

  const toggleCompare = () => {
    if (compareMode) {
      setCompareMode(false)
      setCompareStep(null)
    } else {
      setCompareMode(true)
      setCompareStep(currentStep > 0 ? currentStep - 1 : currentStep + 1)
    }
  }

  const exportExecution = () => {
    if (!selectedExecution) return

    const exportData = {
      executionId: selectedExecution.id,
      workflowId: selectedExecution.workflowId,
      workflowName: selectedExecution.workflowName,
      timestamp: selectedExecution.startTime,
      steps: executionSteps,
      summary: {
        status: selectedExecution.status,
        totalDuration: selectedExecution.endTime
          ? `${Math.round((new Date(selectedExecution.endTime).getTime() - new Date(selectedExecution.startTime).getTime()) / 1000)}s`
          : 'Running...',
        totalCost: selectedExecution.totalCost,
        error: selectedExecution.error,
      }
    }
    const blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `execution_trace_${selectedExecution.id.slice(0, 8)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Activity className="h-12 w-12 mx-auto mb-3 text-blue-600 animate-pulse" />
          <p className="text-gray-600">Loading executions...</p>
        </div>
      </div>
    )
  }

  const stats = {
    total: executions?.length || 0,
    completed: executions?.filter((e) => e.status === 'completed').length || 0,
    failed: executions?.filter((e) => e.status === 'failed').length || 0,
    totalCost: executions?.reduce((sum, e) => sum + e.totalCost, 0) || 0,
  }

  return (
    <div className="flex flex-col h-[calc(100vh-140px)]">
      {/* Page Header */}
      <div className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
              <Bug className="h-7 w-7 text-purple-600" />
              Time-Travel Debugger
            </h1>
            <p className="text-gray-600 mt-1">
              Replay, inspect, and debug workflow executions step by step
            </p>
          </div>
          <button className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
            <RefreshCw className="h-4 w-4" />
            Auto-refresh
          </button>
        </div>

        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mt-6">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-gray-500 mb-1">
              <Activity className="h-4 w-4" />
              <span className="text-sm">Total Executions</span>
            </div>
            <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-green-500 mb-1">
              <CheckCircle className="h-4 w-4" />
              <span className="text-sm">Completed</span>
            </div>
            <p className="text-2xl font-bold text-green-600">{stats.completed}</p>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-red-500 mb-1">
              <XCircle className="h-4 w-4" />
              <span className="text-sm">Failed</span>
            </div>
            <p className="text-2xl font-bold text-red-600">{stats.failed}</p>
          </div>
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center gap-2 text-purple-500 mb-1">
              <DollarSign className="h-4 w-4" />
              <span className="text-sm">Total Cost</span>
            </div>
            <p className="text-2xl font-bold text-purple-600">
              ${stats.totalCost.toFixed(2)}
            </p>
          </div>
        </div>
        {isAdvancedGated && <UpgradeBanner feature="Advanced Time-Travel Debugging (comparisons, replay, analysis)" />}
      </div>

      {/* Main Content - Split View */}
      <div className="grid grid-cols-[300px_1fr] gap-5 flex-1 min-h-0">
        {/* Executions List */}
        <div className="bg-white rounded-lg border border-gray-200 flex flex-col overflow-hidden">
          <div className="p-4 border-b border-gray-200">
            {/* Search */}
            <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 mb-3">
              <Search size={16} className="text-gray-400" />
              <input
                type="text"
                placeholder="Search..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1 border-none bg-transparent outline-none text-sm"
              />
            </div>

            {/* Status Filters */}
            <div className="flex gap-2">
              {(['all', 'completed', 'failed', 'running'] as const).map((status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`px-2 py-1 text-xs font-medium rounded transition-colors capitalize ${
                    statusFilter === status
                      ? 'bg-blue-50 text-blue-600'
                      : 'text-gray-600 hover:bg-gray-50'
                  }`}
                >
                  {status}
                </button>
              ))}
            </div>
          </div>

          {/* Execution List */}
          <div className="flex-1 overflow-y-auto">
            {filteredExecutions.map((exec) => (
              <div
                key={exec.id}
                onClick={() => {
                  setSelectedExecutionId(exec.id)
                  setCurrentStep(0)
                  setCompareMode(false)
                }}
                className={`flex items-center gap-2 p-3 border-b border-gray-100 cursor-pointer transition-colors ${
                  selectedExecutionId === exec.id
                    ? 'bg-blue-50 border-l-4 border-l-blue-500'
                    : 'hover:bg-gray-50'
                }`}
              >
                {getStatusIcon(exec.status)}
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm text-gray-900 truncate">{exec.workflowName}</div>
                  <div className="text-xs text-gray-500 mt-0.5 truncate">
                    {new Date(exec.startTime).toLocaleTimeString()}
                  </div>
                </div>
                <ChevronRight size={14} className="text-gray-400" />
              </div>
            ))}

            {filteredExecutions.length === 0 && (
              <div className="flex flex-col items-center justify-center h-full text-gray-400 p-6 text-center">
                <Activity className="h-10 w-10 mb-2 opacity-30" />
                <p className="text-sm font-medium">No executions found</p>
              </div>
            )}
          </div>
        </div>

        {/* Time-Travel Debugger */}
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden flex flex-col">
          {selectedExecution && executionSteps.length > 0 ? (
            <>
              {/* Header */}
              <div className="flex items-center justify-between p-4 border-b border-gray-200">
                <div>
                  <h2 className="text-lg font-semibold">{selectedExecution.workflowName}</h2>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-gray-500">{selectedExecution.id.slice(0, 8)}...</span>
                    <span className="flex items-center gap-1 text-xs px-2 py-0.5 bg-blue-50 text-blue-600 rounded">
                      <Sparkles size={10} />
                      Time-Travel Mode
                    </span>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={toggleCompare}
                    disabled={!!isAdvancedGated}
                    title={isAdvancedGated ? 'Requires Enterprise license' : undefined}
                    className={`px-3 py-1.5 text-sm font-medium rounded transition-colors ${
                      isAdvancedGated ? 'bg-gray-50 text-gray-400 cursor-not-allowed border' :
                      compareMode ? 'bg-purple-50 text-purple-600 border-purple-200 border' : 'bg-gray-50 text-gray-600 hover:bg-gray-100 border'
                    }`}
                  >
                    {isAdvancedGated && <Lock size={12} className="inline mr-1" />}
                    Compare States
                  </button>
                  <button
                    onClick={replay}
                    disabled={isReplaying || !!isAdvancedGated}
                    title={isAdvancedGated ? 'Requires Enterprise license' : undefined}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-gray-50 text-gray-600 hover:bg-gray-100 border rounded transition-colors disabled:opacity-50"
                  >
                    {isAdvancedGated ? <Lock size={14} /> : <RotateCcw size={14} />}
                    Replay
                  </button>
                  <button
                    onClick={exportExecution}
                    className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium bg-gray-50 text-gray-600 hover:bg-gray-100 border rounded transition-colors"
                  >
                    <Download size={14} />
                    Export
                  </button>
                </div>
              </div>

              {/* Workflow Visualization */}
              {workflowData && (
                <div className="border-b border-gray-200">
                  <div
                    className="flex items-center justify-between p-3 bg-gray-50 cursor-pointer hover:bg-gray-100 transition-colors"
                    onClick={() => setShowWorkflowView(!showWorkflowView)}
                  >
                    <div className="flex items-center gap-2">
                      <GitBranch size={14} className="text-gray-600" />
                      <span className="text-xs font-semibold text-gray-500">WORKFLOW STRUCTURE</span>
                    </div>
                    <ChevronRight
                      size={16}
                      className={`text-gray-400 transition-transform ${showWorkflowView ? 'rotate-90' : ''}`}
                    />
                  </div>
                  {showWorkflowView && (
                    <div className="h-64 bg-white">
                      <WorkflowVisualization
                        nodes={workflowData.nodes || []}
                        edges={workflowData.edges || []}
                        currentStep={step}
                        completedSteps={executionSteps.slice(0, currentStep)}
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Timeline */}
              <div className="p-4 border-b border-gray-200 bg-gray-50">
                <div className="text-xs font-semibold text-gray-500 mb-3">EXECUTION TIMELINE</div>
                <div className="flex gap-2">
                  {executionSteps.map((s, index) => (
                    <div
                      key={s.id}
                      onClick={() => goToStep(index)}
                      className={`flex-1 relative cursor-pointer transition-all ${
                        index === currentStep ? 'scale-105' : ''
                      }`}
                    >
                      <div className={`p-3 rounded-lg border-2 transition-all ${
                        index === currentStep
                          ? 'bg-blue-50 border-blue-500 shadow-sm'
                          : index < currentStep
                          ? 'bg-green-50 border-green-200'
                          : 'bg-white border-gray-200'
                      }`}>
                        <div className="flex items-center gap-2 mb-1">
                          {s.status === 'completed' && <CheckCircle size={12} className="text-green-600" />}
                          {s.status === 'failed' && <AlertCircle size={12} className="text-red-600" />}
                          {s.status === 'pending' && <Clock size={12} className="text-gray-400" />}
                          <span className="text-xs font-medium truncate">{s.name}</span>
                        </div>
                        <div className="text-xs text-gray-500 truncate">{s.timestamp.split('.')[0]}</div>
                      </div>
                      {index === currentStep && (
                        <div className="absolute -bottom-5 left-1/2 transform -translate-x-1/2 text-xs font-medium text-blue-600 whitespace-nowrap">
                          Currently viewing
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>

              {/* Navigation */}
              <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-white">
                <button
                  onClick={() => goToStep(currentStep - 1)}
                  disabled={currentStep === 0 || isReplaying}
                  className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed rounded transition-colors"
                >
                  <ChevronLeft size={16} />
                  <span className="text-sm font-medium">Previous</span>
                </button>
                <div className="text-sm font-medium text-gray-700">
                  Step {currentStep + 1} of {executionSteps.length}
                </div>
                <button
                  onClick={() => goToStep(currentStep + 1)}
                  disabled={currentStep === executionSteps.length - 1 || isReplaying}
                  className="flex items-center gap-2 px-4 py-2 bg-gray-100 hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed rounded transition-colors"
                >
                  <span className="text-sm font-medium">Next</span>
                  <ChevronRight size={16} />
                </button>
              </div>

              {/* State Display */}
              <div className="flex-1 overflow-auto p-4">
                <div className={`grid ${compareMode ? 'grid-cols-2' : 'grid-cols-1'} gap-4 h-full`}>
                  {/* Main State Panel */}
                  <div className="flex flex-col h-full">
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-sm font-semibold">State at Step {currentStep + 1}: "{step.name}"</h3>
                      <div className="flex items-center gap-3 text-xs text-gray-500">
                        <span className="flex items-center gap-1">
                          <Clock size={12} />
                          {step.timestamp}
                        </span>
                        <span className="font-medium text-blue-600">{step.duration}</span>
                      </div>
                    </div>
                    <div className="flex-1 bg-gray-900 text-gray-100 rounded-lg p-4 overflow-auto font-mono text-xs">
                      <pre className="whitespace-pre-wrap">
                        {JSON.stringify(
                          {
                            step: step.name,
                            timestamp: step.timestamp,
                            duration: step.duration,
                            status: step.status,
                            ...step.state,
                          },
                          null,
                          2
                        )}
                      </pre>
                    </div>
                    <div className="flex gap-2 mt-3">
                      <button
                        onClick={replayFromHere}
                        disabled={isReplaying || currentStep === executionSteps.length - 1 || !!isAdvancedGated}
                        title={isAdvancedGated ? 'Requires Enterprise license' : undefined}
                        className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded transition-colors text-sm font-medium"
                      >
                        {isAdvancedGated ? <Lock size={14} /> : <Play size={14} />}
                        Replay from here
                      </button>
                      <button
                        onClick={openModifyModal}
                        disabled={!!isAdvancedGated}
                        title={isAdvancedGated ? 'Requires Enterprise license' : undefined}
                        className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors text-sm font-medium disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isAdvancedGated && <Lock size={12} className="inline mr-1" />}
                        Modify & Retry
                      </button>
                    </div>
                  </div>

                  {/* Compare Panel */}
                  {compareMode && compareStepData && (
                    <div className="flex flex-col h-full">
                      <div className="flex items-center justify-between mb-3">
                        <h3 className="text-sm font-semibold">Compare: Step {compareStep! + 1}</h3>
                        <select
                          value={compareStep!}
                          onChange={(e) => setCompareStep(Number(e.target.value))}
                          className="text-xs border border-gray-200 rounded px-2 py-1"
                        >
                          {executionSteps.map((s, index) => (
                            <option key={s.id} value={index} disabled={index === currentStep}>
                              Step {index + 1}: {s.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="flex-1 bg-gray-900 text-gray-100 rounded-lg p-4 overflow-auto font-mono text-xs">
                        <pre className="whitespace-pre-wrap">
                          {JSON.stringify(
                            {
                              step: compareStepData.name,
                              timestamp: compareStepData.timestamp,
                              duration: compareStepData.duration,
                              status: compareStepData.status,
                              ...compareStepData.state,
                            },
                            null,
                            2
                          )}
                        </pre>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Summary Stats */}
              {selectedExecution.endTime && (
                <div className="grid grid-cols-4 gap-4 p-4 border-t border-gray-200 bg-gray-50">
                  <div className="text-center">
                    <div className="text-xs text-gray-500 mb-1">Total Duration</div>
                    <div className="text-sm font-bold text-gray-900">
                      {Math.round((new Date(selectedExecution.endTime).getTime() - new Date(selectedExecution.startTime).getTime()) / 1000)}s
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-gray-500 mb-1">Total Cost</div>
                    <div className="text-sm font-bold text-gray-900">${selectedExecution.totalCost.toFixed(4)}</div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-gray-500 mb-1">Status</div>
                    <div className={`text-sm font-bold ${
                      selectedExecution.status === 'completed' ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {selectedExecution.status}
                    </div>
                  </div>
                  <div className="text-center">
                    <div className="text-xs text-gray-500 mb-1">Steps</div>
                    <div className="text-sm font-bold text-gray-900">{executionSteps.length}</div>
                  </div>
                </div>
              )}

              {/* Modify & Retry Modal */}
              {showModifyModal && (
                <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50" onClick={() => !isReExecuting && setShowModifyModal(false)}>
                  <div className="bg-white rounded-lg p-6 max-w-2xl w-full mx-4 max-h-[90vh] overflow-auto" onClick={(e) => e.stopPropagation()}>
                    <h3 className="text-lg font-semibold mb-2">Modify & Retry Workflow</h3>
                    <p className="text-sm text-gray-600 mb-4">
                      Modify the input data and re-execute the entire workflow with new values.
                    </p>

                    <div className="mb-4">
                      <label className="block text-sm font-medium text-gray-700 mb-2">Input Data (JSON)</label>
                      <textarea
                        className="w-full border border-gray-200 rounded px-3 py-2 text-sm font-mono bg-gray-50"
                        value={modifiedInput}
                        onChange={(e) => setModifiedInput(e.target.value)}
                        rows={6}
                        disabled={isReExecuting}
                        placeholder='{"ticket_id": "123", "title": "Server down", "description": "Production server not responding"}'
                      />
                    </div>

                    {/* Re-execution status and progress */}
                    {reExecutionStatus && (
                      <div className={`mb-4 p-3 rounded-lg ${
                        reExecutionStatus.includes('Error') ? 'bg-red-50 text-red-700' :
                        reExecutionStatus.includes('completed') ? 'bg-green-50 text-green-700' :
                        'bg-blue-50 text-blue-700'
                      }`}>
                        <div className="flex items-center gap-2">
                          {isReExecuting && <Loader2 size={14} className="animate-spin" />}
                          {reExecutionStatus.includes('completed') && <CheckCircle size={14} />}
                          {reExecutionStatus.includes('Error') && <XCircle size={14} />}
                          <span className="text-sm font-medium">{reExecutionStatus}</span>
                        </div>
                      </div>
                    )}

                    {/* Live execution steps */}
                    {reExecutionSteps.length > 0 && (
                      <div className="mb-4">
                        <label className="block text-sm font-medium text-gray-700 mb-2">Execution Progress</label>
                        <div className="border border-gray-200 rounded-lg overflow-hidden max-h-48 overflow-y-auto">
                          {reExecutionSteps.map((execStep, idx) => (
                            <div
                              key={idx}
                              className={`flex items-center gap-2 px-3 py-2 text-sm border-b border-gray-100 last:border-b-0 ${
                                execStep.status === 'completed' ? 'bg-green-50' :
                                execStep.status === 'running' ? 'bg-blue-50' :
                                execStep.status === 'failed' ? 'bg-red-50' : ''
                              }`}
                            >
                              {execStep.status === 'running' && <Loader2 size={12} className="animate-spin text-blue-500" />}
                              {execStep.status === 'completed' && <CheckCircle size={12} className="text-green-500" />}
                              {execStep.status === 'failed' && <XCircle size={12} className="text-red-500" />}
                              <span className="flex-1">{execStep.name}</span>
                              <span className="text-gray-500">{execStep.duration}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => {
                          setShowModifyModal(false)
                          setReExecutionStatus(null)
                          setReExecutionSteps([])
                          // Close WebSocket if open
                          if (wsRef.current) {
                            wsRef.current.close()
                            wsRef.current = null
                          }
                        }}
                        disabled={isReExecuting}
                        className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors text-sm font-medium disabled:opacity-50"
                      >
                        {reExecutionStatus?.includes('completed') ? 'Close' : 'Cancel'}
                      </button>
                      {!reExecutionStatus?.includes('completed') && (
                        <button
                          onClick={executeWithModifiedInput}
                          disabled={isReExecuting}
                          className="flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded transition-colors text-sm font-medium disabled:opacity-50"
                        >
                          {isReExecuting ? (
                            <>
                              <Loader2 size={14} className="animate-spin" />
                              Executing...
                            </>
                          ) : (
                            <>
                              <Play size={14} />
                              Execute Workflow
                            </>
                          )}
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 p-10 text-center">
              <Play size={48} className="mb-4 opacity-30" />
              <h3 className="text-lg font-semibold mb-2">Select an execution</h3>
              <p className="text-sm">Click on an execution from the list to start time-travel debugging</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default TimeTravelDebuggerPage
