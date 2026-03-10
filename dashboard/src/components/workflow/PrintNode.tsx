import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Terminal, Clock } from 'lucide-react'
import { AgentNodeData } from '../../types'

/**
 * PrintNode - Outputs messages to the Execution Log
 *
 * This node allows non-technical users to print output at any point
 * in the workflow for debugging and visibility purposes.
 * The output appears in the Execution Log panel during workflow execution.
 */
function PrintNode({ data, selected }: NodeProps<AgentNodeData>) {
  const statusColors = {
    idle: 'bg-gray-200 border-gray-300',
    pending: 'bg-yellow-100 border-yellow-300',
    running: 'bg-teal-100 border-teal-400 animate-pulse',
    success: 'bg-green-100 border-green-400',
    error: 'bg-red-100 border-red-400',
  }

  const statusColor = statusColors[data.status || 'idle']

  // Get the print message configuration
  const printConfig = data.printConfig || {}
  const message = printConfig.message || ''
  const label = printConfig.label || 'Output'

  return (
    <div
      className={`px-4 py-3 shadow-lg rounded-lg border-2 ${statusColor} ${
        selected ? 'ring-2 ring-teal-500' : ''
      } min-w-[180px] transition-all`}
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
          <Terminal className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1">
          <div className="text-xs font-medium text-teal-900">PRINT</div>
          <div className="font-semibold text-gray-900">{data.label || 'Print Output'}</div>
        </div>
      </div>

      {/* Node Details */}
      <div className="space-y-1 text-xs text-gray-600">
        {label && (
          <div className="flex items-center gap-1">
            <span className="font-medium">Label:</span>
            <span className="truncate text-teal-700">{label}</span>
          </div>
        )}
        {message && (
          <div className="mt-1 p-2 bg-teal-50 border border-teal-200 rounded text-xs text-teal-800 font-mono truncate">
            {message.length > 50 ? message.substring(0, 50) + '...' : message}
          </div>
        )}
        {!message && (
          <div className="mt-1 p-2 bg-gray-50 border border-gray-200 rounded text-xs text-gray-500 italic">
            No message configured
          </div>
        )}
      </div>

      {/* Metrics */}
      {data.executionTime != null && (
        <div className="flex items-center gap-3 mt-2 pt-2 border-t border-gray-300">
          <div className="flex items-center gap-1 text-xs text-gray-700">
            <Clock className="w-3 h-3" />
            <span>{data.executionTime}ms</span>
          </div>
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

export default memo(PrintNode)
