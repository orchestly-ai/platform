import { Outlet, NavLink } from 'react-router-dom'
import {
  LayoutDashboard,
  Users,
  ListTodo,
  AlertTriangle,
  Activity,
  Workflow,
  Cpu,
  DollarSign,
  Bug,
  CheckCircle,
  GitBranch,
  FileText,
} from 'lucide-react'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Workflows', href: '/workflows', icon: Workflow },
  { name: 'Agents', href: '/agents', icon: Users },
  { name: 'Tasks', href: '/tasks', icon: ListTodo },
  { name: 'Alerts', href: '/alerts', icon: AlertTriangle },
  { name: 'LLM Settings', href: '/llm-settings', icon: Cpu },
  { name: 'Costs', href: '/costs', icon: DollarSign },
  { name: 'Debugger', href: '/debugger', icon: Bug },
  { name: 'Approvals', href: '/approvals', icon: CheckCircle },
  { name: 'A/B Testing', href: '/ab-testing', icon: GitBranch },
  { name: 'Audit', href: '/audit', icon: FileText },
]

export function Layout() {
  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex">
              <div className="flex-shrink-0 flex items-center space-x-3">
                <Activity className="h-8 w-8 text-blue-600" />
                <div>
                  <h1 className="text-xl font-bold text-gray-900">
                    Orchestly
                  </h1>
                  <div className="flex items-center space-x-2">
                    <div className="h-2 w-2 bg-green-500 rounded-full status-active" />
                    <span className="text-xs text-gray-500">Live</span>
                  </div>
                </div>
              </div>
              <div className="hidden sm:ml-8 sm:flex sm:space-x-4">
                {navigation.map((item) => (
                  <NavLink
                    key={item.name}
                    to={item.href}
                    className={({ isActive }) =>
                      `inline-flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors ${
                        isActive
                          ? 'bg-blue-50 text-blue-700'
                          : 'text-gray-700 hover:bg-gray-100'
                      }`
                    }
                  >
                    <item.icon className="mr-2 h-4 w-4" />
                    {item.name}
                  </NavLink>
                ))}
              </div>
            </div>
            <div className="flex items-center">
              <span className="text-sm text-gray-500">
                Updated every 5s
              </span>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <Outlet />
      </main>
    </div>
  )
}
