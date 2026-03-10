import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell,
  Search,
  User,
  LogOut,
  Settings,
} from 'lucide-react';
import { useAuth } from '../contexts/AuthContext';
import ThemeToggle from './ThemeToggle';

interface HeaderProps {
  // Remove darkMode props - now managed by ThemeContext
}

interface Notification {
  id: number;
  title: string;
  message: string;
  time: string;
  type: 'warning' | 'error' | 'success';
}

export function Header({}: HeaderProps = {}) {
  const [showNotifications, setShowNotifications] = useState(false);
  const [showUserMenu, setShowUserMenu] = useState(false);
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  // Get user initials for avatar
  const userInitials = user?.name
    ? user.name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)
    : 'U';

  const notifications: Notification[] = [
    { id: 1, title: 'Budget Alert', message: 'GPT-4 usage at 85% of budget', time: '5m ago', type: 'warning' },
    { id: 2, title: 'Workflow Failed', message: 'Customer Support Agent failed at step 3', time: '12m ago', type: 'error' },
    { id: 3, title: 'New Integration', message: 'Slack integration connected successfully', time: '1h ago', type: 'success' },
  ];

  return (
    <header className="dashboard-header">
      <div className="header-search">
        <Search size={18} />
        <input type="text" placeholder="Search workflows, executions, integrations..." />
        <kbd>⌘K</kbd>
      </div>

      <div className="header-actions">
        <ThemeToggle />

        <div className="notification-wrapper">
          <button
            className={`header-action ${showNotifications ? 'active' : ''}`}
            onClick={() => {
              setShowNotifications(!showNotifications);
              setShowUserMenu(false);
            }}
          >
            <Bell size={20} />
            <span className="notification-indicator" />
          </button>
          {showNotifications && (
            <div className="dropdown-menu notifications-menu">
              <div className="dropdown-header">
                <span>Notifications</span>
                <button className="mark-read">Mark all read</button>
              </div>
              <div className="dropdown-content">
                {notifications.map((notif) => (
                  <div key={notif.id} className={`notification-item ${notif.type}`}>
                    <div className="notification-dot" />
                    <div className="notification-content">
                      <span className="notification-title">{notif.title}</span>
                      <span className="notification-message">{notif.message}</span>
                      <span className="notification-time">{notif.time}</span>
                    </div>
                  </div>
                ))}
              </div>
              <div className="dropdown-footer">
                <button>View all notifications</button>
              </div>
            </div>
          )}
        </div>

        <div className="user-wrapper">
          <button
            className={`header-action user-button ${showUserMenu ? 'active' : ''}`}
            onClick={() => {
              setShowUserMenu(!showUserMenu);
              setShowNotifications(false);
            }}
          >
            <div className="user-avatar-small">{userInitials}</div>
            <span className="user-name-header">{user?.name || 'User'}</span>
          </button>
          {showUserMenu && (
            <div className="dropdown-menu user-menu">
              <div className="dropdown-header user-header">
                <div className="user-avatar-large">{userInitials}</div>
                <div className="user-details">
                  <span className="user-full-name">{user?.name || 'User'}</span>
                  <span className="user-email">{user?.email || ''}</span>
                </div>
              </div>
              <div className="dropdown-content">
                <button className="menu-item" onClick={() => navigate('/settings')}>
                  <User size={16} />
                  Profile Settings
                </button>
                <button className="menu-item" onClick={() => navigate('/settings')}>
                  <Settings size={16} />
                  Account Settings
                </button>
                <hr />
                <button className="menu-item logout" onClick={handleLogout}>
                  <LogOut size={16} />
                  Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
