/**
 * Overview Page - Dashboard home with key metrics
 * Connects to real backend API for system metrics
 * Shows OnboardingWizard for new users who haven't completed onboarding.
 */

import { useState, useCallback } from 'react';
import { useQuery } from '@tanstack/react-query';
import { api } from '@/services/api';
import { useAuth } from '@/contexts/AuthContext';
import { OnboardingWizard } from '@/components/OnboardingWizard';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  DollarSign,
  Zap,
  CheckCircle,
  XCircle,
  Clock,
  BarChart3,
  Cpu,
  Bot,
  GitBranch,
  Loader2,
  AlertTriangle,
} from 'lucide-react';

type TimeRange = '24h' | '7d' | '30d';

interface MetricCard {
  title: string;
  value: string;
  change: number;
  changeLabel: string;
  icon: typeof Activity;
  trend: 'up' | 'down';
  color: string;
}

// Mock data for demo mode
const getMetricsByTimeRange = (range: TimeRange): MetricCard[] => {
  const data = {
    '24h': [
      { title: 'Total Executions', value: '2,847', change: 12.5, changeLabel: 'vs yesterday', icon: Activity, trend: 'up' as const, color: '#6366f1' },
      { title: 'Success Rate', value: '98.7%', change: 0.3, changeLabel: 'vs yesterday', icon: CheckCircle, trend: 'up' as const, color: '#10b981' },
      { title: 'Total Cost', value: '$247.32', change: -8.2, changeLabel: 'vs yesterday', icon: DollarSign, trend: 'down' as const, color: '#f59e0b' },
      { title: 'Avg. Latency', value: '234ms', change: -15.4, changeLabel: 'vs yesterday', icon: Zap, trend: 'down' as const, color: '#8b5cf6' },
    ],
    '7d': [
      { title: 'Total Executions', value: '18,542', change: 23.1, changeLabel: 'vs last week', icon: Activity, trend: 'up' as const, color: '#6366f1' },
      { title: 'Success Rate', value: '97.2%', change: -1.2, changeLabel: 'vs last week', icon: CheckCircle, trend: 'down' as const, color: '#10b981' },
      { title: 'Total Cost', value: '$1,847.89', change: 5.4, changeLabel: 'vs last week', icon: DollarSign, trend: 'up' as const, color: '#f59e0b' },
      { title: 'Avg. Latency', value: '312ms', change: 8.7, changeLabel: 'vs last week', icon: Zap, trend: 'up' as const, color: '#8b5cf6' },
    ],
    '30d': [
      { title: 'Total Executions', value: '72,394', change: 45.2, changeLabel: 'vs last month', icon: Activity, trend: 'up' as const, color: '#6366f1' },
      { title: 'Success Rate', value: '96.8%', change: 2.1, changeLabel: 'vs last month', icon: CheckCircle, trend: 'up' as const, color: '#10b981' },
      { title: 'Total Cost', value: '$8,247.32', change: -12.3, changeLabel: 'vs last month', icon: DollarSign, trend: 'down' as const, color: '#f59e0b' },
      { title: 'Avg. Latency', value: '287ms', change: -5.2, changeLabel: 'vs last month', icon: Zap, trend: 'down' as const, color: '#8b5cf6' },
    ],
  };
  return data[range];
};

interface ChartEntry {
  label: string;
  success: number;
  failed: number;
}

