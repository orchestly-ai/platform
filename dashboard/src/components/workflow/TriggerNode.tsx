import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Zap, Webhook, Clock, Hand, Radio } from 'lucide-react'
import { AgentNodeData, TriggerType } from '../../types'

const triggerIcons: Record<TriggerType, React.ReactNode> = {
  webhook: <Webhook className="w-4 h-4 text-white" />,
  cron: <Clock className="w-4 h-4 text-white" />,
  manual: <Hand className="w-4 h-4 text-white" />,
  event: <Radio className="w-4 h-4 text-white" />,
}

const triggerLabels: Record<TriggerType, string> = {
  webhook: 'Webhook',
  cron: 'Schedule',
  manual: 'Manual',
  event: 'Event',
}

function TriggerNode({ data, selected }: NodeProps<AgentNodeData>) {
  const statusColors = {
    idle: 'bg-orange-50 border-orange-300',
    pending: 'bg-yellow-100 border-yellow-300',
    running: 'bg-blue-100 border-blue-400 animate-pulse',
    success: 'bg-green-100 border-green-400',
    error: 'bg-red-100 border-red-400',
  }

  const statusColor = statusColors[data.status || 'idle']
  const triggerType = data.triggerConfig?.triggerType || 'manual'

  return (
    <div
      className={`px-4 py-3 shadow-lg rounded-lg border-2 ${statusColor} ${
        selected ? 'ring-2 ring-orange-500' : ''
      } min-w-[200px] transition-all`}
    >
      {/* Node Header */}
      <div className="flex items-center gap-2 mb-2">
        <div className="p-1.5 bg-orange-500 rounded">
          {triggerIcons[triggerType] || <Zap className="w-4 h-4 text-white" />}
        </div>
        <div className="flex-1">
          <div className="text-xs font-medium text-orange-900">TRIGGER</div>
          <div className="font-semibold text-gray-900">{data.label}</div>
        </div>
      </div>

      {/* Trigger Details */}
      <div className="space-y-1 text-xs text-gray-600">
        <div className="flex items-center gap-1">
          <span className="font-medium">Type:</span>
          <span className="px-1.5 py-0.5 bg-orange-200 text-orange-900 rounded">
            {triggerLabels[triggerType]}
          </span>
        </div>

        {triggerType === 'cron' && data.triggerConfig?.cronExpression && (
          <div className="flex items-center gap-1">
            <span className="font-medium">Cron:</span>
            <span className="font-mono text-orange-700">{data.triggerConfig.cronExpression}</span>
          </div>
        )}

        {triggerType === 'webhook' && data.triggerConfig?.webhookUrl && (
          <div className="mt-1 p-1.5 bg-orange-100 rounded text-xs font-mono truncate">
            {data.triggerConfig.webhookUrl}
          </div>
        )}

        {triggerType === 'event' && data.triggerConfig?.eventName && (
          <div className="flex items-center gap-1">
            <span className="font-medium">Event:</span>
            <span className="text-orange-700">{data.triggerConfig.eventName}</span>
          </div>
        )}
      </div>

      {/* Error message */}
      {data.error && (
        <div className="mt-2 p-2 bg-red-50 border border-red-200 rounded text-xs text-red-800">
          {data.error}
        </div>
      )}

      {/* Output Handle - Triggers only have output */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 !bg-orange-500"
      />
    </div>
  )
}

export default memo(TriggerNode)
