/**
 * AuditLogs Page - View system audit trail
 *
 * Features:
 * - Searchable log table with advanced filtering
 * - Time range filters
 * - Severity indicators
 * - Log detail modal with diff view
 * - Export functionality (CSV/JSON)
 * - Real-time activity indicator
 * - Stats summary cards
 */

import { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import { UpgradeBanner } from '@/components/UpgradeBanner'
import {
  FileText,
  Activity,
  Search,
  Download,
  ChevronRight,
  X,
  User,
  Clock,
  Globe,
  Calendar,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Info,
  Shield,
  RefreshCw,
  Filter,
  TrendingUp,
  Users,
} from 'lucide-react'
import type { AuditLogEntry } from '@/types/llm'

// Severity configuration
const SEVERITY_CONFIG: Record<string, { icon: typeof Info; color: string; bgColor: string; label: string }> = {
  info: { icon: Info, color: 'text-blue-600', bgColor: 'bg-blue-100', label: 'Info' },
  success: { icon: CheckCircle, color: 'text-green-600', bgColor: 'bg-green-100', label: 'Success' },
  warning: { icon: AlertTriangle, color: 'text-yellow-600', bgColor: 'bg-yellow-100', label: 'Warning' },
  error: { icon: XCircle, color: 'text-red-600', bgColor: 'bg-red-100', label: 'Error' },
  security: { icon: Shield, color: 'text-purple-600', bgColor: 'bg-purple-100', label: 'Security' },
}

// Time range options
const TIME_RANGES = [
  { value: 'today', label: 'Today' },
  { value: '7days', label: 'Last 7 Days' },
  { value: '30days', label: 'Last 30 Days' },
  { value: '90days', label: 'Last 90 Days' },
  { value: 'all', label: 'All Time' },
]

// Action to severity mapping
const ACTION_SEVERITY: Record<string, string> = {
  routing_strategy_changed: 'info',
  approval_granted: 'success',
  approval_rejected: 'warning',
  budget_alert_created: 'warning',
  agent_deployed: 'success',
  experiment_started: 'info',
  experiment_stopped: 'info',
  config_updated: 'info',
  login_failed: 'error',
  permission_denied: 'security',
  api_key_rotated: 'security',
  user_created: 'info',
  user_deleted: 'warning',
}

function LogDetailModal({
  log,
  onClose,
}: {
  log: AuditLogEntry
  onClose: () => void
}) {
  const severity = ACTION_SEVERITY[log.action] || 'info'
  const SeverityIcon = SEVERITY_CONFIG[severity]?.icon || Info

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-3xl w-full mx-4 max-h-[90vh] overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${SEVERITY_CONFIG[severity]?.bgColor}`}>
              <SeverityIcon className={`h-5 w-5 ${SEVERITY_CONFIG[severity]?.color}`} />
            </div>
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Log Details</h2>
              <p className="text-sm text-gray-500">{log.id}</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="h-5 w-5 text-gray-500" />
          </button>
        </div>

        <div className="p-6 overflow-y-auto max-h-[calc(90vh-8rem)]">
          {/* Metadata Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <User className="h-4 w-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-500">User</p>
                <p className="text-sm font-medium text-gray-900">{log.user}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Clock className="h-4 w-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-500">Timestamp</p>
                <p className="text-sm font-medium text-gray-900">
                  {new Date(log.timestamp).toLocaleString()}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Activity className="h-4 w-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-500">Action</p>
                <p className="text-sm font-medium text-gray-900">{log.action.replace(/_/g, ' ')}</p>
              </div>
            </div>
            <div className="flex items-center gap-3 p-3 bg-gray-50 rounded-lg">
              <Globe className="h-4 w-4 text-gray-400" />
              <div>
                <p className="text-xs text-gray-500">IP Address</p>
                <p className="text-sm font-medium text-gray-900">{log.ip}</p>
              </div>
            </div>
          </div>

          {/* Details */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-700 mb-2 flex items-center gap-2">
              <FileText className="h-4 w-4" />
              Details
            </h3>
            <pre className="bg-gray-900 text-gray-100 rounded-lg p-4 text-sm overflow-auto font-mono">
              {JSON.stringify(log.details, null, 2)}
            </pre>
          </div>

          {/* Before/After Diff */}
          {(log.before || log.after) && (
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-2">Changes</h3>
              <div className="grid grid-cols-2 gap-4">
                {log.before && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-medium text-red-600 bg-red-100 px-2 py-0.5 rounded">Before</span>
                    </div>
                    <pre className="bg-red-50 border border-red-200 rounded-lg p-4 text-xs text-gray-700 overflow-auto font-mono">
                      {JSON.stringify(log.before, null, 2)}
                    </pre>
                  </div>
                )}
                {log.after && (
                  <div>
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-xs font-medium text-green-600 bg-green-100 px-2 py-0.5 rounded">After</span>
                    </div>
                    <pre className="bg-green-50 border border-green-200 rounded-lg p-4 text-xs text-gray-700 overflow-auto font-mono">
                      {JSON.stringify(log.after, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        <div className="flex justify-end px-6 py-4 border-t border-gray-200 bg-gray-50">
          <button
            onClick={onClose}
            className="px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-200 rounded-lg transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  )
}

const actionLabels: Record<string, { label: string; color: string }> = {
  routing_strategy_changed: { label: 'Strategy Changed', color: 'blue' },
  approval_granted: { label: 'Approval Granted', color: 'green' },
  approval_rejected: { label: 'Approval Rejected', color: 'red' },
  budget_alert_created: { label: 'Budget Alert', color: 'yellow' },
  agent_deployed: { label: 'Agent Deployed', color: 'purple' },
  experiment_started: { label: 'Experiment Started', color: 'indigo' },
  experiment_stopped: { label: 'Experiment Stopped', color: 'gray' },
  config_updated: { label: 'Config Updated', color: 'cyan' },
  login_failed: { label: 'Login Failed', color: 'red' },
  permission_denied: { label: 'Permission Denied', color: 'red' },
  api_key_rotated: { label: 'API Key Rotated', color: 'purple' },
  user_created: { label: 'User Created', color: 'green' },
  user_deleted: { label: 'User Deleted', color: 'orange' },
}

export function AuditLogsPage() {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedLog, setSelectedLog] = useState<AuditLogEntry | null>(null)
  const [actionFilter, setActionFilter] = useState<string>('')
  const [userFilter, setUserFilter] = useState<string>('')
  const [timeRange, setTimeRange] = useState<string>('7days')
  const [severityFilter, setSeverityFilter] = useState<string>('')
  const [phiOnly, setPhiOnly] = useState(false)
  const [showFilters, setShowFilters] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [exportFormat, setExportFormat] = useState<'csv' | 'json'>('csv')
  const [lastUpdate, setLastUpdate] = useState(new Date())

  const { data: orgPlan } = useQuery({
    queryKey: ['orgPlan'],
    queryFn: () => api.getOrgPlan(),
    staleTime: 60_000,
  })
  const isAdvancedAuditGated = orgPlan && !orgPlan.enabled_features.includes('advanced_audit')

  const { data: logs, isLoading, refetch } = useQuery({
    queryKey: ['auditLogs', actionFilter, userFilter, timeRange],
    queryFn: () => api.getAuditLogs({
      action: actionFilter || undefined,
      user: userFilter || undefined,
      limit: 100,
    }),
    refetchInterval: 30000, // Auto-refresh every 30 seconds
  })

  useEffect(() => {
    if (logs) {
      setLastUpdate(new Date())
    }
  }, [logs])

  const handleExport = () => {
    if (!filteredLogs || filteredLogs.length === 0) return
    setIsExporting(true)

    setTimeout(() => {
      if (exportFormat === 'csv') {
        const headers = ['Timestamp', 'Action', 'User', 'IP', 'Details']
        const rows = filteredLogs.map(log => [
          new Date(log.timestamp).toISOString(),
          log.action,
          log.user,
          log.ip,
          JSON.stringify(log.details),
        ])
        const csv = [headers.join(','), ...rows.map(r => r.map(c => `"${c}"`).join(','))].join('\n')
        downloadFile(csv, 'audit-logs.csv', 'text/csv')
      } else {
        const json = JSON.stringify(filteredLogs, null, 2)
        downloadFile(json, 'audit-logs.json', 'application/json')
      }
      setIsExporting(false)
    }, 500)
  }

  const downloadFile = (content: string, filename: string, type: string) => {
    const blob = new Blob([content], { type })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  const filteredLogs = logs?.filter((log) => {
    const matchesSearch =
      log.action.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.user.toLowerCase().includes(searchQuery.toLowerCase())

    const logSeverity = ACTION_SEVERITY[log.action] || 'info'
    const matchesSeverity = !severityFilter || logSeverity === severityFilter

    const matchesPhi = !phiOnly || (log as any).pii_accessed === true

    return matchesSearch && matchesSeverity && matchesPhi
  })

  // Calculate stats
  const stats = {
    total: filteredLogs?.length || 0,
    info: filteredLogs?.filter(l => (ACTION_SEVERITY[l.action] || 'info') === 'info').length || 0,
    success: filteredLogs?.filter(l => ACTION_SEVERITY[l.action] === 'success').length || 0,
    warning: filteredLogs?.filter(l => ACTION_SEVERITY[l.action] === 'warning').length || 0,
    error: filteredLogs?.filter(l => ACTION_SEVERITY[l.action] === 'error').length || 0,
    security: filteredLogs?.filter(l => ACTION_SEVERITY[l.action] === 'security').length || 0,
    uniqueUsers: new Set(filteredLogs?.map(l => l.user)).size,
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Activity className="h-12 w-12 mx-auto mb-3 text-blue-600 animate-pulse" />
          <p className="text-gray-600">Loading audit logs...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {isAdvancedAuditGated && <UpgradeBanner feature="Advanced Audit (export, reports, retention)" />}
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
            <FileText className="h-7 w-7 text-gray-600" />
            Audit Logs
          </h1>
          <p className="text-gray-600 mt-1">
            Track all system changes and user actions
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Last Updated */}
          <span className="text-sm text-gray-500 flex items-center gap-1">
            <Clock className="h-4 w-4" />
            Updated {lastUpdate.toLocaleTimeString()}
          </span>
          <button
            onClick={() => refetch()}
            className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg"
            title="Refresh"
          >
            <RefreshCw className="h-4 w-4" />
          </button>
          {/* Export Dropdown */}
          <div className="relative">
            <div className="flex items-center border border-gray-200 rounded-lg overflow-hidden">
              <select
                value={exportFormat}
                onChange={(e) => setExportFormat(e.target.value as 'csv' | 'json')}
                className="px-3 py-2 text-sm border-none bg-transparent focus:ring-0"
              >
                <option value="csv">CSV</option>
                <option value="json">JSON</option>
              </select>
              <button
                onClick={handleExport}
                disabled={isExporting || !filteredLogs?.length || !!isAdvancedAuditGated}
                title={isAdvancedAuditGated ? 'Requires Enterprise license' : undefined}
                className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-gray-600 hover:bg-gray-100 transition-colors border-l border-gray-200 disabled:opacity-50"
              >
                <Download className="h-4 w-4" />
                Export
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-6 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Total Logs</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
            </div>
            <FileText className="h-8 w-8 text-gray-400" />
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Unique Users</p>
              <p className="text-2xl font-bold text-gray-900">{stats.uniqueUsers}</p>
            </div>
            <Users className="h-8 w-8 text-blue-400" />
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Success</p>
              <p className="text-2xl font-bold text-green-600">{stats.success}</p>
            </div>
            <CheckCircle className="h-8 w-8 text-green-400" />
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Warnings</p>
              <p className="text-2xl font-bold text-yellow-600">{stats.warning}</p>
            </div>
            <AlertTriangle className="h-8 w-8 text-yellow-400" />
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Errors</p>
              <p className="text-2xl font-bold text-red-600">{stats.error}</p>
            </div>
            <XCircle className="h-8 w-8 text-red-400" />
          </div>
        </div>
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-500">Security</p>
              <p className="text-2xl font-bold text-purple-600">{stats.security}</p>
            </div>
            <Shield className="h-8 w-8 text-purple-400" />
          </div>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="space-y-4">
        <div className="flex gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search by action or user..."
              className="w-full pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>
          <div className="flex items-center gap-2">
            <select
              value={timeRange}
              onChange={(e) => setTimeRange(e.target.value)}
              className="px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
            >
              {TIME_RANGES.map((range) => (
                <option key={range.value} value={range.value}>{range.label}</option>
              ))}
            </select>
            <button
              onClick={() => setPhiOnly(!phiOnly)}
              className={`flex items-center gap-2 px-4 py-2 border rounded-lg text-sm ${
                phiOnly ? 'border-purple-500 text-purple-600 bg-purple-50' : 'border-gray-200 text-gray-600'
              }`}
              title="Show only events with PHI access"
            >
              <Shield className="h-4 w-4" />
              PHI Only
            </button>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-2 px-4 py-2 border rounded-lg text-sm ${
                showFilters ? 'border-blue-500 text-blue-600 bg-blue-50' : 'border-gray-200 text-gray-600'
              }`}
            >
              <Filter className="h-4 w-4" />
              Filters
            </button>
          </div>
        </div>

        {/* Advanced Filters */}
        {showFilters && (
          <div className="flex gap-4 p-4 bg-gray-50 rounded-lg border border-gray-200">
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">Action</label>
              <select
                value={actionFilter}
                onChange={(e) => setActionFilter(e.target.value)}
                className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
              >
                <option value="">All Actions</option>
                {Object.entries(actionLabels).map(([key, config]) => (
                  <option key={key} value={key}>{config.label}</option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">Severity</label>
              <select
                value={severityFilter}
                onChange={(e) => setSeverityFilter(e.target.value)}
                className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
              >
                <option value="">All Severities</option>
                {Object.entries(SEVERITY_CONFIG).map(([key, config]) => (
                  <option key={key} value={key}>{config.label}</option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <label className="block text-sm font-medium text-gray-700 mb-1">User</label>
              <input
                type="text"
                value={userFilter}
                onChange={(e) => setUserFilter(e.target.value)}
                placeholder="Enter user email or ID..."
                className="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
              />
            </div>
          </div>
        )}
      </div>

      {/* Logs Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50 border-b border-gray-200">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Severity
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Timestamp
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Action
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                User
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                IP
              </th>
              <th className="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                Details
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filteredLogs?.map((log) => {
              const actionConfig = actionLabels[log.action] || {
                label: log.action.replace(/_/g, ' '),
                color: 'gray',
              }
              const severity = ACTION_SEVERITY[log.action] || 'info'
              const SeverityIcon = SEVERITY_CONFIG[severity]?.icon || Info

              return (
                <tr key={log.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className={`inline-flex items-center justify-center w-8 h-8 rounded-lg ${SEVERITY_CONFIG[severity]?.bgColor}`}>
                      <SeverityIcon className={`h-4 w-4 ${SEVERITY_CONFIG[severity]?.color}`} />
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <div>
                      <p>{new Date(log.timestamp).toLocaleDateString()}</p>
                      <p className="text-xs text-gray-400">{new Date(log.timestamp).toLocaleTimeString()}</p>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <span
                        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-${actionConfig.color}-100 text-${actionConfig.color}-800`}
                      >
                        {actionConfig.label}
                      </span>
                      {(log as any).pii_accessed && (
                        <span className="inline-flex items-center justify-center w-5 h-5 rounded bg-purple-100" title="PHI Accessed">
                          <Shield className="h-3 w-3 text-purple-600" />
                        </span>
                      )}
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="flex items-center gap-2">
                      <div className="w-6 h-6 bg-gray-200 rounded-full flex items-center justify-center text-xs font-medium text-gray-600">
                        {log.user.charAt(0).toUpperCase()}
                      </div>
                      <span className="text-sm text-gray-900">{log.user}</span>
                    </div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-mono">
                    {log.ip}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-right">
                    <button
                      onClick={() => setSelectedLog(log)}
                      className="inline-flex items-center gap-1 text-sm text-blue-600 hover:text-blue-800"
                    >
                      View
                      <ChevronRight className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>

        {filteredLogs?.length === 0 && (
          <div className="p-12 text-center">
            <FileText className="h-12 w-12 mx-auto text-gray-300 mb-4" />
            <p className="text-gray-500">No logs found matching your search</p>
          </div>
        )}
      </div>

      {/* Pagination */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-gray-500">
          Showing {filteredLogs?.length || 0} of {logs?.length || 0} entries
        </p>
        <div className="flex items-center gap-2">
          <button className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded border border-gray-200">
            Previous
          </button>
          <span className="px-3 py-1.5 text-sm bg-blue-50 text-blue-600 rounded border border-blue-200">1</span>
          <button className="px-3 py-1.5 text-sm text-gray-600 hover:bg-gray-100 rounded border border-gray-200">
            Next
          </button>
        </div>
      </div>

      {/* Detail Modal */}
      {selectedLog && (
        <LogDetailModal log={selectedLog} onClose={() => setSelectedLog(null)} />
      )}
    </div>
  )
}

export default AuditLogsPage