const getChartDataByTimeRange = (range: TimeRange): ChartEntry[] => {
  const data: Record<TimeRange, ChartEntry[]> = {
    '24h': [
      { label: '12AM', success: 180, failed: 12 },
      { label: '2AM', success: 95, failed: 5 },
      { label: '4AM', success: 60, failed: 3 },
      { label: '6AM', success: 120, failed: 8 },
      { label: '8AM', success: 245, failed: 18 },
      { label: '10AM', success: 310, failed: 22 },
      { label: '12PM', success: 340, failed: 15 },
      { label: '2PM', success: 320, failed: 28 },
      { label: '4PM', success: 290, failed: 20 },
      { label: '6PM', success: 230, failed: 14 },
      { label: '8PM', success: 195, failed: 10 },
      { label: '10PM', success: 160, failed: 7 },
    ],
    '7d': [
      { label: 'Mon', success: 2450, failed: 85 },
      { label: 'Tue', success: 2680, failed: 120 },
      { label: 'Wed', success: 2890, failed: 95 },
      { label: 'Thu', success: 2720, failed: 145 },
      { label: 'Fri', success: 2950, failed: 110 },
      { label: 'Sat', success: 1850, failed: 42 },
      { label: 'Sun', success: 1600, failed: 35 },
    ],
    '30d': [
      { label: '1', success: 2100, failed: 78 },
      { label: '2', success: 2250, failed: 92 },
      { label: '3', success: 2180, failed: 65 },
      { label: '4', success: 2400, failed: 110 },
      { label: '5', success: 2350, failed: 88 },
      { label: '6', success: 1900, failed: 45 },
      { label: '7', success: 1750, failed: 38 },
      { label: '8', success: 2500, failed: 95 },
      { label: '9', success: 2650, failed: 120 },
      { label: '10', success: 2700, failed: 105 },
      { label: '11', success: 2800, failed: 130 },
      { label: '12', success: 2750, failed: 98 },
      { label: '13', success: 1950, failed: 52 },
      { label: '14', success: 1800, failed: 40 },
      { label: '15', success: 2600, failed: 115 },
      { label: '16', success: 2850, failed: 125 },
      { label: '17', success: 2900, failed: 108 },
      { label: '18', success: 2780, failed: 95 },
      { label: '19', success: 2950, failed: 140 },
      { label: '20', success: 2050, failed: 48 },
      { label: '21', success: 1850, failed: 42 },
      { label: '22', success: 2700, failed: 102 },
      { label: '23', success: 2850, failed: 118 },
      { label: '24', success: 2920, failed: 135 },
      { label: '25', success: 2800, failed: 100 },
      { label: '26', success: 2750, failed: 88 },
      { label: '27', success: 2000, failed: 55 },
      { label: '28', success: 1900, failed: 45 },
      { label: '29', success: 2650, failed: 110 },
      { label: '30', success: 2800, failed: 95 },
    ],
  };
  return data[range];
};

interface ProviderUsage {
  name: string;
  requests: number;
  cost: number;
  color: string;
}

const getProviderUsageByTimeRange = (range: TimeRange): ProviderUsage[] => {
  const multiplier = range === '24h' ? 1 : range === '7d' ? 7 : 30;
  return [
    { name: 'GPT-4o', requests: Math.round(1521 * multiplier), cost: 142.12 * multiplier, color: '#10b981' },
    { name: 'Claude 3.5', requests: Math.round(1892 * multiplier), cost: 189.20 * multiplier, color: '#6366f1' },
    { name: 'GPT-4o-mini', requests: Math.round(2847 * multiplier), cost: 42.35 * multiplier, color: '#f59e0b' },
    { name: 'Gemini Pro', requests: Math.round(587 * multiplier), cost: 73.65 * multiplier, color: '#ec4899' },
  ];
};

interface RecentExecution {
  id: string;
  workflow: string;
  type: 'agent' | 'workflow';
  status: 'success' | 'failed' | 'running';
  duration: string;
  cost: string;
  timestamp: string;
  team: string;
}

