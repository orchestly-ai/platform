import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Wrench, DollarSign, Clock } from 'lucide-react'
import { AgentNodeData } from '../../types'

function ToolNode({ data, selected }: NodeProps<AgentNodeData>) {
  const statusColors = {
    idle: 'bg-gray-200 border-gray-300',
    pending: 'bg-yellow-100 border-yellow-300',
    running: 'bg-green-100 border-green-400 animate-pulse',
    success: 'bg-green-100 border-green-400',
    error: 'bg-red-100 border-red-400',
  }

  const statusColor = statusColors[data.status || 'idle']

  return (
    <div
      className={`px-4 py-3 shadow-lg rounded-lg border-2 ${statusColor} ${
        selected ? 'ring-2 ring-green-500' : ''
      } min-w-[200px] transition-all`}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-green-500"
      />

      {/* Node Header */}
      <div className="flex items-center gap-2 mb-2">
        <div className="p-1.5 bg-green-500 rounded">
          <Wrench className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1">
          <div className="text-xs font-medium text-green-900">TOOL</div>
          <div className="font-semibold text-gray-900">{data.label}</div>
        </div>
      </div>

      {/* Node Details */}
      <div className="space-y-1 text-xs text-gray-600">
        {data.tools && data.tools.length > 0 && (
          <div>
            <span className="font-medium">Tools:</span>
            <div className="flex flex-wrap gap-1 mt-1">
              {data.tools.slice(0, 3).map((tool, idx) => (
                <span key={idx} className="px-1.5 py-0.5 bg-green-200 text-green-900 rounded text-xs">
                  {tool}
                </span>
              ))}
              {data.tools.length > 3 && (
                <span className="px-1.5 py-0.5 bg-green-200 text-green-900 rounded text-xs">
                  +{data.tools.length - 3}
                </span>
              )}
            </div>
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
        className="w-3 h-3 !bg-green-500"
      />
    </div>
  )
}

export default memo(ToolNode)
