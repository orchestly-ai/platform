import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Bot, DollarSign, Clock, FileText } from 'lucide-react'
import { AgentNodeData } from '../../types'

function WorkerNode({ data, selected }: NodeProps<AgentNodeData>) {
  const statusColors = {
    idle: 'bg-gray-200 border-gray-300',
    pending: 'bg-yellow-100 border-yellow-300',
    running: 'bg-blue-100 border-blue-400 animate-pulse',
    success: 'bg-green-100 border-green-400',
    error: 'bg-red-100 border-red-400',
  }

  const statusColor = statusColors[data.status || 'idle']

  return (
    <div
      className={`px-4 py-3 shadow-lg rounded-lg border-2 ${statusColor} ${
        selected ? 'ring-2 ring-blue-500' : ''
      } min-w-[200px] transition-all`}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-blue-500"
      />

      {/* Node Header */}
      <div className="flex items-center gap-2 mb-2">
        <div className="p-1.5 bg-blue-500 rounded">
          <Bot className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1">
          <div className="text-xs font-medium text-blue-900">WORKER</div>
          <div className="font-semibold text-gray-900">{data.label}</div>
        </div>
      </div>

      {/* Node Details */}
      <div className="space-y-1 text-xs text-gray-600">
        {/* Model Selection Display */}
        {(data.modelSelection || data.llmModel) && (
          <div className="flex items-center gap-1">
            <span className="font-medium">Model:</span>
            {data.modelSelection === 'auto' && (
              <span className="truncate text-blue-600 font-medium">Auto (Routing)</span>
            )}
            {data.modelSelection === 'cost_optimized' && (
              <span className="truncate text-green-600 font-medium">Cost Optimized</span>
            )}
            {data.modelSelection === 'latency_optimized' && (
              <span className="truncate text-orange-600 font-medium">Latency Optimized</span>
            )}
            {data.modelSelection === 'quality_first' && (
              <span className="truncate text-purple-600 font-medium">Quality First</span>
            )}
            {(data.modelSelection?.startsWith('llm:') || (!data.modelSelection && data.llmModel)) && data.llmModel && (
              <span className="truncate text-gray-800 font-medium">{data.llmModel}</span>
            )}
          </div>
        )}

        {/* Runtime info - show actual model used after execution */}
        {data.actualModel && (
          <div className="flex items-center gap-1 text-blue-700">
            <span className="font-medium">Used:</span>
            <span className="truncate font-mono text-xs">{data.actualModel}</span>
          </div>
        )}

        {data.capabilities && data.capabilities.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-1">
            {data.capabilities.slice(0, 2).map((cap, idx) => (
              <span key={idx} className="px-1.5 py-0.5 bg-blue-200 text-blue-900 rounded text-xs">
                {cap}
              </span>
            ))}
            {data.capabilities.length > 2 && (
              <span className="px-1.5 py-0.5 bg-blue-200 text-blue-900 rounded text-xs">
                +{data.capabilities.length - 2}
              </span>
            )}
          </div>
        )}
        {data.promptSlug && (
          <div className="flex items-center gap-1 mt-1">
            <FileText className="w-3 h-3 text-green-600" />
            <span className="text-xs text-green-700 font-medium truncate">
              {data.promptSlug} {data.promptVersion && `v${data.promptVersion}`}
            </span>
          </div>
        )}
      </div>

      {/* Metrics */}
      {(data.cost != null || data.executionTime != null) && (
        <div className="flex items-center gap-3 mt-2 pt-2 border-t border-gray-300">
          {data.cost != null && (
            <div className="flex items-center gap-1 text-xs text-gray-700">
              <DollarSign className="w-3 h-3" />
              <span>${data.cost.toFixed(3)}</span>
            </div>
          )}
          {data.executionTime != null && (
            <div className="flex items-center gap-1 text-xs text-gray-700">
              <Clock className="w-3 h-3" />
              <span>{data.executionTime}ms</span>
            </div>
          )}
        </div>
      )}

      {/* Error message */}
      {data.error && (
        <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-800">
          {data.error}
        </div>
      )}

      {/* Output Handle */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 !bg-blue-500"
      />
    </div>
  )
}

export default memo(WorkerNode)
