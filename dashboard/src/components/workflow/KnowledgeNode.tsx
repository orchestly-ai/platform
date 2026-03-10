import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { BookOpen, DollarSign, Clock, FileText } from 'lucide-react'
import { AgentNodeData } from '../../types'

function KnowledgeNode({ data, selected }: NodeProps<AgentNodeData>) {
  const statusColors = {
    idle: 'bg-gray-200 border-gray-300',
    pending: 'bg-yellow-100 border-yellow-300',
    running: 'bg-teal-100 border-teal-400 animate-pulse',
    success: 'bg-teal-100 border-teal-400',
    error: 'bg-red-100 border-red-400',
  }

  const statusColor = statusColors[data.status || 'idle']

  return (
    <div
      className={`px-4 py-3 shadow-lg rounded-lg border-2 ${statusColor} ${
        selected ? 'ring-2 ring-teal-500' : ''
      } min-w-[200px] transition-all`}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-teal-500"
      />

      {/* Node Header */}
      <div className="flex items-center gap-2 mb-2">
        <div className="p-1.5 bg-teal-500 rounded">
          <BookOpen className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1">
          <div className="text-xs font-medium text-teal-900">KNOWLEDGE</div>
          <div className="font-semibold text-gray-900">{data.label}</div>
        </div>
      </div>

      {/* Node Details */}
      <div className="space-y-1 text-xs text-gray-600">
        {/* Query preview */}
        {data.knowledgeConfig?.query && (
          <div className="flex items-center gap-1">
            <FileText className="w-3 h-3 text-gray-500 flex-shrink-0" />
            <span className="truncate text-gray-700 text-xs">
              "{data.knowledgeConfig.query.substring(0, 30)}{data.knowledgeConfig.query.length > 30 ? '...' : ''}"
            </span>
          </div>
        )}

        {/* Limit */}
        {data.knowledgeConfig?.limit && (
          <div className="text-xs text-gray-500">
            Limit: {data.knowledgeConfig.limit} results
          </div>
        )}

        {/* Rerank indicator */}
        {data.knowledgeConfig?.rerank && (
          <div className="text-xs text-teal-600 font-medium">
            ✓ Re-ranking enabled
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
        className="w-3 h-3 !bg-teal-500"
      />
    </div>
  )
}

export default memo(KnowledgeNode)
