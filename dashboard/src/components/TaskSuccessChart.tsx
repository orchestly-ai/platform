import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { TrendingUp } from 'lucide-react'

export function TaskSuccessChart() {
  const { data: metrics } = useQuery({
    queryKey: ['systemMetrics'],
    queryFn: () => api.getSystemMetrics(),
  })

  const chartData = [
    { name: 'Completed', value: metrics?.tasks.completed || 0, fill: '#10b981' },
    { name: 'Failed', value: metrics?.tasks.failed || 0, fill: '#ef4444' },
  ]

  const successRate = metrics?.tasks.success_rate
    ? (metrics.tasks.success_rate * 100).toFixed(1)
    : '0'

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Task Success Rate</h2>
          <p className="text-sm text-gray-500 mt-1">
            {successRate}% success • All time
          </p>
        </div>
        <TrendingUp className="h-6 w-6 text-green-600" />
      </div>

      {!metrics || (metrics.tasks.completed === 0 && metrics.tasks.failed === 0) ? (
        <div className="h-64 flex items-center justify-center text-gray-500">
          <div className="text-center">
            <TrendingUp className="h-12 w-12 mx-auto mb-3 text-gray-300" />
            <p>No task data yet</p>
            <p className="text-sm mt-1">Data will appear as tasks complete</p>
          </div>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="name"
              tick={{ fill: '#6b7280', fontSize: 12 }}
              tickLine={{ stroke: '#e5e7eb' }}
            />
            <YAxis
              tick={{ fill: '#6b7280', fontSize: 12 }}
              tickLine={{ stroke: '#e5e7eb' }}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #e5e7eb',
                borderRadius: '0.5rem',
              }}
            />
            <Bar dataKey="value" radius={[8, 8, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
