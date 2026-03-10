import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { DollarSign } from 'lucide-react'
import { format } from 'date-fns'

export function CostChart() {
  const { data: costData } = useQuery({
    queryKey: ['timeseries', 'cost'],
    queryFn: () => api.getCostTimeSeries(),
  })

  const { data: metrics } = useQuery({
    queryKey: ['systemMetrics'],
    queryFn: () => api.getSystemMetrics(),
  })

  const chartData = costData?.map((point) => ({
    time: format(new Date(point.timestamp), 'HH:mm'),
    cost: parseFloat(point.cost.toFixed(4)),
  }))

  const totalCost = metrics?.costs.today ?? 0

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Cost Trends</h2>
          <p className="text-sm text-gray-500 mt-1">
            ${totalCost.toFixed(4)} today • Last 60 minutes
          </p>
        </div>
        <DollarSign className="h-6 w-6 text-purple-600" />
      </div>

      {!chartData || chartData.length === 0 ? (
        <div className="h-64 flex items-center justify-center text-gray-500">
          <div className="text-center">
            <DollarSign className="h-12 w-12 mx-auto mb-3 text-gray-300" />
            <p>No cost data yet</p>
            <p className="text-sm mt-1">Data will appear as API calls are made</p>
          </div>
        </div>
      ) : (
        <ResponsiveContainer width="100%" height={250}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
            <XAxis
              dataKey="time"
              tick={{ fill: '#6b7280', fontSize: 12 }}
              tickLine={{ stroke: '#e5e7eb' }}
            />
            <YAxis
              tick={{ fill: '#6b7280', fontSize: 12 }}
              tickLine={{ stroke: '#e5e7eb' }}
              tickFormatter={(value) => `$${value}`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#fff',
                border: '1px solid #e5e7eb',
                borderRadius: '0.5rem',
              }}
              formatter={(value: number) => [`$${value.toFixed(4)}`, 'Cost']}
            />
            <Line
              type="monotone"
              dataKey="cost"
              stroke="#9333ea"
              strokeWidth={2}
              dot={{ fill: '#9333ea', r: 3 }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      )}
    </div>
  )
}
