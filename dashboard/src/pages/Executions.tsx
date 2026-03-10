/**
 * Executions Page - Monitor and debug agent & workflow executions
 * Fetches real execution data from the API
 */

import { useState, useEffect } from 'react';
import {
  Play,
  Search,
  CheckCircle,
  XCircle,
  Clock,
  ChevronRight,
  ChevronDown,
  Copy,
  RotateCcw,
  DollarSign,
  RefreshCw,
  Bot,
  GitBranch,
  AlertCircle,
  Loader2,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react';

interface ExecutionStep {
  id: string;
  name: string;
  type: 'llm' | 'integration' | 'conditional' | 'transform';
  status: 'success' | 'failed' | 'running' | 'pending';
  duration: string;
  cost: string;
  input?: string;
  output?: string;
  model?: string;
  tokens?: number;
}

interface NodeStateData {
  status: string;
  output?: unknown;
  duration?: number;
  cost?: number;
  ab_testing?: {
    assignment_id: number;
    experiment_id: number;
    variant_name: string;
  };
}

interface Execution {
  execution_id: string;
  workflow_id: string;
  workflow_name: string | null;
  workflow_version: number;
  organization_id: string;
  status: 'completed' | 'failed' | 'running' | 'pending' | 'cancelled' | 'timeout';
  triggered_by: string | null;
  trigger_source: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  input_data: Record<string, unknown> | null;
  output_data: Record<string, unknown> | null;
  error_message: string | null;
  error_node_id: string | null;
  retry_count: number;
  node_states: Record<string, NodeStateData>;
  total_cost: number;
  total_tokens: number | null;
  created_at: string;
}

// Track feedback given for each assignment
interface FeedbackState {
  [assignmentId: number]: 'positive' | 'negative' | 'pending';
}

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function ExecutionsPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'completed' | 'failed' | 'running' | 'pending'>('all');
  const [selectedExecution, setSelectedExecution] = useState<string | null>(null);
  const [expandedSteps, setExpandedSteps] = useState<Set<string>>(new Set());
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);
  const [feedbackState, setFeedbackState] = useState<FeedbackState>({});

  // Submit feedback for A/B testing
  const submitFeedback = async (assignmentId: number, positive: boolean) => {
    setFeedbackState(prev => ({ ...prev, [assignmentId]: 'pending' }));

    try {
      const response = await fetch(
        `${API_BASE_URL}/api/v1/experiments/assignments/${assignmentId}/feedback`,
        {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            assignment_id: assignmentId,
            positive: positive,
            rating: positive ? 5 : 1,
          }),
        }
      );

      if (response.ok) {
        setFeedbackState(prev => ({ ...prev, [assignmentId]: positive ? 'positive' : 'negative' }));
      } else {
        // Reset on error
        setFeedbackState(prev => {
          const newState = { ...prev };
          delete newState[assignmentId];
          return newState;
        });
        console.error('Failed to submit feedback');
      }
    } catch (err) {
      console.error('Error submitting feedback:', err);
      setFeedbackState(prev => {
        const newState = { ...prev };
        delete newState[assignmentId];
        return newState;
      });
    }
  };

  // Fetch executions from API
  const fetchExecutions = async () => {
    try {
      setError(null);
      const statusParam = statusFilter !== 'all' ? `&status=${statusFilter}` : '';
      const response = await fetch(`${API_BASE_URL}/api/workflows/executions?limit=50${statusParam}`);

      if (!response.ok) {
        throw new Error(`Failed to fetch executions: ${response.statusText}`);
      }

      const data = await response.json();
      setExecutions(data);

      // Auto-select first execution if none selected
      if (data.length > 0 && !selectedExecution) {
        setSelectedExecution(data[0].execution_id);
      }
    } catch (err) {
      console.error('Error fetching executions:', err);
      setError(err instanceof Error ? err.message : 'Failed to fetch executions');
    } finally {
      setLoading(false);
    }
  };

  // Initial fetch and refetch on filter change
  useEffect(() => {
    fetchExecutions();
  }, [statusFilter]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(fetchExecutions, 5000);
    return () => clearInterval(interval);
  }, [autoRefresh, statusFilter]);

  const filteredExecutions = executions.filter((exec) => {
    const matchesSearch =
      (exec.workflow_name?.toLowerCase().includes(searchQuery.toLowerCase()) || false) ||
      exec.execution_id.toLowerCase().includes(searchQuery.toLowerCase());
    return matchesSearch;
  });

  const selectedExecutionData = executions.find((e) => e.execution_id === selectedExecution);

  const toggleStep = (stepId: string) => {
    const newExpanded = new Set(expandedSteps);
    if (newExpanded.has(stepId)) {
      newExpanded.delete(stepId);
    } else {
      newExpanded.add(stepId);
    }
    setExpandedSteps(newExpanded);
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
      case 'success': return <CheckCircle size={14} className="status-icon success" />;
      case 'failed': return <XCircle size={14} className="status-icon failed" />;
      case 'running': return <RefreshCw size={14} className="status-icon running" />;
      case 'pending': return <Clock size={14} className="status-icon pending" />;
      case 'cancelled': return <XCircle size={14} className="status-icon" style={{ color: '#f59e0b' }} />;
      default: return <Clock size={14} className="status-icon pending" />;
    }
  };

  const getTypeIcon = (type: 'agent' | 'workflow') => {
    return type === 'agent' ? <Bot size={14} /> : <GitBranch size={14} />;
  };

  const getStepTypeColor = (type: string) => {
    switch (type) {
      case 'llm':
      case 'supervisor':
      case 'worker': return '#6366f1';
      case 'integration':
      case 'http': return '#10b981';
      case 'conditional':
      case 'condition': return '#f59e0b';
      case 'transform':
      case 'tool': return '#8b5cf6';
      default: return '#6366f1';
    }
  };

  const formatDuration = (seconds: number | null) => {
    if (seconds === null) return '-';
    if (seconds < 1) return `${Math.round(seconds * 1000)}ms`;
    return `${seconds.toFixed(1)}s`;
  };

  const formatCost = (cost: number) => {
    return `$${cost.toFixed(4)}`;
  };

  const formatTimeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMins = Math.floor(diffMs / 60000);

    if (diffMins < 1) return 'just now';
    if (diffMins < 60) return `${diffMins} min ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)} hours ago`;
    return `${Math.floor(diffMins / 1440)} days ago`;
  };

  // Convert node_states to steps for display
  const getStepsFromNodeStates = (nodeStates: Record<string, NodeStateData>) => {
    return Object.entries(nodeStates).map(([nodeId, state], index) => {
      // Check if output contains ab_testing data
      let abTesting: { assignment_id: number; experiment_id: number; variant_name: string } | undefined;
      if (state.output && typeof state.output === 'object') {
        const outputObj = state.output as Record<string, unknown>;
        if (outputObj.ab_testing) {
          abTesting = outputObj.ab_testing as { assignment_id: number; experiment_id: number; variant_name: string };
        }
      }

      return {
        id: `step-${index}`,
        name: nodeId,
        type: 'llm' as const,
        status: state.status === 'completed' ? 'success' as const :
                state.status === 'failed' ? 'failed' as const :
                state.status === 'running' ? 'running' as const : 'pending' as const,
        duration: formatDuration(state.duration || null),
        cost: formatCost(state.cost || 0),
        output: state.output ? JSON.stringify(state.output) : undefined,
        abTesting,
      };
    });
  };

  if (loading) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 'calc(100vh - 140px)' }}>
        <Loader2 size={48} className="animate-spin" style={{ color: 'var(--primary-color)', marginBottom: '16px' }} />
        <p style={{ color: 'var(--text-muted)' }}>Loading executions...</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 'calc(100vh - 140px)' }}>
        <AlertCircle size={48} style={{ color: 'var(--error-color)', marginBottom: '16px' }} />
        <h3 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 8px', color: 'var(--text-primary)' }}>Failed to load executions</h3>
        <p style={{ color: 'var(--text-muted)', marginBottom: '16px' }}>{error}</p>
        <button
          className="btn-primary"
          onClick={() => { setLoading(true); fetchExecutions(); }}
          style={{ display: 'flex', alignItems: 'center', gap: '8px' }}
        >
          <RefreshCw size={16} />
          Retry
        </button>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 140px)' }}>
      {/* Page Header */}
      <div className="page-header">
        <div className="page-title">
          <h1>Executions</h1>
          <p>Monitor and debug workflow executions in real-time</p>
        </div>
        <button
          className={`btn-secondary ${autoRefresh ? 'active' : ''}`}
          onClick={() => setAutoRefresh(!autoRefresh)}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
            background: autoRefresh ? 'rgba(99, 102, 241, 0.1)' : undefined,
            borderColor: autoRefresh ? 'var(--primary-color)' : undefined,
            color: autoRefresh ? 'var(--primary-color)' : undefined
          }}
        >
          <RefreshCw size={16} className={autoRefresh ? 'animate-spin' : ''} />
          {autoRefresh ? 'Auto-refreshing' : 'Auto-refresh'}
        </button>
      </div>

      {executions.length === 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', flex: 1, textAlign: 'center', padding: '40px' }}>
          <Play size={64} style={{ opacity: 0.3, marginBottom: '24px', color: 'var(--text-muted)' }} />
          <h2 style={{ fontSize: '20px', fontWeight: 600, margin: '0 0 8px', color: 'var(--text-primary)' }}>No executions yet</h2>
          <p style={{ color: 'var(--text-muted)', maxWidth: '400px' }}>
            Execute a workflow to see execution history here. Go to the Workflows page to create and execute workflows.
          </p>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '400px 1fr', gap: '20px', flex: 1, minHeight: 0 }}>
          {/* Executions List */}
          <div className="chart-card" style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', padding: 0 }}>
            <div style={{ padding: '16px', borderBottom: '1px solid var(--border-color)' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '6px', padding: '8px 12px', marginBottom: '12px' }}>
                <Search size={16} style={{ color: 'var(--text-muted)' }} />
                <input
                  type="text"
                  placeholder="Search executions..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  style={{ flex: 1, border: 'none', background: 'transparent', outline: 'none', fontSize: '13px', color: 'var(--text-primary)' }}
                />
              </div>
              <div style={{ display: 'flex', gap: '6px' }}>
                {(['all', 'completed', 'failed', 'running', 'pending'] as const).map((status) => (
                  <button
                    key={status}
                    onClick={() => setStatusFilter(status)}
                    style={{
                      padding: '4px 10px',
                      border: 'none',
                      background: statusFilter === status ? 'rgba(99, 102, 241, 0.1)' : 'transparent',
                      borderRadius: '4px',
                      fontSize: '12px',
                      fontWeight: 500,
                      color: statusFilter === status ? '#6366f1' : 'var(--text-muted)',
                      cursor: 'pointer',
                      textTransform: 'capitalize',
                    }}
                  >
                    {status}
                  </button>
                ))}
              </div>
            </div>

            <div style={{ flex: 1, overflowY: 'auto' }}>
              {filteredExecutions.map((exec) => (
                <div
                  key={exec.execution_id}
                  onClick={() => setSelectedExecution(exec.execution_id)}
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: '12px',
                    padding: '14px 16px',
                    borderBottom: '1px solid var(--border-color)',
                    cursor: 'pointer',
                    background: selectedExecution === exec.execution_id ? 'rgba(99, 102, 241, 0.08)' : 'transparent',
                    borderLeft: selectedExecution === exec.execution_id ? '3px solid var(--primary-color)' : 'none',
                  }}
                >
                  {getStatusIcon(exec.status)}
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div style={{ fontWeight: 500, color: 'var(--text-primary)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      {exec.workflow_name || 'Unknown Workflow'}
                    </div>
                    <div style={{ display: 'flex', gap: '8px', fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                      <span className="type-badge workflow" style={{ padding: '2px 6px', fontSize: '11px' }}>
                        {getTypeIcon('workflow')}
                        workflow
                      </span>
                      <span>{formatTimeAgo(exec.created_at)}</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '4px', fontSize: '11px', color: 'var(--text-muted)' }}>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><Clock size={12} />{formatDuration(exec.duration_seconds)}</span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}><DollarSign size={12} />{formatCost(exec.total_cost)}</span>
                  </div>
                  <ChevronRight size={16} style={{ color: 'var(--text-muted)' }} />
                </div>
              ))}
            </div>
          </div>

          {/* Execution Details */}
          <div className="chart-card" style={{ overflow: 'auto', padding: 0 }}>
            {selectedExecutionData ? (
              <>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '20px', borderBottom: '1px solid var(--border-color)', position: 'sticky', top: 0, background: 'var(--bg-primary)', zIndex: 10 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <h2 style={{ fontSize: '18px', fontWeight: 600, margin: 0 }}>{selectedExecutionData.workflow_name || 'Unknown Workflow'}</h2>
                    <span className="type-badge workflow">{getTypeIcon('workflow')}workflow</span>
                    <span className={`status-badge ${selectedExecutionData.status}`}>{getStatusIcon(selectedExecutionData.status)}{selectedExecutionData.status}</span>
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <button className="btn-secondary" style={{ padding: '8px' }} title="Copy execution ID" onClick={() => navigator.clipboard.writeText(selectedExecutionData.execution_id)}><Copy size={16} /></button>
                    <button className="btn-secondary" style={{ padding: '8px' }} title="Re-run execution"><RotateCcw size={16} /></button>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', padding: '16px 20px', background: 'var(--bg-secondary)', borderBottom: '1px solid var(--border-color)' }}>
                  {[
                    { label: 'Execution ID', value: selectedExecutionData.execution_id.slice(0, 8) + '...' },
                    { label: 'Triggered By', value: selectedExecutionData.triggered_by || 'Unknown' },
                    { label: 'Duration', value: formatDuration(selectedExecutionData.duration_seconds) },
                    { label: 'Total Cost', value: formatCost(selectedExecutionData.total_cost) },
                  ].map((meta) => (
                    <div key={meta.label}>
                      <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{meta.label}</div>
                      <div style={{ fontSize: '14px', fontWeight: 500, color: 'var(--text-primary)' }}>{meta.value}</div>
                    </div>
                  ))}
                </div>

                {/* Steps from node_states */}
                {selectedExecutionData.node_states && Object.keys(selectedExecutionData.node_states).length > 0 && (
                  <div style={{ padding: '20px' }}>
                    <h3 style={{ fontSize: '14px', fontWeight: 600, marginBottom: '16px' }}>Execution Trace ({Object.keys(selectedExecutionData.node_states).length} nodes)</h3>
                    {getStepsFromNodeStates(selectedExecutionData.node_states).map((step, index, arr) => (
                      <div key={step.id} style={{ display: 'flex', gap: '16px' }}>
                        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '16px' }}>
                          <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: step.status === 'success' ? getStepTypeColor(step.type) : step.status === 'failed' ? '#ef4444' : '#6366f1' }} />
                          {index < arr.length - 1 && <div style={{ width: '2px', flex: 1, background: 'var(--border-color)', margin: '4px 0' }} />}
                        </div>
                        <div
                          onClick={() => toggleStep(step.id)}
                          style={{ flex: 1, background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', marginBottom: '12px', cursor: 'pointer' }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                              <span style={{ fontSize: '10px', fontWeight: 600, padding: '3px 8px', borderRadius: '4px', background: `${getStepTypeColor(step.type)}15`, color: getStepTypeColor(step.type), textTransform: 'uppercase' }}>{step.type}</span>
                              <span style={{ fontWeight: 500 }}>{step.name}</span>
                              {getStatusIcon(step.status)}
                            </div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', fontSize: '12px', color: 'var(--text-muted)' }}>
                              <span>{step.duration}</span>
                              <span>{step.cost}</span>
                              {expandedSteps.has(step.id) ? <ChevronDown size={16} /> : <ChevronRight size={16} />}
                            </div>
                          </div>
                          {expandedSteps.has(step.id) && step.output && (
                            <div style={{ padding: '0 16px 16px', borderTop: '1px solid var(--border-color)' }}>
                              <div style={{ padding: '8px 0' }}>
                                <span style={{ fontSize: '12px', color: 'var(--text-muted)', width: '80px', display: 'inline-block' }}>Output</span>
                                <pre style={{ fontSize: '11px', margin: '8px 0', background: 'var(--bg-primary)', padding: '8px', borderRadius: '4px', overflow: 'auto', maxHeight: '200px' }}>{step.output}</pre>
                              </div>

                              {/* A/B Testing Feedback Section */}
                              {step.abTesting && (
                                <div style={{
                                  marginTop: '12px',
                                  padding: '12px',
                                  background: 'linear-gradient(135deg, rgba(99, 102, 241, 0.05), rgba(139, 92, 246, 0.05))',
                                  border: '1px solid rgba(99, 102, 241, 0.2)',
                                  borderRadius: '8px'
                                }}>
                                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
                                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                                      <span style={{
                                        fontSize: '10px',
                                        fontWeight: 600,
                                        padding: '3px 8px',
                                        borderRadius: '4px',
                                        background: 'rgba(99, 102, 241, 0.15)',
                                        color: '#6366f1',
                                        textTransform: 'uppercase',
                                        letterSpacing: '0.5px'
                                      }}>
                                        A/B Test
                                      </span>
                                      <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                                        Variant: <strong style={{ color: 'var(--text-primary)' }}>{step.abTesting.variant_name}</strong>
                                      </span>
                                    </div>
                                  </div>

                                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                                    <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>Was this output helpful?</span>

                                    {feedbackState[step.abTesting.assignment_id] === 'pending' ? (
                                      <span style={{ fontSize: '12px', color: 'var(--text-muted)', display: 'flex', alignItems: 'center', gap: '4px' }}>
                                        <Loader2 size={14} className="animate-spin" />
                                        Submitting...
                                      </span>
                                    ) : feedbackState[step.abTesting.assignment_id] ? (
                                      <span style={{
                                        fontSize: '12px',
                                        color: feedbackState[step.abTesting.assignment_id] === 'positive' ? '#10b981' : '#ef4444',
                                        display: 'flex',
                                        alignItems: 'center',
                                        gap: '4px'
                                      }}>
                                        {feedbackState[step.abTesting.assignment_id] === 'positive' ? (
                                          <><ThumbsUp size={14} /> Thanks for the feedback!</>
                                        ) : (
                                          <><ThumbsDown size={14} /> Thanks for the feedback!</>
                                        )}
                                      </span>
                                    ) : (
                                      <div style={{ display: 'flex', gap: '8px' }}>
                                        <button
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            submitFeedback(step.abTesting!.assignment_id, true);
                                          }}
                                          style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '4px',
                                            padding: '6px 12px',
                                            border: '1px solid #10b981',
                                            background: 'rgba(16, 185, 129, 0.1)',
                                            borderRadius: '6px',
                                            cursor: 'pointer',
                                            fontSize: '12px',
                                            fontWeight: 500,
                                            color: '#10b981',
                                            transition: 'all 0.2s'
                                          }}
                                          onMouseOver={(e) => {
                                            e.currentTarget.style.background = 'rgba(16, 185, 129, 0.2)';
                                          }}
                                          onMouseOut={(e) => {
                                            e.currentTarget.style.background = 'rgba(16, 185, 129, 0.1)';
                                          }}
                                        >
                                          <ThumbsUp size={14} />
                                          Helpful
                                        </button>
                                        <button
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            submitFeedback(step.abTesting!.assignment_id, false);
                                          }}
                                          style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            gap: '4px',
                                            padding: '6px 12px',
                                            border: '1px solid #ef4444',
                                            background: 'rgba(239, 68, 68, 0.1)',
                                            borderRadius: '6px',
                                            cursor: 'pointer',
                                            fontSize: '12px',
                                            fontWeight: 500,
                                            color: '#ef4444',
                                            transition: 'all 0.2s'
                                          }}
                                          onMouseOver={(e) => {
                                            e.currentTarget.style.background = 'rgba(239, 68, 68, 0.2)';
                                          }}
                                          onMouseOut={(e) => {
                                            e.currentTarget.style.background = 'rgba(239, 68, 68, 0.1)';
                                          }}
                                        >
                                          <ThumbsDown size={14} />
                                          Not Helpful
                                        </button>
                                      </div>
                                    )}
                                  </div>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}

                {/* Error message */}
                {selectedExecutionData.error_message && (
                  <div style={{ padding: '20px', borderTop: '1px solid var(--border-color)' }}>
                    <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: '8px', padding: '16px' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', color: '#dc2626', fontWeight: 600 }}>
                        <XCircle size={16} />
                        Error
                      </div>
                      <pre style={{ fontSize: '12px', fontFamily: 'monospace', margin: 0, color: '#dc2626', whiteSpace: 'pre-wrap' }}>{selectedExecutionData.error_message}</pre>
                    </div>
                  </div>
                )}

                {/* Input/Output */}
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', padding: '20px', borderTop: '1px solid var(--border-color)' }}>
                  <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', overflow: 'hidden' }}>
                    <h4 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', padding: '12px 16px', margin: 0, borderBottom: '1px solid var(--border-color)', background: 'var(--bg-primary)' }}>Input</h4>
                    <pre style={{ fontSize: '12px', fontFamily: 'monospace', padding: '16px', margin: 0, overflow: 'auto', maxHeight: '200px' }}>
                      {selectedExecutionData.input_data ? JSON.stringify(selectedExecutionData.input_data, null, 2) : 'No input data'}
                    </pre>
                  </div>
                  <div style={{ background: 'var(--bg-secondary)', border: '1px solid var(--border-color)', borderRadius: '8px', overflow: 'hidden' }}>
                    <h4 style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', padding: '12px 16px', margin: 0, borderBottom: '1px solid var(--border-color)', background: 'var(--bg-primary)' }}>Output</h4>
                    <pre style={{ fontSize: '12px', fontFamily: 'monospace', padding: '16px', margin: 0, overflow: 'auto', maxHeight: '200px' }}>
                      {selectedExecutionData.output_data ? JSON.stringify(selectedExecutionData.output_data, null, 2) : 'Pending...'}
                    </pre>
                  </div>
                </div>
              </>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--text-muted)', textAlign: 'center', padding: '40px' }}>
                <Play size={48} style={{ opacity: 0.3, marginBottom: '16px' }} />
                <h3 style={{ fontSize: '16px', fontWeight: 600, margin: '0 0 8px' }}>Select an execution</h3>
                <p style={{ margin: 0 }}>Click on an execution from the list to view details</p>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default ExecutionsPage;
