import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import { MetricsCard } from '@/components/MetricsCard'
import { AgentStatusGrid } from '@/components/AgentStatusGrid'
import { QueueVisualization } from '@/components/QueueVisualization'
import { CostChart } from '@/components/CostChart'
import { TaskSuccessChart } from '@/components/TaskSuccessChart'
import { AlertBanner } from '@/components/AlertBanner'
import { Users, CheckCircle, DollarSign, Activity } from 'lucide-react'

export function DashboardPage() {
  const { data: metrics, isLoading } = useQuery({
    queryKey: ['systemMetrics'],
    queryFn: () => api.getSystemMetrics(),
  })

  const { data: alertStats } = useQuery({
    queryKey: ['alertStats'],
    queryFn: () => api.getAlertStats(),
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Activity className="h-12 w-12 mx-auto mb-3 text-blue-600 animate-pulse" />
          <p className="text-gray-600">Loading dashboard...</p>
        </div>
      </div>
    )
  }

  if (!metrics) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-600">Unable to load metrics</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="text-gray-600 mt-1">
          Real-time system overview and monitoring
        </p>
      </div>

      {alertStats && <AlertBanner alertStats={alertStats} />}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricsCard
          title="Active Agents"
          value={metrics.agents.active}
          subtitle={`${metrics.agents.total} total`}
          icon={Users}
          color="blue"
        />
        <MetricsCard
          title="Agent Utilization"
          value={`${(metrics.agents.utilization * 100).toFixed(1)}%`}
          subtitle="Average across all agents"
          icon={Activity}
          color="green"
        />
        <MetricsCard
          title="Tasks Completed"
          value={metrics.tasks.completed}
          subtitle={`${(metrics.tasks.success_rate * 100).toFixed(1)}% success rate`}
          icon={CheckCircle}
          color="green"
        />
        <MetricsCard
          title="Cost Today"
          value={`$${metrics.costs.today.toFixed(4)}`}
          subtitle={`$${metrics.costs.month.toFixed(2)} this month`}
          icon={DollarSign}
          color="purple"
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <TaskSuccessChart />
        <CostChart />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <div className="mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Agent Status</h2>
            <p className="text-sm text-gray-500 mt-1">
              Monitor all registered agents
            </p>
          </div>
          <AgentStatusGrid agents={metrics.agents.details} />
        </div>

        <div className="lg:col-span-1">
          <QueueVisualization queues={metrics.queues} />
        </div>
      </div>
    </div>
  )
}
