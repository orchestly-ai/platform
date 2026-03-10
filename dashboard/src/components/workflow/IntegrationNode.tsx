import { memo } from 'react'
import { Handle, Position, NodeProps } from 'reactflow'
import {
  MessageSquare, CreditCard, Github, Mail, Phone,
  Cloud, Headphones, Users, BarChart3, FileSpreadsheet,
  Plug, DollarSign, Clock, FileText, Database, Send,
  AlertTriangle, CheckCircle
} from 'lucide-react'
import { AgentNodeData, IntegrationType } from '../../types'

const integrationIcons: Record<IntegrationType, React.ReactNode> = {
  slack: <MessageSquare className="w-4 h-4 text-white" />,
  discord: <MessageSquare className="w-4 h-4 text-white" />,
  gmail: <Mail className="w-4 h-4 text-white" />,
  stripe: <CreditCard className="w-4 h-4 text-white" />,
  github: <Github className="w-4 h-4 text-white" />,
  sendgrid: <Mail className="w-4 h-4 text-white" />,
  twilio: <Phone className="w-4 h-4 text-white" />,
  aws_s3: <Cloud className="w-4 h-4 text-white" />,
  zendesk: <Headphones className="w-4 h-4 text-white" />,
  hubspot: <Users className="w-4 h-4 text-white" />,
  salesforce: <BarChart3 className="w-4 h-4 text-white" />,
  notion: <FileText className="w-4 h-4 text-white" />,
  airtable: <Database className="w-4 h-4 text-white" />,
  mailchimp: <Send className="w-4 h-4 text-white" />,
  google_sheets: <FileSpreadsheet className="w-4 h-4 text-white" />,
  custom: <Plug className="w-4 h-4 text-white" />,
}

const integrationColors: Record<IntegrationType, string> = {
  slack: 'bg-purple-600',
  discord: 'bg-indigo-600',
  gmail: 'bg-red-500',
  stripe: 'bg-indigo-600',
  github: 'bg-gray-800',
  sendgrid: 'bg-blue-600',
  twilio: 'bg-red-500',
  aws_s3: 'bg-orange-500',
  zendesk: 'bg-green-600',
  hubspot: 'bg-orange-600',
  salesforce: 'bg-blue-500',
  notion: 'bg-gray-900',
  airtable: 'bg-teal-500',
  mailchimp: 'bg-yellow-500',
  google_sheets: 'bg-green-500',
  custom: 'bg-gray-600',
}

const integrationLabels: Record<IntegrationType, string> = {
  slack: 'Slack',
  discord: 'Discord',
  gmail: 'Gmail',
  stripe: 'Stripe',
  github: 'GitHub',
  sendgrid: 'SendGrid',
  twilio: 'Twilio',
  aws_s3: 'AWS S3',
  zendesk: 'Zendesk',
  hubspot: 'HubSpot',
  salesforce: 'Salesforce',
  notion: 'Notion',
  airtable: 'Airtable',
  mailchimp: 'Mailchimp',
  google_sheets: 'Google Sheets',
  custom: 'Custom API',
}

function IntegrationNode({ data, selected }: NodeProps<AgentNodeData>) {
  const isConnected = data.integrationConfig?.isConnected ?? false

  const statusColors = {
    idle: 'bg-indigo-50 border-indigo-300',
    pending: 'bg-yellow-100 border-yellow-300',
    running: 'bg-blue-100 border-blue-400 animate-pulse',
    success: 'bg-green-100 border-green-400',
    error: 'bg-red-100 border-red-400',
  }

  // Override status color if not connected
  const getStatusColor = () => {
    if (!isConnected) {
      return 'bg-orange-50 border-orange-400 border-dashed'
    }
    return statusColors[data.status || 'idle']
  }

  const statusColor = getStatusColor()
  const integrationType = data.integrationConfig?.integrationType || 'custom'

  return (
    <div
      className={`px-4 py-3 shadow-lg rounded-lg border-2 ${statusColor} ${
        selected ? 'ring-2 ring-indigo-500' : ''
      } min-w-[220px] transition-all relative`}
    >
      {/* Not Connected Warning Badge */}
      {!isConnected && (
        <div className="absolute -top-2 -right-2 flex items-center gap-1 px-2 py-0.5 bg-orange-500 text-white text-xs font-medium rounded-full shadow-sm">
          <AlertTriangle className="w-3 h-3" />
          <span>Not Connected</span>
        </div>
      )}

      {/* Connected Badge (only show if explicitly connected) */}
      {isConnected && data.status === 'idle' && (
        <div className="absolute -top-2 -right-2 flex items-center gap-1 px-2 py-0.5 bg-green-500 text-white text-xs font-medium rounded-full shadow-sm">
          <CheckCircle className="w-3 h-3" />
        </div>
      )}

      {/* Input Handle */}
      <Handle
        type="target"
        position={Position.Top}
        className="w-3 h-3 !bg-indigo-500"
      />

      {/* Node Header */}
      <div className="flex items-center gap-2 mb-2">
        <div className={`p-1.5 ${integrationColors[integrationType]} rounded`}>
          {integrationIcons[integrationType]}
        </div>
        <div className="flex-1">
          <div className="text-xs font-medium text-indigo-900">INTEGRATION</div>
          <div className="font-semibold text-gray-900">{data.label}</div>
        </div>
      </div>

      {/* Integration Details */}
      <div className="space-y-1 text-xs text-gray-600">
        <div className="flex items-center gap-1">
          <span className="font-medium">Service:</span>
          <span className={`px-1.5 py-0.5 ${integrationColors[integrationType]} text-white rounded text-xs`}>
            {integrationLabels[integrationType]}
          </span>
        </div>

        {data.integrationConfig?.action && (
          <div className="flex items-center gap-1">
            <span className="font-medium">Action:</span>
            <span className="text-indigo-700">{data.integrationConfig.action}</span>
          </div>
        )}

        {/* Show some parameters preview */}
        {data.integrationConfig?.parameters && Object.keys(data.integrationConfig.parameters).length > 0 && (
          <div className="mt-1 p-1.5 bg-indigo-100 rounded text-xs">
            <div className="font-medium text-indigo-800 mb-1">Parameters:</div>
            {Object.entries(data.integrationConfig.parameters).slice(0, 2).map(([key, value]) => (
              <div key={key} className="flex items-center gap-1 text-indigo-700">
                <span className="font-mono">{key}:</span>
                <span className="truncate">{String(value).slice(0, 20)}</span>
              </div>
            ))}
            {Object.keys(data.integrationConfig.parameters).length > 2 && (
              <div className="text-indigo-500">+{Object.keys(data.integrationConfig.parameters).length - 2} more</div>
            )}
          </div>
        )}
      </div>

      {/* Metrics */}
      {(data.cost != null || data.executionTime != null) && (
        <div className="flex items-center gap-3 mt-2 pt-2 border-t border-indigo-200">
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

      {/* Not Connected Warning */}
      {!isConnected && (
        <div className="mt-2 p-2 bg-orange-50 border border-orange-200 rounded text-xs text-orange-800 flex items-center gap-1.5">
          <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
          <span>Click to configure credentials</span>
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

export default memo(IntegrationNode)
