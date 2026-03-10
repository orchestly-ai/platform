import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import type { Alert } from '@/types'
import { AlertTriangle, CheckCircle, Clock } from 'lucide-react'
import { format } from 'date-fns'

export function AlertsPage() {
  const { data: alertsData, isLoading } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => api.getAlerts(),
  })

  const { data: alertStats } = useQuery({
    queryKey: ['alertStats'],
    queryFn: () => api.getAlertStats(),
  })

  if (isLoading) {
    return <div>Loading...</div>
  }

  const alerts = alertsData || []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Alerts</h1>
        <p className="text-gray-600 mt-1">
          Monitor and manage system alerts
        </p>
      </div>

      {alertStats && (
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="bg-white rounded-lg border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Active Alerts</span>
              <AlertTriangle className="h-5 w-5 text-yellow-600" />
            </div>
            <p className="text-2xl font-bold text-gray-900 mt-2">
              {alertStats.active.total}
            </p>
          </div>

          <div className="bg-red-50 rounded-lg border border-red-200 p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-red-700">Critical</span>
              <AlertTriangle className="h-5 w-5 text-red-600" />
            </div>
            <p className="text-2xl font-bold text-red-900 mt-2">
              {alertStats.active.critical}
            </p>
          </div>

          <div className="bg-yellow-50 rounded-lg border border-yellow-200 p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-yellow-700">Warnings</span>
              <AlertTriangle className="h-5 w-5 text-yellow-600" />
            </div>
            <p className="text-2xl font-bold text-yellow-900 mt-2">
              {alertStats.active.warning}
            </p>
          </div>

          <div className="bg-gray-50 rounded-lg border border-gray-200 p-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-600">Last 24h</span>
              <Clock className="h-5 w-5 text-gray-600" />
            </div>
            <p className="text-2xl font-bold text-gray-900 mt-2">
              {alertStats.last_24h.total}
            </p>
          </div>
        </div>
      )}

      <div className="bg-white rounded-lg border border-gray-200">
        <div className="p-6 border-b border-gray-200">
          <h2 className="text-lg font-semibold text-gray-900">Active Alerts</h2>
        </div>

        {alerts.length === 0 ? (
          <div className="p-8 text-center">
            <CheckCircle className="h-12 w-12 mx-auto mb-3 text-green-500" />
            <p className="text-gray-900 font-medium">No active alerts</p>
            <p className="text-gray-500 text-sm mt-1">
              All systems operating normally
            </p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200">
            {alerts.map((alert: Alert) => (
              <div key={alert.alert_id} className="p-4 hover:bg-gray-50">
                <div className="flex items-start justify-between">
                  <div className="flex items-start space-x-3">
                    <div className={`
                      p-2 rounded-lg
                      ${alert.severity === 'critical' ? 'bg-red-100' :
                        alert.severity === 'warning' ? 'bg-yellow-100' :
                        'bg-blue-100'}
                    `}>
                      <AlertTriangle className={`h-5 w-5
                        ${alert.severity === 'critical' ? 'text-red-600' :
                          alert.severity === 'warning' ? 'text-yellow-600' :
                          'text-blue-600'}
                      `} />
                    </div>
                    <div>
                      <h3 className="font-medium text-gray-900">{alert.message}</h3>
                      <p className="text-sm text-gray-500 mt-1">
                        {format(new Date(alert.created_at), 'MMM d, yyyy h:mm a')}
                      </p>
                    </div>
                  </div>
                  <span className={`
                    px-2 py-1 rounded text-xs font-medium
                    ${alert.severity === 'critical' ? 'bg-red-100 text-red-800' :
                      alert.severity === 'warning' ? 'bg-yellow-100 text-yellow-800' :
                      'bg-blue-100 text-blue-800'}
                  `}>
                    {alert.severity}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
