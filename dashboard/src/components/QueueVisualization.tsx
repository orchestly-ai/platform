import { QueueMetrics } from '@/types'
import { Layers, AlertOctagon } from 'lucide-react'

interface QueueVisualizationProps {
  queues: QueueMetrics
}

export function QueueVisualization({ queues }: QueueVisualizationProps) {
  const capabilities = Object.entries(queues.by_capability).sort(
    ([, a], [, b]) => b - a
  )

  const maxDepth = Math.max(...Object.values(queues.by_capability), 1)

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Task Queues</h2>
          <p className="text-sm text-gray-500 mt-1">
            Total depth: {queues.total_depth}
          </p>
        </div>
        <Layers className="h-6 w-6 text-blue-600" />
      </div>

      {capabilities.length === 0 ? (
        <div className="text-center py-8">
          <Layers className="h-12 w-12 mx-auto mb-3 text-gray-300" />
          <p className="text-gray-500">No tasks in queue</p>
        </div>
      ) : (
        <div className="space-y-4">
          {capabilities.map(([capability, depth]) => {
            const percentage = (depth / maxDepth) * 100

            return (
              <div key={capability}>
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700">
                    {capability}
                  </span>
                  <span className="text-sm font-semibold text-gray-900">
                    {depth}
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2.5">
                  <div
                    className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            )
          })}
        </div>
      )}

      {queues.dead_letter_queue > 0 && (
        <div className="mt-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <div className="flex items-center space-x-2">
            <AlertOctagon className="h-5 w-5 text-red-600" />
            <div>
              <p className="text-sm font-medium text-red-900">
                Dead Letter Queue
              </p>
              <p className="text-sm text-red-700">
                {queues.dead_letter_queue} failed tasks require attention
              </p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
