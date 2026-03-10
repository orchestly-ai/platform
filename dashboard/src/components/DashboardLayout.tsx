import { useState } from 'react';
import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useTheme } from '../contexts/ThemeContext';
import './DashboardLayout.css';

export function DashboardLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const { themeType } = useTheme();

  return (
    <div className={`dashboard ${themeType === 'monokai-pro' ? 'theme-dark' : ''} ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggle={() => setSidebarCollapsed(!sidebarCollapsed)}
      />

      <div className="dashboard-main">
        <Header />

        <main className="dashboard-content">
          <Outlet context={{ sidebarCollapsed, setSidebarCollapsed }} />
        </main>
      </div>
    </div>
  );
}
