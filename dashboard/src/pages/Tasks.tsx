import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { QueueVisualization } from '@/components/QueueVisualization'
import { Plus, Send } from 'lucide-react'

export function TasksPage() {
  const queryClient = useQueryClient()
  const [showSubmitForm, setShowSubmitForm] = useState(false)
  const [capability, setCapability] = useState('')
  const [inputData, setInputData] = useState('{}')

  const { data: metrics, isLoading: metricsLoading, error: metricsError } = useQuery({
    queryKey: ['systemMetrics'],
    queryFn: () => api.getSystemMetrics(),
    refetchInterval: 5000, // Refresh every 5 seconds
  })

  const { data: tasks, isLoading: tasksLoading, error: tasksError } = useQuery({
    queryKey: ['tasks'],
    queryFn: () => api.getTasks(),
    refetchInterval: 5000, // Refresh every 5 seconds
  })

  const submitTaskMutation = useMutation({
    mutationFn: (taskData: { capability: string; input_data: Record<string, unknown> }) =>
      api.submitTask(taskData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['tasks'] })
      queryClient.invalidateQueries({ queryKey: ['systemMetrics'] })
      setShowSubmitForm(false)
      setCapability('')
      setInputData('{}')
    },
  })

  const handleSubmitTask = (e: React.FormEvent) => {
    e.preventDefault()
    try {
      const parsedInput = JSON.parse(inputData)
      submitTaskMutation.mutate({
        capability,
        input_data: parsedInput,
      })
    } catch (error) {
      alert('Invalid JSON input data')
    }
  }

  if (metricsLoading) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tasks</h1>
          <p className="text-gray-600 mt-1">
            Monitor task queues and execution status
          </p>
        </div>
        <div className="flex items-center justify-center p-8">
          <div className="text-gray-500">Loading task metrics...</div>
        </div>
      </div>
    )
  }

  if (metricsError) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tasks</h1>
          <p className="text-gray-600 mt-1">
            Monitor task queues and execution status
          </p>
        </div>
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <h3 className="text-red-800 font-semibold mb-2">Error Loading Task Metrics</h3>
          <p className="text-red-600 text-sm">
            {metricsError instanceof Error ? metricsError.message : 'Failed to load task metrics'}
          </p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Tasks</h1>
          <p className="text-gray-600 mt-1">
            Monitor task queues and execution status
          </p>
        </div>
        <button
          onClick={() => setShowSubmitForm(!showSubmitForm)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <Plus className="w-4 h-4" />
          Submit Task
        </button>
      </div>

      {showSubmitForm && (
        <div className="bg-white rounded-lg border border-gray-200 p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Submit New Task</h3>
          <form onSubmit={handleSubmitTask} className="space-y-4">
            <div>
              <label htmlFor="capability" className="block text-sm font-medium text-gray-700 mb-1">
                Capability
              </label>
              <input
                type="text"
                id="capability"
                value={capability}
                onChange={(e) => setCapability(e.target.value)}
                placeholder="e.g., code_generation, data_analysis"
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>
            <div>
              <label htmlFor="inputData" className="block text-sm font-medium text-gray-700 mb-1">
                Input Data (JSON)
              </label>
              <textarea
                id="inputData"
                value={inputData}
                onChange={(e) => setInputData(e.target.value)}
                placeholder='{"key": "value"}'
                rows={4}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg font-mono text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                required
              />
            </div>
            <div className="flex gap-3">
              <button
                type="submit"
                disabled={submitTaskMutation.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors"
              >
                <Send className="w-4 h-4" />
                {submitTaskMutation.isPending ? 'Submitting...' : 'Submit Task'}
              </button>
              <button
                type="button"
                onClick={() => setShowSubmitForm(false)}
                className="px-4 py-2 bg-gray-200 text-gray-700 rounded-lg hover:bg-gray-300 transition-colors"
              >
                Cancel
              </button>
            </div>
            {submitTaskMutation.isError && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <p className="text-red-800 text-sm">
                  Error submitting task: {submitTaskMutation.error instanceof Error ? submitTaskMutation.error.message : 'Unknown error'}
                </p>
              </div>
            )}
            {submitTaskMutation.isSuccess && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-3">
                <p className="text-green-800 text-sm">Task submitted successfully!</p>
              </div>
            )}
          </form>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-1">
          <QueueVisualization queues={metrics?.queues || { total_depth: 0, by_capability: {}, dead_letter_queue: 0 }} />
        </div>

        <div className="lg:col-span-2">
          <div className="bg-white rounded-lg border border-gray-200 p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Task List</h3>

            {tasksLoading ? (
              <div className="text-center py-8 text-gray-500">Loading tasks...</div>
            ) : tasksError ? (
              <div className="bg-yellow-50 border border-yellow-200 rounded p-4">
                <p className="text-yellow-800 text-sm">
                  Task list endpoint not yet available in backend. Queue metrics shown on the left.
                </p>
              </div>
            ) : tasks && tasks.length > 0 ? (
              <div className="space-y-2">
                {tasks.map((task) => (
                  <div key={task.task_id} className="border border-gray-200 rounded-lg p-4">
                    <div className="flex justify-between items-start">
                      <div>
                        <h4 className="font-medium text-gray-900">{task.capability}</h4>
                        <p className="text-sm text-gray-600 mt-1">ID: {task.task_id}</p>
                      </div>
                      <span className={`px-2 py-1 text-xs font-medium rounded-full ${
                        task.status === 'completed' ? 'bg-green-100 text-green-800' :
                        task.status === 'running' ? 'bg-blue-100 text-blue-800' :
                        task.status === 'failed' ? 'bg-red-100 text-red-800' :
                        'bg-gray-100 text-gray-800'
                      }`}>
                        {task.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8">
                <p className="text-gray-600">
                  No tasks found. Task list endpoint not yet available in backend.
                </p>
                <p className="text-gray-500 text-sm mt-2">
                  Queue metrics are shown on the left.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
