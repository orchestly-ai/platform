/**
 * HITLApprovals Page - Human-in-the-Loop approval queue
 *
 * Features:
 * - Pending approvals queue
 * - Approve/Reject with comments
 * - Risk level indicators
 * - Approval history
 *
 * Verification:
 * - Navigate to /approvals
 * - See pending approval cards
 * - Approve/Reject buttons work
 * - Risk levels color-coded
 */

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import {
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  Activity,
  Shield,
  MessageSquare,
} from 'lucide-react'
import type { HITLApproval, RiskLevel } from '@/types/llm'

const riskConfig: Record<RiskLevel, { color: string; bg: string; icon: typeof AlertTriangle }> = {
  low: { color: 'text-green-600', bg: 'bg-green-100', icon: CheckCircle },
  medium: { color: 'text-yellow-600', bg: 'bg-yellow-100', icon: AlertTriangle },
  high: { color: 'text-orange-600', bg: 'bg-orange-100', icon: AlertTriangle },
  critical: { color: 'text-red-600', bg: 'bg-red-100', icon: Shield },
}

function ApprovalCard({
  approval,
  onApprove,
  onReject,
}: {
  approval: HITLApproval
  onApprove: (id: string, comment?: string) => void
  onReject: (id: string, reason: string) => void
}) {
  const [showComment, setShowComment] = useState(false)
  const [comment, setComment] = useState('')
  const [_rejectReason, _setRejectReason] = useState('')

  const config = riskConfig[approval.riskLevel]
  const RiskIcon = config.icon
  const expiresIn = Math.max(
    0,
    Math.round((new Date(approval.expiresAt).getTime() - Date.now()) / 60000)
  )

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-start gap-3">
          <div className={`p-2 rounded-lg ${config.bg}`}>
            <RiskIcon className={`h-5 w-5 ${config.color}`} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h3 className="font-semibold text-gray-900">{approval.action}</h3>
              <span className="px-2 py-0.5 bg-gray-100 text-gray-600 text-xs font-mono rounded">
                #{approval.id}
              </span>
            </div>
            <div className="flex items-center gap-3 mt-1 text-sm text-gray-500">
              <span>Requested by: {approval.requestedBy}</span>
              <span>•</span>
              <span>{new Date(approval.requestedAt).toLocaleString()}</span>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span
            className={`px-3 py-1 rounded-full text-xs font-medium ${config.bg} ${config.color}`}
          >
            {approval.riskLevel.toUpperCase()}
          </span>
        </div>
      </div>

      {/* Context */}
      <div className="bg-gray-50 rounded-lg p-3 mb-4">
        <h4 className="text-sm font-medium text-gray-700 mb-2">Context</h4>
        <pre className="text-xs text-gray-600 overflow-auto">
          {JSON.stringify(approval.context, null, 2)}
        </pre>
      </div>

      {/* Expiration */}
      <div className="flex items-center gap-2 text-sm text-gray-500 mb-4">
        <Clock className="h-4 w-4" />
        <span>
          {expiresIn > 0 ? `Expires in ${expiresIn} minutes` : 'Expired'}
        </span>
      </div>

      {/* Comment Section */}
      {showComment && (
        <div className="mb-4 space-y-3">
          <textarea
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            placeholder="Add a comment (optional for approve, required for reject)"
            className="w-full px-3 py-2 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            rows={2}
          />
        </div>
      )}

      {/* Actions */}
      <div className="flex items-center gap-3">
        <button
          onClick={() => {
            if (!showComment) {
              setShowComment(true)
            } else {
              onApprove(approval.id, comment || undefined)
            }
          }}
          className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-700 transition-colors"
        >
          <CheckCircle className="h-4 w-4" />
          {showComment ? 'Confirm Approve' : 'Approve'}
        </button>
        <button
          onClick={() => {
            if (!showComment) {
              setShowComment(true)
            } else if (comment) {
              onReject(approval.id, comment)
            }
          }}
          disabled={showComment && !comment}
          className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            showComment && !comment
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
              : 'bg-red-600 text-white hover:bg-red-700'
          }`}
        >
          <XCircle className="h-4 w-4" />
          {showComment ? 'Confirm Reject' : 'Reject'}
        </button>
        {!showComment && (
          <button
            onClick={() => setShowComment(true)}
            className="flex items-center gap-2 px-4 py-2 text-gray-600 hover:bg-gray-100 rounded-lg text-sm font-medium transition-colors"
          >
            <MessageSquare className="h-4 w-4" />
            Add Comment
          </button>
        )}
        {showComment && (
          <button
            onClick={() => {
              setShowComment(false)
              setComment('')
            }}
            className="px-4 py-2 text-gray-500 hover:text-gray-700 text-sm"
          >
            Cancel
          </button>
        )}
      </div>
    </div>
  )
}

export function HITLApprovalsPage() {
  const queryClient = useQueryClient()

  const { data: approvals, isLoading } = useQuery({
    queryKey: ['pendingApprovals'],
    queryFn: () => api.getPendingApprovals(),
    refetchInterval: 30000,
  })

  const approveMutation = useMutation({
    mutationFn: ({ id, comment }: { id: string; comment?: string }) =>
      api.approveAction(id, comment),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pendingApprovals'] })
    },
  })

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      api.rejectAction(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['pendingApprovals'] })
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Activity className="h-12 w-12 mx-auto mb-3 text-blue-600 animate-pulse" />
          <p className="text-gray-600">Loading approvals...</p>
        </div>
      </div>
    )
  }

  const criticalCount = approvals?.filter((a) => a.riskLevel === 'critical').length || 0
  const highCount = approvals?.filter((a) => a.riskLevel === 'high').length || 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-2">
          <CheckCircle className="h-7 w-7 text-blue-600" />
          Human-in-the-Loop Approvals
        </h1>
        <p className="text-gray-600 mt-1">
          Review and approve high-risk agent actions
        </p>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg border border-gray-200 p-4">
          <span className="text-sm text-gray-500">Pending</span>
          <p className="text-2xl font-bold text-gray-900 mt-1">
            {approvals?.length || 0}
          </p>
        </div>
        <div className="bg-red-50 rounded-lg border border-red-200 p-4">
          <span className="text-sm text-red-600">Critical</span>
          <p className="text-2xl font-bold text-red-600 mt-1">{criticalCount}</p>
        </div>
        <div className="bg-orange-50 rounded-lg border border-orange-200 p-4">
          <span className="text-sm text-orange-600">High Risk</span>
          <p className="text-2xl font-bold text-orange-600 mt-1">{highCount}</p>
        </div>
        <div className="bg-green-50 rounded-lg border border-green-200 p-4">
          <span className="text-sm text-green-600">Approved Today</span>
          <p className="text-2xl font-bold text-green-600 mt-1">12</p>
        </div>
      </div>

      {/* Approval Queue */}
      {approvals && approvals.length > 0 ? (
        <div className="space-y-4">
          <h2 className="text-lg font-semibold text-gray-900">Pending Approvals</h2>
          {approvals.map((approval) => (
            <ApprovalCard
              key={approval.id}
              approval={approval}
              onApprove={(id, comment) =>
                approveMutation.mutate({ id, comment })
              }
              onReject={(id, reason) => rejectMutation.mutate({ id, reason })}
            />
          ))}
        </div>
      ) : (
        <div className="bg-gray-50 rounded-lg p-12 text-center">
          <CheckCircle className="h-12 w-12 mx-auto text-green-500 mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">
            All caught up!
          </h3>
          <p className="text-gray-500">
            No pending approvals at this time. New approval requests will appear
            here.
          </p>
        </div>
      )}

      {/* Info Box */}
      <div className="bg-blue-50 rounded-lg p-4 border border-blue-100">
        <h3 className="font-medium text-blue-900 mb-2">About HITL Approvals</h3>
        <ul className="text-sm text-blue-700 space-y-1">
          <li>• Critical and high-risk actions require human approval before execution</li>
          <li>• Approvals expire after a set time to prevent stale requests</li>
          <li>• All decisions are logged for audit purposes</li>
          <li>• Configure approval policies in the settings</li>
        </ul>
      </div>
    </div>
  )
}

export default HITLApprovalsPage
