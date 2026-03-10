import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { GitBranch, Check, X } from 'lucide-react'
import { AgentNodeData } from '../../types'

function ConditionNode({ data, selected }: NodeProps<AgentNodeData>) {
  const statusColors = {
    idle: 'bg-amber-50 border-amber-300',
    pending: 'bg-yellow-100 border-yellow-300',
    running: 'bg-blue-100 border-blue-400 animate-pulse',
    success: 'bg-green-100 border-green-400',
    error: 'bg-red-100 border-red-400',
  }

  const statusColor = statusColors[data.status || 'idle']

  return (
    <div
      className={`px-4 py-3 shadow-lg rounded-lg border-2 ${statusColor} ${
        selected ? 'ring-2 ring-amber-500' : ''
      } min-w-[200px] transition-all`}
    >
      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-amber-500"
      />

      {/* Node Header */}
      <div className="flex items-center gap-2 mb-2">
        <div className="p-1.5 bg-amber-500 rounded">
          <GitBranch className="w-4 h-4 text-white" />
        </div>
        <div className="flex-1">
          <div className="text-xs font-medium text-amber-900">CONDITION</div>
          <div className="font-semibold text-gray-900">{data.label}</div>
        </div>
      </div>

      {/* Condition Expression */}
      <div className="space-y-2 text-xs">
        {data.conditionConfig?.expression ? (
          <div className="p-2 bg-amber-100 rounded font-mono text-amber-800 break-all">
            {data.conditionConfig.expression}
          </div>
        ) : (
          <div className="p-2 bg-amber-100 rounded text-amber-600 italic">
            No condition set
          </div>
        )}

        {/* Branch Labels */}
        <div className="flex items-center justify-between pt-2">
          <div className="flex items-center gap-1 text-green-700">
            <Check className="w-3 h-3" />
            <span className="font-medium">
              {data.conditionConfig?.trueLabel || 'True'}
            </span>
          </div>
          <div className="flex items-center gap-1 text-red-700">
            <X className="w-3 h-3" />
            <span className="font-medium">
              {data.conditionConfig?.falseLabel || 'False'}
            </span>
          </div>
        </div>
      </div>

      {/* Error message */}
      {data.error && (
        <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-800">
          {data.error}
        </div>
      )}

      {/* Output Handles - Two outputs for true/false branches */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="true"
        style={{ left: '30%' }}
        className="w-3 h-3 !bg-green-500"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="false"
        style={{ left: '70%' }}
        className="w-3 h-3 !bg-red-500"
      />
    </div>
  )
}

export default memo(ConditionNode)
