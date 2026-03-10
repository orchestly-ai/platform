import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Database, DollarSign, Clock, Search, Save, Trash2 } from 'lucide-react'
import { AgentNodeData } from '../../types'

function MemoryNode({ data, selected }: NodeProps<AgentNodeData>) {
  const statusColors = {
    idle: 'bg-gray-200 border-gray-300',
    pending: 'bg-yellow-100 border-yellow-300',
    running: 'bg-indigo-100 border-indigo-400 animate-pulse',
    success: 'bg-indigo-100 border-indigo-400',
    error: 'bg-red-100 border-red-400',
  }

  const statusColor = statusColors[data.status || 'idle']

  const operation = data.memoryConfig?.operation || 'query'
  const operationIcons = {
    store: <Save className="w-3 h-3" />,
    query: <Search className="w-3 h-3" />,
    delete: <Trash2 className="w-3 h-3" />,
  }

  const operationColors = {
    store: 'text-green-700 bg-green-100',
    query: 'text-blue-700 bg-blue-100',
    delete: 'text-red-700 bg-red-100',
  }

  return (
    <div
      className={`px-4 py-3 shadow-lg rounded-lg border-2 ${statusColor} ${
        selected ? 'ring-2 ring-indigo-500' : ''
      } min-w-[200px] transition-all`}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-indigo-500"
      />

      {/* Node Header */}
      <div className="flex items-center gap-2 mb-2">
        <div className="p-1.5 bg-indigo-500 rounded">
          <Database className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1">
          <div className="text-xs font-medium text-indigo-900">MEMORY</div>
          <div className="font-semibold text-gray-900">{data.label}</div>
        </div>
      </div>

      {/* Node Details */}
      <div className="space-y-1 text-xs text-gray-600">
        {/* Operation */}
        {data.memoryConfig && (
          <div className="flex items-center gap-2">
            <span className={`px-2 py-0.5 rounded font-bold text-xs flex items-center gap-1 ${operationColors[operation]}`}>
              {operationIcons[operation]}
              {operation.charAt(0).toUpperCase() + operation.slice(1)}
            </span>
          </div>
        )}

        {/* Namespace */}
        {data.memoryConfig?.namespace && (
          <div className="text-xs text-gray-700">
            <span className="font-medium">Namespace:</span> {data.memoryConfig.namespace}
          </div>
        )}

        {/* Query/Content preview */}
        {data.memoryConfig?.query && (
          <div className="text-xs text-gray-500 truncate">
            Query: "{data.memoryConfig.query.substring(0, 30)}{data.memoryConfig.query.length > 30 ? '...' : ''}"
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
        className="w-3 h-3 !bg-indigo-500"
      />
    </div>
  )
}

export default memo(MemoryNode)
