import { AlertStats } from '@/types'
import { AlertTriangle, XCircle, Info } from 'lucide-react'
import { Link } from 'react-router-dom'

interface AlertBannerProps {
  alertStats: AlertStats
}

export function AlertBanner({ alertStats }: AlertBannerProps) {
  if (alertStats.active.total === 0) {
    return null
  }

  const { critical, warning, info } = alertStats.active

  return (
    <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <AlertTriangle className="h-5 w-5 text-yellow-600" />
          <div>
            <h3 className="font-semibold text-yellow-900">
              {alertStats.active.total} Active Alert{alertStats.active.total !== 1 ? 's' : ''}
            </h3>
            <div className="flex items-center space-x-4 mt-1 text-sm">
              {critical > 0 && (
                <span className="flex items-center space-x-1 text-red-700">
                  <XCircle className="h-4 w-4" />
                  <span>{critical} Critical</span>
                </span>
              )}
              {warning > 0 && (
                <span className="flex items-center space-x-1 text-yellow-700">
                  <AlertTriangle className="h-4 w-4" />
                  <span>{warning} Warning</span>
                </span>
              )}
              {info > 0 && (
                <span className="flex items-center space-x-1 text-blue-700">
                  <Info className="h-4 w-4" />
                  <span>{info} Info</span>
                </span>
              )}
            </div>
          </div>
        </div>
        <Link
          to="/alerts"
          className="px-4 py-2 bg-yellow-600 text-white rounded-lg hover:bg-yellow-700 transition-colors text-sm font-medium"
        >
          View Alerts
        </Link>
      </div>
    </div>
  )
}
