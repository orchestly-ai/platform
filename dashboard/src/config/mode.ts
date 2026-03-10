/**
 * Dashboard Mode Configuration
 *
 * Controls whether the dashboard runs in demo mode (mock data) or production mode (real APIs)
 *
 * Demo mode:
 * - Uses mock data for all visualizations
 * - Shows "Demo Mode" banner
 * - Suitable for marketing, investor demos, and testing
 *
 * Production mode:
 * - Connects to real backend APIs
 * - Shows live data
 * - For actual customer usage
 */

export type DashboardMode = 'demo' | 'production';

// Check URL params first, then environment variable
function detectMode(): DashboardMode {
  // Check URL param: ?mode=demo or ?demo=true
  if (typeof window !== 'undefined') {
    const params = new URLSearchParams(window.location.search);
    if (params.get('mode') === 'demo' || params.get('demo') === 'true') {
      return 'demo';
    }
    if (params.get('mode') === 'production') {
      return 'production';
    }
  }

  // Check environment variable
  const envMode = import.meta.env.VITE_DASHBOARD_MODE as string | undefined;
  if (envMode === 'demo') {
    return 'demo';
  }

  // Default to demo for development, production otherwise
  if (import.meta.env.DEV) {
    return 'demo';
  }

  return 'production';
}

export const dashboardMode = detectMode();
export const isDemoMode = dashboardMode === 'demo';
export const isProductionMode = dashboardMode === 'production';

// Re-export for components that need to check mode
export function useDashboardMode(): DashboardMode {
  return dashboardMode;
}
