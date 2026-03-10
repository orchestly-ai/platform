import React, { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import { Webhook, Lock, Globe, AlertCircle } from 'lucide-react'
import { AgentNodeData } from '../../types'

const WebhookNode = memo(({ data, selected }: NodeProps<AgentNodeData>) => {
  const webhookConfig = data.webhookConfig || {}
  const hasAuth = webhookConfig.authentication?.type && webhookConfig.authentication.type !== 'none'
  const webhookUrl = webhookConfig.webhookUrl || 'Not configured'

  // Extract domain or show placeholder
  const getUrlDisplay = () => {
    if (!webhookConfig.webhookUrl) return 'Configure webhook URL'
    try {
      const url = new URL(webhookConfig.webhookUrl)
      return url.hostname
    } catch {
      return webhookConfig.webhookUrl.substring(0, 30) + '...'
    }
  }

  const methodColor = webhookConfig.method === 'GET'
    ? 'text-blue-700 bg-blue-100'
    : 'text-green-700 bg-green-100'

  return (
    <div
      className={`
        px-4 py-3 shadow-lg rounded-lg border-2 min-w-[200px] max-w-[280px]
        ${selected ? 'border-purple-500 shadow-xl' : 'border-purple-300'}
        ${data.status === 'running' ? 'animate-pulse' : ''}
        ${data.status === 'error' ? 'border-red-500' : ''}
        ${data.status === 'success' ? 'border-green-500' : ''}
        bg-white
      `}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-purple-500"
      />

      {/* Header */}
      <div className="flex items-center gap-2 mb-2">
        <div className="p-1.5 rounded-lg bg-purple-100">
          <Webhook className="w-4 h-4 text-purple-700" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="font-semibold text-sm text-gray-900 truncate">
            {data.label}
          </div>
          <div className="text-xs text-purple-600 font-medium">
            Webhook Listener
          </div>
        </div>
        {hasAuth && (
          <Lock className="w-3.5 h-3.5 text-gray-500 flex-shrink-0" />
        )}
      </div>

      {/* Configuration Display */}
      <div className="space-y-1.5 text-xs">
        {/* HTTP Method */}
        {webhookConfig.method && (
          <div className="flex items-center gap-1.5">
            <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${methodColor}`}>
              {webhookConfig.method}
            </span>
          </div>
        )}

        {/* Webhook URL */}
        <div className="flex items-center gap-1">
          <Globe className="w-3 h-3 text-gray-500 flex-shrink-0" />
          <span className="truncate text-gray-700">
            {getUrlDisplay()}
          </span>
        </div>

        {/* Authentication Type */}
        {hasAuth && (
          <div className="flex items-center gap-1">
            <Lock className="w-3 h-3 text-gray-500 flex-shrink-0" />
            <span className="text-gray-600">
              {webhookConfig.authentication?.type === 'secret' && 'Secret Token'}
              {webhookConfig.authentication?.type === 'hmac' && 'HMAC Signature'}
              {webhookConfig.authentication?.type === 'oauth2' && 'OAuth 2.0'}
            </span>
          </div>
        )}

        {/* Conditions */}
        {webhookConfig.conditions && webhookConfig.conditions.length > 0 && (
          <div className="flex items-center gap-1">
            <AlertCircle className="w-3 h-3 text-gray-500 flex-shrink-0" />
            <span className="text-gray-600">
              {webhookConfig.conditions.length} filter{webhookConfig.conditions.length !== 1 ? 's' : ''}
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
        className="w-3 h-3 !bg-purple-500"
      />
    </div>
  )
})

WebhookNode.displayName = 'WebhookNode'

export default WebhookNode