const recentExecutions: RecentExecution[] = [
  { id: 'exec-001', workflow: 'Customer Support Agent', type: 'agent', status: 'success', duration: '2.3s', cost: '$0.023', timestamp: '2 min ago', team: 'Support' },
  { id: 'exec-002', workflow: 'Lead Qualification Flow', type: 'workflow', status: 'success', duration: '4.1s', cost: '$0.045', timestamp: '5 min ago', team: 'Sales' },
  { id: 'exec-003', workflow: 'Content Writer Agent', type: 'agent', status: 'running', duration: '1.2s', cost: '$0.012', timestamp: '8 min ago', team: 'Marketing' },
  { id: 'exec-004', workflow: 'Data Pipeline', type: 'workflow', status: 'failed', duration: '12.4s', cost: '$0.089', timestamp: '12 min ago', team: 'Engineering' },
  { id: 'exec-005', workflow: 'Support Triage Agent', type: 'agent', status: 'success', duration: '1.8s', cost: '$0.019', timestamp: '15 min ago', team: 'Support' },
];

export function OverviewPage() {
  const [timeRange, setTimeRange] = useState<TimeRange>('24h');
  const { user, refreshUser } = useAuth();
  const [onboardingDismissed, setOnboardingDismissed] = useState(false);

  const showOnboarding =
    !onboardingDismissed && user && !user.preferences?.onboarding_completed;

  const handleOnboardingComplete = useCallback(async () => {
    try {
      await api.updateCurrentUser({
        preferences: { ...(user?.preferences || {}), onboarding_completed: true },
      });
      await refreshUser();
    } catch {
      // Still dismiss the wizard even if the API call fails
    }
    setOnboardingDismissed(true);
  }, [user, refreshUser]);

  const handleOnboardingDismiss = useCallback(async () => {
    try {
      await api.updateCurrentUser({
        preferences: { ...(user?.preferences || {}), onboarding_completed: true },
      });
      await refreshUser();
    } catch {
      // Still dismiss on error
    }
    setOnboardingDismissed(true);
  }, [user, refreshUser]);

  // Fetch real system metrics from backend
  const { data: systemMetrics, isLoading, error } = useQuery({
    queryKey: ['systemMetrics'],
    queryFn: () => api.getSystemMetrics(),
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  // Fallback to demo data for development
  const metrics = getMetricsByTimeRange(timeRange);
  const chartData = getChartDataByTimeRange(timeRange);
  const providerUsage = getProviderUsageByTimeRange(timeRange);
  const totalRequests = providerUsage.reduce((sum, p) => sum + p.requests, 0);

  const getStatusIcon = (status: RecentExecution['status']) => {
    switch (status) {
      case 'success': return <CheckCircle size={14} className="status-icon success" />;
      case 'failed': return <XCircle size={14} className="status-icon failed" />;
      case 'running': return <Clock size={14} className="status-icon running" />;
    }
  };

  const getTypeIcon = (type: RecentExecution['type']) => {
    return type === 'agent' ? <Bot size={14} /> : <GitBranch size={14} />;
  };

  // Show loading state
  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <Loader2 className="h-8 w-8 animate-spin mx-auto mb-4 text-blue-500" />
          <p className="text-gray-600">Loading system metrics...</p>
        </div>
      </div>
    );
  }

  // Show error state
  if (error) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center max-w-md">
          <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">Failed to Load Metrics</h2>
          <p className="text-gray-600 mb-4">
            {error instanceof Error ? error.message : 'Unknown error occurred'}
          </p>
          <p className="text-sm text-gray-500">
            Make sure the backend API is running at {import.meta.env.VITE_API_URL || 'http://localhost:8000'}
          </p>
        </div>
      </div>
    );
  }

  // Show onboarding wizard for new users
  if (showOnboarding) {
    return (
      <div className="overview-page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minHeight: '80vh' }}>
        <OnboardingWizard
          onComplete={handleOnboardingComplete}
          onDismiss={handleOnboardingDismiss}
        />
      </div>
    );
  }

  return (
    <div className="overview-page">
      {/* Page Header */}
      <div className="page-header">
        <div className="page-title">
          <h1>Dashboard Overview</h1>
          <p>Monitor your AI agents and workflows in real-time</p>
          {systemMetrics && (
            <div className="text-xs text-green-600 mt-1 flex items-center gap-1">
              <Activity className="h-3 w-3" />
              <span>Connected to backend • {systemMetrics.agents.total} agents • Last update: {new Date(systemMetrics.timestamp).toLocaleTimeString()}</span>
            </div>
          )}
        </div>
        <div className="time-range-selector">
          {(['24h', '7d', '30d'] as const).map((range) => (
            <button
              key={range}
              className={`range-btn ${timeRange === range ? 'active' : ''}`}
              onClick={() => setTimeRange(range)}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* Metrics Grid */}
      <div className="metrics-grid">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <div key={metric.title} className="metric-card">
              <div className="metric-header">
                <div className="metric-icon" style={{ background: `${metric.color}15`, color: metric.color }}>
                  <Icon size={20} />
                </div>
                <div className={`metric-change ${metric.trend}`}>
                  {metric.trend === 'up' ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                  {Math.abs(metric.change)}%
                </div>
              </div>
              <div className="metric-value">{metric.value}</div>
              <div className="metric-label">
                <span>{metric.title}</span>
                <span className="metric-sublabel">{metric.changeLabel}</span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Charts Row */}
      <div className="charts-row">
        <div className="chart-card">
          <div className="chart-header">
            <div className="chart-title">
              <BarChart3 size={18} />
              <span>Execution Trends</span>
            </div>
          </div>
          {(() => {
            const maxTotal = Math.max(...chartData.map(d => d.success + d.failed));
            const yMax = Math.ceil(maxTotal / 100) * 100;
            const labelInterval = timeRange === '30d' ? 5 : 1;
            return (
              <div style={{ display: 'flex', height: '200px', paddingBottom: '0' }}>
                {/* Y-axis */}
                <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'space-between', paddingRight: '8px', paddingBottom: '24px', minWidth: '40px' }}>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)', textAlign: 'right' }}>{yMax}</span>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)', textAlign: 'right' }}>{Math.round(yMax / 2)}</span>
                  <span style={{ fontSize: '10px', color: 'var(--text-muted)', textAlign: 'right' }}>0</span>
                </div>
                {/* Bars + X-axis */}
                <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
                  <div style={{ flex: 1, display: 'flex', alignItems: 'flex-end', gap: timeRange === '30d' ? '2px' : '4px' }}>
                    {chartData.map((entry, i) => {
                      const total = entry.success + entry.failed;
                      const successHeight = (entry.success / yMax) * 100;
                      const failedHeight = (entry.failed / yMax) * 100;
                      return (
                        <div
                          key={i}
                          style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', minWidth: '4px', maxWidth: '40px', height: '100%' }}
                          title={`${entry.label}: ${entry.success} successful, ${entry.failed} failed`}
                        >
                          <div style={{ height: `${failedHeight}%`, background: '#ff6188', borderRadius: '3px 3px 0 0', minHeight: failedHeight > 0 ? '2px' : '0' }} />
                          <div style={{ height: `${successHeight}%`, background: '#a9dc76', borderRadius: total === entry.success ? '3px 3px 0 0' : '0', minHeight: successHeight > 0 ? '2px' : '0' }} />
                        </div>
                      );
                    })}
                  </div>
                  {/* X-axis labels */}
                  <div style={{ display: 'flex', gap: timeRange === '30d' ? '2px' : '4px', paddingTop: '6px' }}>
                    {chartData.map((entry, i) => (
                      <div key={i} style={{ flex: 1, minWidth: '4px', maxWidth: '40px', textAlign: 'center' }}>
                        {i % labelInterval === 0 && (
                          <span style={{ fontSize: '9px', color: 'var(--text-muted)', whiteSpace: 'nowrap' }}>{entry.label}</span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            );
          })()}
          <div style={{ display: 'flex', gap: '16px', justifyContent: 'center', paddingTop: '12px', borderTop: '1px solid var(--border-color)' }}>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#10b981' }} />
              Successful
            </span>
            <span style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '12px', color: 'var(--text-secondary)' }}>
              <span style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#ef4444' }} />
              Failed
            </span>
          </div>
        </div>

        <div className="chart-card">
          <div className="chart-header">
            <div className="chart-title">
              <Cpu size={18} />
              <span>Provider Usage</span>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            {providerUsage.map((provider) => (
              <div key={provider.name}>
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span style={{ fontWeight: 600, color: provider.color }}>{provider.name}</span>
                  <span style={{ fontWeight: 600 }}>${provider.cost.toFixed(2)}</span>
                </div>
                <div style={{ height: '8px', background: 'var(--bg-secondary)', borderRadius: '4px' }}>
                  <div style={{ height: '100%', width: `${(provider.requests / totalRequests) * 100}%`, background: provider.color, borderRadius: '4px' }} />
                </div>
                <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
                  {provider.requests.toLocaleString()} requests ({((provider.requests / totalRequests) * 100).toFixed(1)}%)
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Recent Executions */}
      <div style={{ background: 'var(--bg-primary)', border: '1px solid var(--border-color)', borderRadius: '12px', padding: '20px', marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontSize: '16px', fontWeight: 600, color: 'var(--text-primary)' }}>
            <Activity size={18} />
            <span>Recent Executions</span>
          </div>
          <button style={{ display: 'flex', alignItems: 'center', gap: '4px', padding: '6px 12px', border: 'none', background: 'transparent', color: 'var(--primary-color)', fontSize: '13px', fontWeight: 500, cursor: 'pointer', borderRadius: '6px' }}>
            View All →
          </button>
        </div>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '700px' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                <th style={{ padding: '12px 8px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Name</th>
                <th style={{ padding: '12px 8px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Type</th>
                <th style={{ padding: '12px 8px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Team</th>
                <th style={{ padding: '12px 8px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Status</th>
                <th style={{ padding: '12px 8px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Duration</th>
                <th style={{ padding: '12px 8px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Cost</th>
                <th style={{ padding: '12px 8px', textAlign: 'left', fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase' }}>Time</th>
              </tr>
            </thead>
            <tbody>
              {recentExecutions.map((exec) => (
                <tr key={exec.id} style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <td style={{ padding: '14px 8px', fontWeight: 500, color: 'var(--text-primary)' }}>{exec.workflow}</td>
                  <td style={{ padding: '14px 8px' }}>
                    <span className={`type-badge ${exec.type}`}>
                      {getTypeIcon(exec.type)}
                      {exec.type}
                    </span>
                  </td>
                  <td style={{ padding: '14px 8px' }}>
                    <span className="team-badge">{exec.team}</span>
                  </td>
                  <td style={{ padding: '14px 8px' }}>
                    <span className={`status-badge ${exec.status}`}>
                      {getStatusIcon(exec.status)}
                      {exec.status}
                    </span>
                  </td>
                  <td style={{ padding: '14px 8px', fontFamily: 'monospace', fontSize: '13px' }}>{exec.duration}</td>
                  <td style={{ padding: '14px 8px', fontWeight: 500 }}>{exec.cost}</td>
                  <td style={{ padding: '14px 8px', color: 'var(--text-muted)', fontSize: '13px' }}>{exec.timestamp}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Quick Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
        {[
          { icon: Bot, value: '24', label: 'Active Agents', color: '#6366f1' },
          { icon: GitBranch, value: '18', label: 'Active Workflows', color: '#10b981' },
          { icon: Activity, value: '6', label: 'Teams', color: '#f59e0b' },
          { icon: CheckCircle, value: '8', label: 'Integrations', color: '#ec4899' },
        ].map((stat) => (
          <div key={stat.label} className="metric-card" style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div className="metric-icon" style={{ background: `${stat.color}15`, color: stat.color, width: '48px', height: '48px' }}>
              <stat.icon size={24} />
            </div>
            <div>
              <div style={{ fontSize: '24px', fontWeight: 700, color: 'var(--text-primary)' }}>{stat.value}</div>
              <div style={{ fontSize: '14px', color: 'var(--text-secondary)' }}>{stat.label}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default OverviewPage;
