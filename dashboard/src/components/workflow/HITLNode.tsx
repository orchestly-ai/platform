import React, { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { UserCheck, Clock, Mail, MessageSquare, AlertCircle } from 'lucide-react'
import { AgentNodeData } from '../../types'

const HITLNode = memo(({ data, selected }: NodeProps<AgentNodeData>) => {
  const hitlConfig = data.hitlConfig || {}
  const approverCount = hitlConfig.approvers?.length || 0
  const hasTimeout = hitlConfig.timeout && hitlConfig.timeout > 0
  const notificationChannels = hitlConfig.notifyVia || []

  const approvalTypeLabel = {
    'any': 'Any approver',
    'all': 'All approvers',
    'majority': 'Majority',
  }[hitlConfig.approvalType || 'any']

  return (
    <div
      className={`
        px-4 py-3 shadow-lg rounded-lg border-2 min-w-[200px] max-w-[280px]
        ${selected ? 'border-amber-500 shadow-xl' : 'border-amber-300'}
        ${data.status === 'running' ? 'animate-pulse' : ''}
        ${data.status === 'error' ? 'border-red-500' : ''}
        ${data.status === 'success' ? 'border-green-500' : ''}
        bg-white
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-amber-500"
      />

      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <div className="p-1.5 rounded-lg bg-amber-100">
          <UserCheck className="w-4 h-4 text-amber-700" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm text-gray-900 truncate">
            {data.label}
          </div>
          <div className="text-xs text-amber-600 font-medium">
            Human Approval
          </div>
        </div>
      </div>

      {/* Configuration Display */}
      <div className="space-y-1.5 text-xs">
        {/* Approvers */}
        {approverCount > 0 && (
          <div className="flex items-center gap-1">
            <UserCheck className="w-3 h-3 text-gray-500 flex-shrink-0" />
            <span className="text-gray-700">
              {approverCount} approver{approverCount !== 1 ? 's' : ''}
            </span>
            <span className="text-gray-500">
              ({approvalTypeLabel})
            </span>
          </div>
        )}

        {/* Title/Description */}
        {hitlConfig.title && (
          <div className="text-gray-700 font-medium truncate">
            "{hitlConfig.title}"
          </div>
        )}

        {/* Timeout */}
        {hasTimeout && (
          <div className="flex items-center gap-1">
            <Clock className="w-3 h-3 text-gray-500 flex-shrink-0" />
            <span className="text-gray-600">
              {hitlConfig.timeout}m timeout
            </span>
            {hitlConfig.timeoutAction && (
              <span className="text-gray-500">
                → {hitlConfig.timeoutAction}
              </span>
            )}
          </div>
        )}

        {/* Notification Channels */}
        {notificationChannels.length > 0 && (
          <div className="flex items-center gap-1 flex-wrap">
            {notificationChannels.includes('email') && (
              <div className="flex items-center gap-0.5 px-1.5 py-0.5 bg-blue-50 text-blue-700 rounded">
                <Mail className="w-3 h-3" />
                <span className="text-[10px]">Email</span>
              </div>
            )}
            {notificationChannels.includes('slack') && (
              <div className="flex items-center gap-0.5 px-1.5 py-0.5 bg-purple-50 text-purple-700 rounded">
                <MessageSquare className="w-3 h-3" />
                <span className="text-[10px]">Slack</span>
              </div>
            )}
            {notificationChannels.includes('sms') && (
              <div className="flex items-center gap-0.5 px-1.5 py-0.5 bg-green-50 text-green-700 rounded">
                <MessageSquare className="w-3 h-3" />
                <span className="text-[10px]">SMS</span>
              </div>
            )}
          </div>
        )}

        {/* Custom Actions */}
        {hitlConfig.customActions && hitlConfig.customActions.length > 0 && (
          <div className="flex items-center gap-1">
            <AlertCircle className="w-3 h-3 text-gray-500 flex-shrink-0" />
            <span className="text-gray-600">
              {hitlConfig.customActions.length} custom action{hitlConfig.customActions.length !== 1 ? 's' : ''}
            </span>
          </div>
        )}

        {/* Status/Metrics */}
        {(data.cost != null || data.executionTime != null) && (
          <div className="pt-1.5 mt-1.5 border-t border-gray-200">
            <div className="flex items-center justify-between text-[10px]">
              {data.executionTime != null && (
                <span className="text-gray-500">
                  {data.executionTime.toFixed(0)}ms
                </span>
              )}
              {data.cost != null && (
                <span className="text-gray-500">
                  ${data.cost.toFixed(4)}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Error Display */}
        {data.error && (
          <div className="text-[10px] text-red-600 bg-red-50 px-2 py-1 rounded mt-1">
            {data.error}
          </div>
        )}
      </div>

      {/* Status Indicator */}
      {data.status && data.status !== 'idle' && (
        <div className={`
          absolute -top-2 -right-2 w-5 h-5 rounded-full border-2 border-white
          flex items-center justify-center
          ${data.status === 'running' ? 'bg-blue-500 animate-pulse' : ''}
          ${data.status === 'success' ? 'bg-green-500' : ''}
          ${data.status === 'error' ? 'bg-red-500' : ''}
          ${data.status === 'pending' ? 'bg-yellow-500' : ''}
        `}>
          <span className="text-white text-[10px] font-bold">
            {data.status === 'running' && '⋯'}
            {data.status === 'success' && '✓'}
            {data.status === 'error' && '✕'}
            {data.status === 'pending' && '○'}
          </span>
        </div>
      )}

      <Handle
        type="source"
        position={Position.Bottom}
        className="w-3 h-3 !bg-amber-500"
      />
    </div>
  )
})

HITLNode.displayName = 'HITLNode'

export default HITLNode
