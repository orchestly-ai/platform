/**
 * Runs Page - Unified workflow execution monitoring and debugging
 *
 * Combines executions monitoring with time-travel debugging:
 * - Simple View: Quick overview of all runs with status and metrics
 * - Detailed View: Interactive timeline, step-by-step debugging, state inspection
 * - Compare mode for side-by-side comparison
 * - Replay from any point with modified input
 * - Export execution trace
 */

import { useState, useCallback, useRef } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import type { ExecutionStep } from '@/types/llm'
import { WorkflowVisualization } from '@/components/WorkflowVisualization'
import {
  Play,
  Activity,
  CheckCircle,
  XCircle,
  ChevronRight,
  ChevronLeft,
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
  ArrowLeft,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

// Track feedback given for each assignment
interface FeedbackState {
  [assignmentId: number]: 'positive' | 'negative' | 'pending';
}

export function RunsPage() {
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
  // Default canvas height: ~2/3 of usable vertical space
  const [canvasHeight, setCanvasHeight] = useState(() =>
    Math.round((window.innerHeight - 260) * 0.65)
  )
  const isDraggingRef = useRef(false)

  // Resizable split pane drag handler
  const handleDragStart = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDraggingRef.current = true
    const startY = e.clientY
    const startHeight = canvasHeight

    const onMouseMove = (e: MouseEvent) => {
      if (!isDraggingRef.current) return
      const delta = e.clientY - startY
      const newHeight = Math.max(100, Math.min(startHeight + delta, 600))
      setCanvasHeight(newHeight)
    }

    const onMouseUp = () => {
      isDraggingRef.current = false
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }

    document.body.style.cursor = 'row-resize'
    document.body.style.userSelect = 'none'
    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }, [canvasHeight])
  const [modifiedInput, setModifiedInput] = useState('')
  const [isReExecuting, setIsReExecuting] = useState(false)
  const [reExecutionStatus, setReExecutionStatus] = useState<string | null>(null)
  const [reExecutionSteps, setReExecutionSteps] = useState<ExecutionStep[]>([])
  const wsRef = useRef<WebSocket | null>(null)
  const [feedbackState, setFeedbackState] = useState<FeedbackState>({})
  const [sortField, setSortField] = useState<'time' | 'status' | 'cost' | 'duration'>('time')
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc')

  const toggleSort = (field: 'time' | 'status' | 'cost' | 'duration') => {
    if (sortField === field) {
      setSortDirection(d => d === 'desc' ? 'asc' : 'desc')
    } else {
      setSortField(field)
      setSortDirection('desc')
    }
  }

  // Submit feedback for A/B testing
  const submitFeedback = async (assignmentId: number, positive: boolean) => {
    setFeedbackState(prev => ({ ...prev, [assignmentId]: 'pending' }));

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/experiments/assignments/${assignmentId}/feedback`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            assignment_id: assignmentId,
            positive: positive,
            rating: positive ? 5 : 1,
          }),
        }
      );

      if (response.ok) {
        setFeedbackState(prev => ({ ...prev, [assignmentId]: positive ? 'positive' : 'negative' }));
      } else {
        // Reset on error
        setFeedbackState(prev => {
          const newState = { ...prev };
          delete newState[assignmentId];
          return newState;
        });
        console.error('Failed to submit feedback');
      }
    } catch (err) {
      console.error('Error submitting feedback:', err);
      setFeedbackState(prev => {
        const newState = { ...prev };
        delete newState[assignmentId];
        return newState;
      });
    }
  };

  const { data: executions, isLoading } = useQuery({
    queryKey: ['executions'],
    queryFn: () => api.getExecutions(),
  })

  // Fetch workflow definition for selected execution
  const selectedExecution = executions?.find((e) => e.id === selectedExecutionId)
  const { data: workflowData } = useQuery({
    queryKey: ['workflow', selectedExecution?.workflowId],
    queryFn: () => selectedExecution?.workflowId ? api.getWorkflowById(selectedExecution.workflowId) : null,
    enabled: !!selectedExecution?.workflowId,
  })

  const filteredExecutions = (executions?.filter((exec) => {
    const matchesStatus = statusFilter === 'all' || exec.status === statusFilter
    const matchesSearch = exec.workflowName.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         exec.id.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesStatus && matchesSearch
  }) || []).sort((a, b) => {
    const dir = sortDirection === 'desc' ? -1 : 1
    switch (sortField) {
      case 'time':
        return dir * (new Date(a.startTime).getTime() - new Date(b.startTime).getTime())
      case 'status':
        return dir * a.status.localeCompare(b.status)
      case 'cost':
        return dir * (a.totalCost - b.totalCost)
      case 'duration': {
        const dA = a.endTime ? new Date(a.endTime).getTime() - new Date(a.startTime).getTime() : 0
        const dB = b.endTime ? new Date(b.endTime).getTime() - new Date(b.startTime).getTime() : 0
        return dir * (dA - dB)
      }
      default:
        return 0
    }
  })

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
    <div className="flex flex-col h-[calc(100vh-100px)]">
      {/* Header — changes based on whether a run is selected */}
      <div className="flex items-center justify-between mb-3">
        {selectedExecutionId && selectedExecution ? (
          /* Detail view header */
          <>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSelectedExecutionId(null)}
                className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs font-medium text-gray-600 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <ArrowLeft className="h-3.5 w-3.5" />
                All Runs
              </button>
              <div className="flex items-center gap-2">
                {getStatusIcon(selectedExecution.status)}
                <h1 className="text-lg font-bold text-gray-900">{selectedExecution.workflowName}</h1>
                <span className="text-xs text-gray-400">{selectedExecution.id.slice(0, 8)}</span>
              </div>
              <span className="flex items-center gap-1 text-[10px] px-1.5 py-0.5 bg-blue-50 text-blue-600 rounded">
                <Sparkles size={8} />
                Time-Travel
              </span>
            </div>
            <div className="flex gap-1.5">
              <button
                onClick={toggleCompare}
                className={`px-2 py-1 text-xs font-medium rounded transition-colors ${
                  compareMode ? 'bg-purple-50 text-purple-600 border-purple-200' : 'bg-gray-50 text-gray-600 hover:bg-gray-100'
                } border`}
              >
                Compare
              </button>
              <button
                onClick={replay}
                disabled={isReplaying}
                className="flex items-center gap-1 px-2 py-1 text-xs font-medium bg-gray-50 text-gray-600 hover:bg-gray-100 border rounded transition-colors disabled:opacity-50"
              >
                <RotateCcw size={12} />
                Replay
              </button>
              <button
                onClick={exportExecution}
                className="flex items-center gap-1 px-2 py-1 text-xs font-medium bg-gray-50 text-gray-600 hover:bg-gray-100 border rounded transition-colors"
              >
                <Download size={12} />
                Export
              </button>
            </div>
          </>
        ) : (
          /* List view header */
          <>
            <div className="flex items-center gap-4">
              <h1 className="text-lg font-bold text-gray-900 flex items-center gap-2 whitespace-nowrap">
                <Play className="h-5 w-5 text-purple-600" />
                Runs
              </h1>
              {/* Inline Stats */}
              <div className="flex items-center gap-3 text-sm">
                <span className="flex items-center gap-1.5 px-2.5 py-1 bg-gray-50 border border-gray-200 rounded-md">
                  <Activity className="h-3.5 w-3.5 text-gray-400" />
                  <span className="font-semibold text-gray-900">{stats.total}</span>
                  <span className="text-gray-400">total</span>
                </span>
                <span className="flex items-center gap-1.5 px-2.5 py-1 bg-green-50 border border-green-200 rounded-md">
                  <CheckCircle className="h-3.5 w-3.5 text-green-500" />
                  <span className="font-semibold text-green-700">{stats.completed}</span>
                </span>
                <span className="flex items-center gap-1.5 px-2.5 py-1 bg-red-50 border border-red-200 rounded-md">
                  <XCircle className="h-3.5 w-3.5 text-red-500" />
                  <span className="font-semibold text-red-700">{stats.failed}</span>
                </span>
                <span className="flex items-center gap-1.5 px-2.5 py-1 bg-purple-50 border border-purple-200 rounded-md">
                  <DollarSign className="h-3.5 w-3.5 text-purple-500" />
                  <span className="font-semibold text-purple-700">${stats.totalCost.toFixed(2)}</span>
                </span>
              </div>
            </div>
            <button className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-white border border-gray-200 rounded-lg hover:bg-gray-50 transition-colors">
              <RefreshCw className="h-3.5 w-3.5" />
              Auto-refresh
            </button>
          </>
        )}
      </div>

      {/* Simple View - Table-like list */}
      {/* List View — shown when no run is selected */}
      {!selectedExecutionId && (
        <div className="bg-white rounded-lg border border-gray-200 flex-1 overflow-hidden flex flex-col">
          {/* Search and Filters */}
          <div className="px-4 py-2.5 border-b border-gray-200 flex items-center gap-3">
            <div className="flex items-center gap-2 bg-gray-50 border border-gray-200 rounded-lg px-3 py-1.5 flex-1 max-w-sm">
              <Search size={14} className="text-gray-400" />
              <input
                type="text"
                placeholder="Search workflows..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="flex-1 border-none bg-transparent outline-none text-xs"
              />
            </div>
            <div className="flex gap-1">
              {(['all', 'completed', 'failed', 'running'] as const).map((status) => (
                <button
                  key={status}
                  onClick={() => setStatusFilter(status)}
                  className={`px-2.5 py-1 text-xs font-medium rounded-md transition-colors capitalize ${
                    statusFilter === status
                      ? 'bg-blue-100 text-blue-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  }`}
                >
                  {status}
                </button>
              ))}
            </div>
          </div>

          {/* Table Header */}
          <div className="grid grid-cols-[1fr_90px_70px_80px_90px] gap-3 px-4 py-2 bg-gray-50 border-b border-gray-200 text-xs font-medium text-gray-500">
            <div>Workflow</div>
            <div className="cursor-pointer hover:text-gray-700 select-none" onClick={() => toggleSort('status')}>
              Status {sortField === 'status' && (sortDirection === 'desc' ? '\u2193' : '\u2191')}
            </div>
            <div className="cursor-pointer hover:text-gray-700 select-none" onClick={() => toggleSort('duration')}>
              Duration {sortField === 'duration' && (sortDirection === 'desc' ? '\u2193' : '\u2191')}
            </div>
            <div className="cursor-pointer hover:text-gray-700 select-none" onClick={() => toggleSort('cost')}>
              Cost {sortField === 'cost' && (sortDirection === 'desc' ? '\u2193' : '\u2191')}
            </div>
            <div className="cursor-pointer hover:text-gray-700 select-none" onClick={() => toggleSort('time')}>
              Started {sortField === 'time' && (sortDirection === 'desc' ? '\u2193' : '\u2191')}
            </div>
          </div>

          {/* Table Body — click row to open detail */}
          <div className="flex-1 overflow-y-auto">
            {filteredExecutions.map((exec) => {
              const duration = exec.endTime
                ? Math.round((new Date(exec.endTime).getTime() - new Date(exec.startTime).getTime()) / 1000)
                : null
              return (
                <div
                  key={exec.id}
                  onClick={() => {
                    setSelectedExecutionId(exec.id)
                    setCurrentStep(0)
                  }}
                  className="grid grid-cols-[1fr_90px_70px_80px_90px] gap-3 px-4 py-2.5 border-b border-gray-100 hover:bg-blue-50 cursor-pointer transition-colors items-center"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="w-6 h-6 rounded bg-purple-50 flex items-center justify-center flex-shrink-0">
                      <Play size={10} className="text-purple-600" />
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-gray-900 truncate">{exec.workflowName}</div>
                      <div className="text-[10px] text-gray-400">{exec.id.slice(0, 8)}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    {getStatusIcon(exec.status)}
                    <span className={`text-xs font-medium capitalize ${
                      exec.status === 'completed' ? 'text-green-600' :
                      exec.status === 'failed' ? 'text-red-600' :
                      exec.status === 'running' ? 'text-blue-600' :
                      'text-gray-600'
                    }`}>
                      {exec.status}
                    </span>
                  </div>
                  <div className="text-xs text-gray-600">
                    {duration !== null ? `${duration}s` : '-'}
                  </div>
                  <div className="text-xs font-medium text-gray-900">
                    ${exec.totalCost.toFixed(4)}
                  </div>
                  <div className="text-xs text-gray-500">
                    {new Date(exec.startTime).toLocaleTimeString()}
                  </div>
                </div>
              )
            })}

            {filteredExecutions.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-gray-400">
                <Activity className="h-12 w-12 mb-3 opacity-30" />
                <p className="text-sm font-medium">No executions found</p>
                <p className="text-xs mt-1">Try adjusting your filters or run a workflow</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Detail View — full-width debugger, shown when a run is selected */}
      {selectedExecutionId && selectedExecution && executionSteps.length > 0 && (
      <div className="flex flex-col flex-1 min-h-0">
        <div className="bg-white rounded-lg border border-gray-200 overflow-hidden flex flex-col flex-1">
            <>

              {/* Workflow Visualization — resizable canvas */}
              {workflowData && showWorkflowView && (
                <div style={{ height: canvasHeight }} className="bg-white flex-shrink-0">
                  <WorkflowVisualization
                    nodes={workflowData.nodes || []}
                    edges={workflowData.edges || []}
                    currentStep={step}
                    completedSteps={executionSteps.slice(0, currentStep)}
                  />
                </div>
              )}

              {/* Drag handle + toggle + timeline in one row */}
              <div className="flex items-center border-y border-gray-200 bg-gray-50 flex-shrink-0">
                {/* Canvas toggle */}
                {workflowData && (
                  <button
                    onClick={() => setShowWorkflowView(!showWorkflowView)}
                    className="flex items-center gap-1 px-2 py-1.5 text-[10px] text-gray-500 hover:text-gray-700 hover:bg-gray-100 transition-colors border-r border-gray-200"
                  >
                    <GitBranch size={10} />
                    <ChevronRight
                      size={10}
                      className={`transition-transform ${showWorkflowView ? 'rotate-90' : ''}`}
                    />
                  </button>
                )}
                {/* Drag handle — only when canvas is visible */}
                {workflowData && showWorkflowView && (
                  <div
                    onMouseDown={handleDragStart}
                    className="flex items-center justify-center px-2 py-1.5 cursor-row-resize hover:bg-gray-200 transition-colors border-r border-gray-200 group"
                    title="Drag to resize"
                  >
                    <div className="flex flex-col gap-[2px]">
                      <div className="w-4 h-[2px] bg-gray-300 rounded group-hover:bg-gray-500" />
                      <div className="w-4 h-[2px] bg-gray-300 rounded group-hover:bg-gray-500" />
                    </div>
                  </div>
                )}
                {/* Timeline steps */}
                <div className="flex items-center gap-2 px-2 py-1.5 flex-1 min-w-0">
                <button
                  onClick={() => goToStep(currentStep - 1)}
                  disabled={currentStep === 0 || isReplaying}
                  className="flex items-center p-1 bg-white hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed rounded border border-gray-200 transition-colors flex-shrink-0"
                >
                  <ChevronLeft size={14} />
                </button>
                <div className="flex gap-1.5 flex-1 overflow-x-auto">
                  {executionSteps.map((s, index) => (
                    <div
                      key={s.id}
                      onClick={() => goToStep(index)}
                      className={`flex items-center gap-1.5 px-2 py-1.5 rounded-md border cursor-pointer transition-all whitespace-nowrap flex-shrink-0 ${
                        index === currentStep
                          ? 'bg-blue-50 border-blue-400 shadow-sm ring-1 ring-blue-200'
                          : index < currentStep
                          ? 'bg-green-50 border-green-200'
                          : 'bg-white border-gray-200 hover:bg-gray-50'
                      }`}
                    >
                      {s.status === 'completed' && <CheckCircle size={10} className="text-green-600" />}
                      {s.status === 'failed' && <AlertCircle size={10} className="text-red-600" />}
                      {s.status === 'pending' && <Clock size={10} className="text-gray-400" />}
                      <span className="text-[11px] font-medium truncate max-w-[100px]">{s.name}</span>
                      {s.duration && s.duration !== '-' && (
                        <span className="text-[10px] text-gray-400">{s.duration}</span>
                      )}
                    </div>
                  ))}
                </div>
                <button
                  onClick={() => goToStep(currentStep + 1)}
                  disabled={currentStep === executionSteps.length - 1 || isReplaying}
                  className="flex items-center p-1 bg-white hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed rounded border border-gray-200 transition-colors flex-shrink-0"
                >
                  <ChevronRight size={14} />
                </button>
                <span className="text-[10px] text-gray-400 whitespace-nowrap flex-shrink-0">
                  {currentStep + 1}/{executionSteps.length}
                </span>
                </div>{/* close timeline steps inner div */}
              </div>{/* close combined drag handle + timeline row */}

              {/* State Display */}
              <div className="flex-1 overflow-auto p-3">
                <div className={`grid ${compareMode ? 'grid-cols-2' : 'grid-cols-1'} gap-3 h-full`}>
                  {/* Main State Panel */}
                  <div className="flex flex-col h-full">
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-xs font-semibold text-gray-700">"{step.name}"</h3>
                      <div className="flex items-center gap-2 text-[10px] text-gray-400">
                        {step.state?.model && (
                          <span className="px-1.5 py-0.5 bg-gray-100 rounded text-gray-600">{step.state.model}</span>
                        )}
                        {step.state?.cost != null && (
                          <span className="text-purple-600 font-medium">${Number(step.state.cost).toFixed(6)}</span>
                        )}
                        <span className={`font-medium ${
                          step.status === 'completed' ? 'text-green-600' :
                          step.status === 'failed' ? 'text-red-600' : 'text-gray-500'
                        }`}>{step.status}</span>
                        <span className="text-blue-600 font-medium">{step.duration}</span>
                      </div>
                    </div>
                    <div className="flex-1 overflow-auto space-y-2">

                      {/* Input Section */}
                      {step.state?.input && (
                        <div className="rounded-md border border-gray-200 overflow-hidden">
                          <div className="bg-blue-50 px-2.5 py-1 border-b border-blue-100">
                            <span className="text-[10px] font-semibold text-blue-700 uppercase tracking-wide">Input</span>
                          </div>
                          <div className="bg-gray-900 text-gray-100 p-2 font-mono text-[11px] max-h-40 overflow-auto">
                            <pre className="whitespace-pre-wrap">{(() => {
                              try { return JSON.stringify(JSON.parse(step.state.input!), null, 2) }
                              catch { return step.state.input }
                            })()}</pre>
                          </div>
                        </div>
                      )}

                      {/* Output Section */}
                      {step.state?.output && (
                        <div className="rounded-md border border-gray-200 overflow-hidden">
                          <div className="bg-green-50 px-2.5 py-1 border-b border-green-100">
                            <span className="text-[10px] font-semibold text-green-700 uppercase tracking-wide">Output</span>
                          </div>
                          <div className="bg-gray-900 text-gray-100 p-2 font-mono text-[11px] flex-1 overflow-auto">
                            <pre className="whitespace-pre-wrap">{(() => {
                              try {
                                const parsed = JSON.parse(step.state.output!)
                                if (parsed.content && typeof parsed.content === 'string') {
                                  return parsed.content
                                }
                                return JSON.stringify(parsed, null, 2)
                              } catch { return step.state.output }
                            })()}</pre>
                          </div>
                        </div>
                      )}

                      {/* Error Section */}
                      {step.state?.error && (
                        <div className="rounded-md border border-red-200 overflow-hidden">
                          <div className="bg-red-50 px-2.5 py-1 border-b border-red-100">
                            <span className="text-[10px] font-semibold text-red-700 uppercase tracking-wide">Error</span>
                          </div>
                          <div className="bg-red-900 text-red-100 p-2 font-mono text-[11px] max-h-28 overflow-auto">
                            <pre className="whitespace-pre-wrap">{step.state.error}</pre>
                          </div>
                        </div>
                      )}

                      {/* Empty state */}
                      {!step.state?.input && !step.state?.output && !step.state?.error && (
                        <div className="bg-gray-50 rounded-md p-3 text-center text-xs text-gray-400 border border-gray-200">
                          No input/output data recorded for this step
                        </div>
                      )}
                    </div>

                    {/* A/B Testing Feedback Section */}
                    {(() => {
                      // Extract ab_testing data from multiple sources
                      let abTesting: { assignment_id: number; experiment_id: number; variant_name: string } | null = null;

                      // First, try to get from node_states (most reliable source)
                      // node_states has the full output object with ab_testing
                      const nodeStates = selectedExecution.node_states;
                      if (nodeStates && step.name) {
                        const nodeState = nodeStates[step.name];
                        if (nodeState?.output?.ab_testing) {
                          abTesting = nodeState.output.ab_testing;
                        }
                      }

                      // Fallback: try from step.state.output (may be stringified)
                      if (!abTesting && step.state?.output) {
                        try {
                          const outputData = typeof step.state.output === 'string'
                            ? JSON.parse(step.state.output)
                            : step.state.output;
                          if (outputData?.ab_testing) {
                            abTesting = outputData.ab_testing;
                          }
                        } catch {
                          // Not JSON or no ab_testing data
                        }
                      }

                      if (!abTesting) return null;

                      return (
                        <div className="mt-4 p-4 bg-gradient-to-r from-indigo-50 to-purple-50 border border-indigo-200 rounded-lg">
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-semibold px-2 py-1 bg-indigo-100 text-indigo-700 rounded uppercase tracking-wide">
                                A/B Test
                              </span>
                              <span className="text-sm text-gray-600">
                                Variant: <strong className="text-gray-900">{abTesting.variant_name}</strong>
                              </span>
                            </div>
                          </div>

                          <div className="flex items-center gap-3">
                            <span className="text-sm text-gray-600">Was this output helpful?</span>

                            {feedbackState[abTesting.assignment_id] === 'pending' ? (
                              <span className="text-sm text-gray-500 flex items-center gap-2">
                                <Loader2 size={14} className="animate-spin" />
                                Submitting...
                              </span>
                            ) : feedbackState[abTesting.assignment_id] ? (
                              <span className={`text-sm flex items-center gap-2 ${
                                feedbackState[abTesting.assignment_id] === 'positive' ? 'text-green-600' : 'text-red-600'
                              }`}>
                                {feedbackState[abTesting.assignment_id] === 'positive' ? (
                                  <><ThumbsUp size={14} /> Thanks for the feedback!</>
                                ) : (
                                  <><ThumbsDown size={14} /> Thanks for the feedback!</>
                                )}
                              </span>
                            ) : (
                              <div className="flex gap-2">
                                <button
                                  onClick={() => submitFeedback(abTesting!.assignment_id, true)}
                                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-green-700 bg-green-50 border border-green-200 rounded-lg hover:bg-green-100 transition-colors"
                                >
                                  <ThumbsUp size={14} />
                                  Helpful
                                </button>
                                <button
                                  onClick={() => submitFeedback(abTesting!.assignment_id, false)}
                                  className="flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium text-red-700 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 transition-colors"
                                >
                                  <ThumbsDown size={14} />
                                  Not Helpful
                                </button>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })()}

                    <div className="flex gap-2 mt-2">
                      <button
                        onClick={replayFromHere}
                        disabled={isReplaying || currentStep === executionSteps.length - 1}
                        className="flex items-center gap-1 px-3 py-1.5 bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded transition-colors text-xs font-medium"
                      >
                        <Play size={12} />
                        Replay from here
                      </button>
                      <button
                        onClick={openModifyModal}
                        className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors text-xs font-medium"
                      >
                        Modify & Retry
                      </button>
                    </div>
                  </div>

                  {/* Compare Panel */}
                  {compareMode && compareStepData && (
                    <div className="flex flex-col h-full">
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="text-xs font-semibold text-gray-700">Compare: Step {compareStep! + 1}</h3>
                        <select
                          value={compareStep!}
                          onChange={(e) => setCompareStep(Number(e.target.value))}
                          className="text-[10px] border border-gray-200 rounded px-1.5 py-0.5"
                        >
                          {executionSteps.map((s, index) => (
                            <option key={s.id} value={index} disabled={index === currentStep}>
                              Step {index + 1}: {s.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="flex-1 overflow-auto space-y-2">
                        <div className="flex items-center gap-3 text-[10px] text-gray-400">
                          <span className={`font-medium ${
                            compareStepData.status === 'completed' ? 'text-green-600' : 'text-red-600'
                          }`}>{compareStepData.status}</span>
                          <span className="text-blue-600 font-medium">{compareStepData.duration}</span>
                        </div>
                        {compareStepData.state?.output && (
                          <div className="rounded-md border border-gray-200 overflow-hidden">
                            <div className="bg-green-50 px-2.5 py-1 border-b border-green-100">
                              <span className="text-[10px] font-semibold text-green-700 uppercase tracking-wide">Output</span>
                            </div>
                            <div className="bg-gray-900 text-gray-100 p-2 font-mono text-[11px] flex-1 overflow-auto">
                              <pre className="whitespace-pre-wrap">{(() => {
                                try {
                                  const parsed = JSON.parse(compareStepData.state.output!)
                                  if (parsed.content && typeof parsed.content === 'string') return parsed.content
                                  return JSON.stringify(parsed, null, 2)
                                } catch { return compareStepData.state.output }
                              })()}</pre>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Summary Stats — compact inline bar */}
              {selectedExecution.endTime && (
                <div className="flex items-center justify-center gap-4 px-3 py-1.5 border-t border-gray-200 bg-gray-50 text-[10px]">
                  <span className="text-gray-400">Duration: <span className="font-semibold text-gray-700">{Math.round((new Date(selectedExecution.endTime).getTime() - new Date(selectedExecution.startTime).getTime()) / 1000)}s</span></span>
                  <span className="text-gray-300">|</span>
                  <span className="text-gray-400">Cost: <span className="font-semibold text-purple-700">${selectedExecution.totalCost.toFixed(4)}</span></span>
                  <span className="text-gray-300">|</span>
                  <span className={`font-semibold ${selectedExecution.status === 'completed' ? 'text-green-600' : 'text-red-600'}`}>{selectedExecution.status}</span>
                  <span className="text-gray-300">|</span>
                  <span className="text-gray-400">{executionSteps.length} steps</span>
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

                    {/* Live execution steps with output */}
                    {reExecutionSteps.length > 0 && (
                      <div className="mb-4">
                        <label className="block text-sm font-medium text-gray-700 mb-2">Execution Progress</label>
                        <div className="border border-gray-200 rounded-lg overflow-hidden max-h-[400px] overflow-y-auto">
                          {reExecutionSteps.map((execStep, idx) => {
                            // Parse output for display
                            let outputText = ''
                            if (execStep.state?.output) {
                              try {
                                const parsed = JSON.parse(execStep.state.output)
                                if (parsed.content && typeof parsed.content === 'string') {
                                  outputText = parsed.content
                                } else if (parsed.message_id) {
                                  outputText = `Sent to channel ${parsed.channel_id || ''}`
                                } else {
                                  outputText = JSON.stringify(parsed, null, 2)
                                }
                              } catch {
                                outputText = execStep.state.output
                              }
                            }
                            return (
                              <div
                                key={idx}
                                className={`px-3 py-2 text-sm border-b border-gray-100 last:border-b-0 ${
                                  execStep.status === 'completed' ? 'bg-green-50' :
                                  execStep.status === 'running' ? 'bg-blue-50' :
                                  execStep.status === 'failed' ? 'bg-red-50' : ''
                                }`}
                              >
                                <div className="flex items-center gap-2">
                                  {execStep.status === 'running' && <Loader2 size={12} className="animate-spin text-blue-500" />}
                                  {execStep.status === 'completed' && <CheckCircle size={12} className="text-green-500" />}
                                  {execStep.status === 'failed' && <XCircle size={12} className="text-red-500" />}
                                  <span className="flex-1 font-medium">{execStep.name}</span>
                                  <span className="text-gray-500">{execStep.duration}</span>
                                </div>
                                {outputText && execStep.status === 'completed' && (
                                  <div className="mt-1.5 ml-5 bg-gray-900 text-gray-100 rounded p-2 font-mono text-xs max-h-32 overflow-auto">
                                    <pre className="whitespace-pre-wrap">{outputText}</pre>
                                  </div>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      </div>
                    )}

                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={() => {
                          setShowModifyModal(false)
                          setReExecutionStatus(null)
                          setReExecutionSteps([])
                          if (wsRef.current) {
                            wsRef.current.close()
                            wsRef.current = null
                          }
                        }}
                        disabled={isReExecuting}
                        className="px-4 py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded transition-colors text-sm font-medium disabled:opacity-50"
                      >
                        Cancel
                      </button>
                      {reExecutionStatus?.includes('completed') ? (
                        <button
                          onClick={() => {
                            setShowModifyModal(false)
                            setReExecutionStatus(null)
                            setReExecutionSteps([])
                            // Auto-select the latest execution (it will be first after refetch)
                            queryClient.invalidateQueries({ queryKey: ['executions'] }).then(() => {
                              // Select the first execution after refresh (latest)
                              setTimeout(() => {
                                const latest = executions?.[0]
                                if (latest && latest.id !== selectedExecutionId) {
                                  setSelectedExecutionId(latest.id)
                                  setCurrentStep(0)
                                }
                              }, 500)
                            })
                          }}
                          className="flex items-center gap-1.5 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded transition-colors text-sm font-medium"
                        >
                          <CheckCircle size={14} />
                          View New Run
                        </button>
                      ) : (
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
        </div>
      </div>
      )}
    </div>
  )
}

export default RunsPage
