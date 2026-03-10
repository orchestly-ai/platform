import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Workflow,
  Play,
  DollarSign,
  Plug,
  Settings,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  AlertTriangle,
  Cpu,
  CheckCircle,
  GitBranch,
  FileText,
  Users,
  ListTodo,
  Store,
  Webhook,
  Calendar,
  MessageSquare,
  Wrench,
  Code,
  Key,
  BookOpen,
  Brain,
  Database,
  Server,
  Shield,
  Palette,
  Cloud,
} from 'lucide-react';

interface NavItem {
  id: string;
  label: string;
  href: string;
  icon: typeof LayoutDashboard;
  badge?: number;
}

interface NavSection {
  id: string;
  label: string;
  items: NavItem[];
  collapsible?: boolean;
}

const navSections: NavSection[] = [
  {
    id: 'operate',
    label: 'Operate',
    items: [
      { id: 'overview', label: 'Overview', href: '/dashboard', icon: LayoutDashboard },
      { id: 'workflows', label: 'Workflows', href: '/workflows', icon: Workflow, badge: 12 },
      { id: 'runs', label: 'Runs', href: '/runs', icon: Play, badge: 3 },
      { id: 'agents', label: 'Agents', href: '/agents', icon: Users, badge: 5 },
      { id: 'tasks', label: 'Tasks', href: '/tasks', icon: ListTodo },
      { id: 'approvals', label: 'Approvals', href: '/approvals', icon: CheckCircle, badge: 5 },
      { id: 'alerts', label: 'Alerts', href: '/alerts', icon: AlertTriangle, badge: 2 },
      { id: 'schedules', label: 'Schedules', href: '/schedules', icon: Calendar },
    ],
  },
  {
    id: 'build',
    label: 'Build',
    items: [
      { id: 'marketplace', label: 'Marketplace', href: '/marketplace', icon: Store },
      { id: 'integrations', label: 'Integrations', href: '/integrations', icon: Plug, badge: 8 },
      { id: 'prompts', label: 'Prompt Registry', href: '/prompts', icon: MessageSquare },
      { id: 'webhooks', label: 'Webhooks', href: '/webhooks', icon: Webhook },
      { id: 'mcp', label: 'MCP Tools', href: '/mcp', icon: Wrench },
      { id: 'developers', label: 'Developers', href: '/developers', icon: Code },
    ],
  },
  {
    id: 'platform',
    label: 'Platform',
    collapsible: true,
    items: [
      { id: 'llm-settings', label: 'LLM Router', href: '/llm-settings', icon: Cpu },
      { id: 'costs', label: 'Costs & Billing', href: '/costs', icon: DollarSign },
      { id: 'ab-testing', label: 'A/B Testing', href: '/ab-testing', icon: GitBranch },
      { id: 'audit', label: 'Audit Logs', href: '/audit', icon: FileText },
      { id: 'byok-settings', label: 'API Keys', href: '/byok-settings', icon: Key },
      { id: 'memory-providers', label: 'Memory BYOS', href: '/memory-providers', icon: Brain },
      { id: 'rag-connectors', label: 'RAG BYOD', href: '/rag-connectors', icon: Database },
      { id: 'byoc-workers', label: 'Workers BYOC', href: '/byoc-workers', icon: Server },
      { id: 'sso-config', label: 'SSO Config', href: '/sso-config', icon: Shield },
      { id: 'white-label', label: 'White-Label', href: '/white-label', icon: Palette },
      { id: 'multicloud', label: 'Multi-Cloud', href: '/multicloud', icon: Cloud },
      { id: 'settings', label: 'Settings', href: '/settings', icon: Settings },
    ],
  },
];

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  const [collapsedSections, setCollapsedSections] = useState<Record<string, boolean>>({
    platform: true,
  });

  const toggleSection = (sectionId: string) => {
    setCollapsedSections((prev) => ({
      ...prev,
      [sectionId]: !prev[sectionId],
    }));
  };

  return (
    <aside className={`dashboard-sidebar ${collapsed ? 'collapsed' : ''}`}>
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <div className="logo-icon">
            <Workflow size={24} />
          </div>
          {!collapsed && (
            <>
              <span className="logo-text">Orchestly</span>
              <span className="logo-badge">Pro</span>
            </>
          )}
        </div>
        <button
          className="sidebar-toggle"
          onClick={onToggle}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>

      <nav className="sidebar-nav">
        {navSections.map((section) => {
          const isCollapsed = section.collapsible && collapsedSections[section.id];

          return (
            <div key={section.id} className="nav-section">
              {!collapsed && (
                <div
                  className={`nav-section-header ${section.collapsible ? 'collapsible' : ''}`}
                  onClick={section.collapsible ? () => toggleSection(section.id) : undefined}
                >
                  <span className="nav-section-label">{section.label}</span>
                  {section.collapsible && (
                    <ChevronDown
                      size={14}
                      className={`nav-section-chevron ${isCollapsed ? 'rotated' : ''}`}
                    />
                  )}
                </div>
              )}
              {!isCollapsed &&
                section.items.map((item) => {
                  const Icon = item.icon;
                  return (
                    <NavLink
                      key={item.id}
                      to={item.href}
                      className={({ isActive }) => `nav-item ${isActive ? 'active' : ''}`}
                      title={collapsed ? item.label : undefined}
                    >
                      <Icon size={20} />
                      {!collapsed && (
                        <>
                          <span className="nav-label">{item.label}</span>
                          {item.badge && <span className="nav-badge">{item.badge}</span>}
                        </>
                      )}
                      {collapsed && item.badge && <span className="nav-badge-dot" />}
                    </NavLink>
                  );
                })}
            </div>
          );
        })}
      </nav>

      <div className="sidebar-footer">
        <a
          href="http://localhost:8000/docs"
          target="_blank"
          rel="noopener noreferrer"
          className="nav-item"
          title="API Documentation"
        >
          <BookOpen size={20} />
          {!collapsed && <span className="nav-label">API Docs</span>}
        </a>
        <div className="sidebar-user">
          {!collapsed && (
            <div className="user-info">
              <span className="user-name">Acme Corp</span>
              <span className="user-plan">Enterprise Plan</span>
            </div>
          )}
          <div className="user-avatar">AC</div>
        </div>
      </div>
    </aside>
  );
}
