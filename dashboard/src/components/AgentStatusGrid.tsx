import { AgentDetail } from '@/types'
import { Circle, CheckCircle, XCircle, Clock } from 'lucide-react'
import { format } from 'date-fns'

interface AgentStatusGridProps {
  agents: AgentDetail[]
}

const statusConfig = {
  active: {
    icon: Circle,
    color: 'text-green-600',
    bgColor: 'bg-green-50',
    borderColor: 'border-green-200',
  },
  idle: {
    icon: Clock,
    color: 'text-yellow-600',
    bgColor: 'bg-yellow-50',
    borderColor: 'border-yellow-200',
  },
  error: {
    icon: XCircle,
    color: 'text-red-600',
    bgColor: 'bg-red-50',
    borderColor: 'border-red-200',
  },
}

function AgentCard({ agent }: { agent: AgentDetail }) {
  const config = statusConfig[agent.status]
  const StatusIcon = config.icon

  return (
    <div
      className={`bg-white rounded-lg border-2 ${config.borderColor} p-4 hover:shadow-lg transition-all`}
    >
      <div className="flex items-start justify-between mb-3">
        <div>
          <h3 className="font-semibold text-gray-900">{agent.name}</h3>
          <p className="text-xs text-gray-500 mt-1">{agent.agent_id.slice(0, 8)}</p>
        </div>
        <div className={`p-2 rounded-lg ${config.bgColor}`}>
          <StatusIcon className={`h-5 w-5 ${config.color}`} />
        </div>
      </div>

      <div className="space-y-2 mb-3">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">Status</span>
          <span className={`font-medium ${config.color} capitalize`}>
            {agent.status}
          </span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">Active Tasks</span>
          <span className="font-medium text-gray-900">{agent.active_tasks}</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">Completed</span>
          <span className="font-medium text-green-600">{agent.tasks_completed}</span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">Failed</span>
          <span className="font-medium text-red-600">{agent.tasks_failed}</span>
        </div>
      </div>

      <div className="border-t border-gray-200 pt-3 space-y-2">
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">Cost Today</span>
          <span className="font-medium text-gray-900">
            ${agent.cost_today.toFixed(4)}
          </span>
        </div>
        <div className="flex items-center justify-between text-sm">
          <span className="text-gray-600">Last Seen</span>
          <span className="text-gray-500">
            {format(new Date(agent.last_seen), 'HH:mm:ss')}
          </span>
        </div>
      </div>

      {agent.error_message && (
        <div className="mt-3 p-2 bg-red-50 rounded border border-red-200">
          <p className="text-xs text-red-800">{agent.error_message}</p>
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-1">
        {agent.capabilities.map((cap) => (
          <span
            key={cap}
            className="inline-block px-2 py-1 text-xs font-medium bg-blue-50 text-blue-700 rounded"
          >
            {cap}
          </span>
        ))}
      </div>
    </div>
  )
}

export function AgentStatusGrid({ agents }: AgentStatusGridProps) {
  if (agents.length === 0) {
    return (
      <div className="bg-white rounded-lg border border-gray-200 p-12 text-center">
        <CheckCircle className="h-12 w-12 mx-auto mb-3 text-gray-300" />
        <p className="text-gray-900 font-medium">No agents registered</p>
        <p className="text-gray-500 text-sm mt-1">
          Agents will appear here once they register with the platform
        </p>
      </div>
    )
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {agents.map((agent) => (
        <AgentCard key={agent.agent_id} agent={agent} />
      ))}
    </div>
  )
}
