import React, { useState, useCallback, useEffect, useRef, DragEvent } from 'react'
import { useSearchParams, useNavigate, useLocation } from 'react-router-dom'
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  MiniMap,
  BackgroundVariant,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Panel,
  ReactFlowProvider,
  useReactFlow,
} from 'reactflow'
import 'reactflow/dist/style.css'
import {
  Save, Play, Download, Upload, FolderOpen, FileText, CheckCircle, XCircle, X,
  HelpCircle, DollarSign, AlertTriangle, TestTube, RotateCcw, History,
  AlertCircle, Undo2, Redo2, Crown, Cpu, Wrench, Zap, GitBranch,
  MessageSquare, CreditCard, Github, Mail, Phone, Cloud, Headphones,
  Users, BarChart3, FileSpreadsheet, Plug, GripVertical, Sparkles,
  Database, BookOpen, Webhook, UserCheck, Terminal
} from 'lucide-react'
import { AgentNodeData, NodeType, IntegrationType, WebhookAuthType } from '../types'
import api from '../services/api'
import { TemplateModal } from '../components/TemplateModal'
import type { WorkflowTemplate } from '../data/workflowTemplates'

// Custom node types
import SupervisorNode from '../components/workflow/SupervisorNode'
import WorkerNode from '../components/workflow/WorkerNode'
import ToolNode from '../components/workflow/ToolNode'
import TriggerNode from '../components/workflow/TriggerNode'
import IntegrationNode from '../components/workflow/IntegrationNode'
import ConditionNode from '../components/workflow/ConditionNode'
import MemoryNode from '../components/workflow/MemoryNode'
import KnowledgeNode from '../components/workflow/KnowledgeNode'
import WebhookNode from '../components/workflow/WebhookNode'
import HITLNode from '../components/workflow/HITLNode'
import PrintNode from '../components/workflow/PrintNode'
import VariablePicker from '../components/workflow/VariablePicker'
import PromptSelector from '../components/workflow/PromptSelector'

const nodeTypes = {
  supervisor: SupervisorNode,
  worker: WorkerNode,
  tool: ToolNode,
  trigger: TriggerNode,
  integration: IntegrationNode,
  condition: ConditionNode,
  webhook: WebhookNode,
  hitl: HITLNode,
  memory: MemoryNode,
  knowledge: KnowledgeNode,
  print: PrintNode,
}

// Palette items for drag-and-drop
interface PaletteItem {
  type: NodeType
  label: string
  description: string
  icon: React.ReactNode
  color: string
  defaultData: Partial<AgentNodeData>
}

const agentPaletteItems: PaletteItem[] = [
  {
    type: 'supervisor',
    label: 'Supervisor Agent',
    description: 'Coordinates other agents',
    icon: <Crown className="w-4 h-4" />,
    color: 'purple',
    defaultData: {
      modelSelection: 'auto', // Use routing strategy
      routingStrategy: null, // Inherit from workflow/org
      llmModel: null, // Only used if modelSelection is specific model
      capabilities: ['coordination', 'planning'],
    },
  },
  {
    type: 'worker',
    label: 'Worker Agent',
    description: 'Processes tasks',
    icon: <Cpu className="w-4 h-4" />,
    color: 'blue',
    defaultData: {
      modelSelection: 'auto', // Use routing strategy
      routingStrategy: null, // Inherit from workflow/org
      llmModel: null, // Only used if modelSelection is specific model
      capabilities: ['processing'],
    },
  },
  {
    type: 'tool',
    label: 'Tool/API',
    description: 'External HTTP API call',
    icon: <Wrench className="w-4 h-4" />,
    color: 'green',
    defaultData: {
      toolConfig: {
        method: 'GET',
        timeout: 30000,
        auth: { type: 'none' },
      },
    },
  },
]

const triggerPaletteItems: PaletteItem[] = [
  {
    type: 'trigger',
    label: 'Webhook Trigger',
    description: 'HTTP webhook endpoint',
    icon: <Zap className="w-4 h-4" />,
    color: 'orange',
    defaultData: {
      triggerConfig: { triggerType: 'webhook' },
    },
  },
  {
    type: 'trigger',
    label: 'Schedule Trigger',
    description: 'Cron-based schedule',
    icon: <Zap className="w-4 h-4" />,
    color: 'orange',
    defaultData: {
      triggerConfig: { triggerType: 'cron', cronExpression: '0 9 * * *' },
    },
  },
  {
    type: 'trigger',
    label: 'Manual Trigger',
    description: 'Start manually',
    icon: <Zap className="w-4 h-4" />,
    color: 'orange',
    defaultData: {
      triggerConfig: { triggerType: 'manual' },
    },
  },
]

const conditionPaletteItems: PaletteItem[] = [
  {
    type: 'condition',
    label: 'Condition',
    description: 'Branch on condition',
    icon: <GitBranch className="w-4 h-4" />,
    color: 'amber',
    defaultData: {
      conditionConfig: { expression: '', trueLabel: 'Yes', falseLabel: 'No' },
    },
  },
]

const utilityPaletteItems: PaletteItem[] = [
  {
    type: 'print',
    label: 'Print Output',
    description: 'Print to Execution Log',
    icon: <Terminal className="w-4 h-4" />,
    color: 'teal',
    defaultData: {
      printConfig: {
        label: 'Output',
        message: '',
        includeTimestamp: true,
        logLevel: 'info',
      },
    },
  },
]

const dataPaletteItems: PaletteItem[] = [
  {
    type: 'memory',
    label: 'Memory (BYOS)',
    description: 'Vector database storage/query',
    icon: <Database className="w-4 h-4" />,
    color: 'indigo',
    defaultData: {
      memoryConfig: {
        operation: 'query',
        limit: 5,
      },
    },
  },
  {
    type: 'knowledge',
    label: 'Knowledge (RAG)',
    description: 'Query knowledge base',
    icon: <BookOpen className="w-4 h-4" />,
    color: 'teal',
    defaultData: {
      knowledgeConfig: {
        limit: 5,
        rerank: false,
      },
    },
  },
]

const eventPaletteItems: PaletteItem[] = [
  {
    type: 'webhook',
    label: 'Webhook Listener',
    description: 'Event-driven workflow trigger',
    icon: <Webhook className="w-4 h-4" />,
    color: 'purple',
    defaultData: {
      webhookConfig: {
        method: 'POST',
        authentication: {
          type: 'none',
        },
        responseStatus: 200,
      },
    },
  },
  {
    type: 'hitl',
    label: 'Human Approval',
    description: 'Require manual approval',
    icon: <UserCheck className="w-4 h-4" />,
    color: 'amber',
    defaultData: {
      hitlConfig: {
        approvalType: 'any',
        timeout: 60,
        timeoutAction: 'reject',
        notifyVia: ['email'],
        approvers: [],
      },
    },
  },
]

interface IntegrationPaletteItem extends PaletteItem {
  integrationType: IntegrationType
  actions: string[]
  connected?: boolean
}

// Integration icon mapping based on category
const getIntegrationIcon = (id: string, category: string): React.ReactNode => {
  const iconMap: Record<string, React.ReactNode> = {
    slack: <MessageSquare className="w-4 h-4" />,
    discord: <MessageSquare className="w-4 h-4" />,
    stripe: <CreditCard className="w-4 h-4" />,
    github: <Github className="w-4 h-4" />,
    gmail: <Mail className="w-4 h-4" />,
    sendgrid: <Mail className="w-4 h-4" />,
    twilio: <Phone className="w-4 h-4" />,
    aws_s3: <Cloud className="w-4 h-4" />,
    zendesk: <Headphones className="w-4 h-4" />,
    hubspot: <Users className="w-4 h-4" />,
    salesforce: <BarChart3 className="w-4 h-4" />,
    google_sheets: <FileSpreadsheet className="w-4 h-4" />,
    notion: <FileText className="w-4 h-4" />,
    airtable: <FileSpreadsheet className="w-4 h-4" />,
    jira: <FileText className="w-4 h-4" />,
    google_drive: <Cloud className="w-4 h-4" />,
  }

  // Category-based fallbacks
  const categoryMap: Record<string, React.ReactNode> = {
    communication: <MessageSquare className="w-4 h-4" />,
    crm: <Users className="w-4 h-4" />,
    project_management: <FileText className="w-4 h-4" />,
    storage: <Cloud className="w-4 h-4" />,
    email: <Mail className="w-4 h-4" />,
    ai: <Sparkles className="w-4 h-4" />,
    payments: <CreditCard className="w-4 h-4" />,
  }

  return iconMap[id] || categoryMap[category] || <Plug className="w-4 h-4" />
}

// Color mapping based on category
const getCategoryColor = (category: string): string => {
  const colorMap: Record<string, string> = {
    communication: 'purple',
    crm: 'blue',
    project_management: 'green',
    storage: 'orange',
    email: 'red',
    ai: 'indigo',
    payments: 'indigo',
    developer_tools: 'gray',
    analytics: 'blue',
  }
  return colorMap[category] || 'gray'
}

// Fallback static integrations (used while loading)
const staticIntegrationPaletteItems: IntegrationPaletteItem[] = [
  {
    type: 'integration',
    integrationType: 'slack',
    label: 'Slack',
    description: 'Send messages',
    icon: <MessageSquare className="w-4 h-4" />,
    color: 'purple',
    actions: ['send_message', 'create_channel', 'upload_file'],
    defaultData: {
      integrationConfig: { integrationType: 'slack', action: 'send_message', parameters: {} },
    },
  },
  {
    type: 'integration',
    integrationType: 'discord',
    label: 'Discord',
    description: 'Bot messaging',
    icon: <MessageSquare className="w-4 h-4" />,
    color: 'indigo',
    actions: ['send_message', 'send_embed', 'create_channel', 'add_reaction'],
    defaultData: {
      integrationConfig: { integrationType: 'discord', action: 'send_message', parameters: {} },
    },
  },
  {
    type: 'integration',
    integrationType: 'gmail',
    label: 'Gmail',
    description: 'Send emails',
    icon: <Mail className="w-4 h-4" />,
    color: 'red',
    actions: ['send_email', 'get_messages', 'search_messages', 'add_label'],
    defaultData: {
      integrationConfig: { integrationType: 'gmail', action: 'send_email', parameters: {} },
    },
  },
  {
    type: 'integration',
    integrationType: 'stripe',
    label: 'Stripe',
    description: 'Payment processing',
    icon: <CreditCard className="w-4 h-4" />,
    color: 'indigo',
    actions: ['create_payment', 'create_customer', 'refund'],
    defaultData: {
      integrationConfig: { integrationType: 'stripe', action: 'create_payment', parameters: {} },
    },
  },
  {
    type: 'integration',
    integrationType: 'github',
    label: 'GitHub',
    description: 'Repository actions',
    icon: <Github className="w-4 h-4" />,
    color: 'gray',
    actions: ['create_issue', 'create_pr', 'add_comment'],
    defaultData: {
      integrationConfig: { integrationType: 'github', action: 'create_issue', parameters: {} },
    },
  },
  {
    type: 'integration',
    integrationType: 'sendgrid',
    label: 'SendGrid',
    description: 'Email delivery',
    icon: <Mail className="w-4 h-4" />,
    color: 'blue',
    actions: ['send_email', 'send_template'],
    defaultData: {
      integrationConfig: { integrationType: 'sendgrid', action: 'send_email', parameters: {} },
    },
  },
  {
    type: 'integration',
    integrationType: 'twilio',
    label: 'Twilio',
    description: 'SMS & voice',
    icon: <Phone className="w-4 h-4" />,
    color: 'red',
    actions: ['send_sms', 'make_call'],
    defaultData: {
      integrationConfig: { integrationType: 'twilio', action: 'send_sms', parameters: {} },
    },
  },
  {
    type: 'integration',
    integrationType: 'aws_s3',
    label: 'AWS S3',
    description: 'File storage',
    icon: <Cloud className="w-4 h-4" />,
    color: 'orange',
    actions: ['upload_file', 'download_file', 'list_files'],
    defaultData: {
      integrationConfig: { integrationType: 'aws_s3', action: 'upload_file', parameters: {} },
    },
  },
  {
    type: 'integration',
    integrationType: 'zendesk',
    label: 'Zendesk',
    description: 'Customer support',
    icon: <Headphones className="w-4 h-4" />,
    color: 'green',
    actions: ['create_ticket', 'update_ticket', 'add_comment'],
    defaultData: {
      integrationConfig: { integrationType: 'zendesk', action: 'create_ticket', parameters: {} },
    },
  },
  {
    type: 'integration',
    integrationType: 'hubspot',
    label: 'HubSpot',
    description: 'CRM & marketing',
    icon: <Users className="w-4 h-4" />,
    color: 'orange',
    actions: ['create_contact', 'update_deal', 'send_email'],
    defaultData: {
      integrationConfig: { integrationType: 'hubspot', action: 'create_contact', parameters: {} },
    },
  },
  {
    type: 'integration',
    integrationType: 'salesforce',
    label: 'Salesforce',
    description: 'Enterprise CRM',
    icon: <BarChart3 className="w-4 h-4" />,
    color: 'blue',
    actions: ['create_lead', 'update_opportunity', 'query'],
    defaultData: {
      integrationConfig: { integrationType: 'salesforce', action: 'create_lead', parameters: {} },
    },
  },
  {
    type: 'integration',
    integrationType: 'google_sheets',
    label: 'Google Sheets',
    description: 'Spreadsheet data',
    icon: <FileSpreadsheet className="w-4 h-4" />,
    color: 'green',
    actions: ['read_range', 'write_range', 'append_row'],
    defaultData: {
      integrationConfig: { integrationType: 'google_sheets', action: 'append_row', parameters: {} },
    },
  },
]

// Draggable palette item component
function DraggablePaletteItem({ item, onDragStart }: { item: PaletteItem, onDragStart: (e: DragEvent, item: PaletteItem) => void }) {
  const colorClasses: Record<string, string> = {
    purple: 'bg-purple-100 hover:bg-purple-200 text-purple-900 border-purple-300',
    blue: 'bg-blue-100 hover:bg-blue-200 text-blue-900 border-blue-300',
    green: 'bg-green-100 hover:bg-green-200 text-green-900 border-green-300',
    orange: 'bg-orange-100 hover:bg-orange-200 text-orange-900 border-orange-300',
    amber: 'bg-amber-100 hover:bg-amber-200 text-amber-900 border-amber-300',
    indigo: 'bg-indigo-100 hover:bg-indigo-200 text-indigo-900 border-indigo-300',
    gray: 'bg-gray-100 hover:bg-gray-200 text-gray-900 border-gray-300',
    red: 'bg-red-100 hover:bg-red-200 text-red-900 border-red-300',
  }

  // Check if this is an integration item with connection status
  const integrationItem = item as IntegrationPaletteItem
  const isIntegration = item.type === 'integration'
  const isConnected = integrationItem?.connected

  // Apply different styling for disconnected integrations
  const borderStyle = isIntegration && !isConnected ? 'border-dashed border-orange-400' : ''

  return (
    <div
      draggable
      onDragStart={(e) => onDragStart(e, item)}
      className={`px-3 py-2 ${colorClasses[item.color]} border rounded-lg cursor-grab active:cursor-grabbing flex items-center gap-2 transition-all hover:shadow-md relative ${borderStyle}`}
      title={isIntegration && !isConnected ? 'Not connected - configure credentials in Integrations page' : ''}
    >
      <GripVertical className="w-3 h-3 opacity-50" />
      {item.icon}
      <div className="flex-1 min-w-0">
        <div className="font-medium text-sm truncate flex items-center gap-1">
          {item.label}
          {isIntegration && (
            isConnected ? (
              <CheckCircle className="w-3 h-3 text-green-600 flex-shrink-0" />
            ) : (
              <AlertTriangle className="w-3 h-3 text-orange-500 flex-shrink-0" />
            )
          )}
        </div>
        <div className="text-xs opacity-75 truncate">
          {isIntegration && !isConnected ? 'Not connected' : item.description}
        </div>
      </div>
    </div>
  )
}

const initialNodes: Node<AgentNodeData>[] = []
const initialEdges: Edge[] = []

// Main component wrapped in ReactFlowProvider
function WorkflowDesignerInner() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const location = useLocation()
  const reactFlowWrapper = useRef<HTMLDivElement>(null)
  const { project } = useReactFlow()
  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes)
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges)
  const [workflowName, setWorkflowName] = useState('Untitled Workflow')
  const [workflowId, setWorkflowId] = useState<string | null>(null)
  const [selectedNode, setSelectedNode] = useState<Node<AgentNodeData> | null>(null)
  const [paramJsonText, setParamJsonText] = useState<string>('{}') // Local state for params textarea
  const [paramJsonError, setParamJsonError] = useState<string | null>(null)
  const [isSaving, setIsSaving] = useState(false)
  const [isExecuting, setIsExecuting] = useState(false)
  const [showTestInputModal, setShowTestInputModal] = useState(false)
  const [testInputData, setTestInputData] = useState<string>('{\n  "ticket_id": "12345",\n  "title": "Example ticket",\n  "description": "This is a test ticket"\n}')
  const [executionLogs, setExecutionLogs] = useState<Array<{timestamp: string, message: string, type: string}>>([])
  const [showLogs, setShowLogs] = useState(false)
  const [toast, setToast] = useState<{ message: string; type: 'success' | 'error' } | null>(null)
  const [showShortcuts, setShowShortcuts] = useState(false)
  const [showCostBreakdown, setShowCostBreakdown] = useState(false)
  const [budgetLimit, setBudgetLimit] = useState<number>(1.0) // Default $1 budget
  const [totalCost, setTotalCost] = useState<number>(0)
  const [ws, setWs] = useState<WebSocket | null>(null)
  const [testMode, setTestMode] = useState(false) // Dry run mode
  const [showHistory, setShowHistory] = useState(false)
  const [executionHistory, setExecutionHistory] = useState<Array<{
    timestamp: string,
    duration: number,
    cost: number,
    status: 'success' | 'failed',
    nodeCount: number
  }>>([])
  const [validationErrors, setValidationErrors] = useState<string[]>([])
  const [failedNode, setFailedNode] = useState<string | null>(null)
  const startTimeRef = useRef<number>(0)
  const [showTemplateModal, setShowTemplateModal] = useState(false)
  const [availableActions, setAvailableActions] = useState<Array<{name: string, description?: string}>>([])
  const [loadingActions, setLoadingActions] = useState(false)
  const [testExecuting, setTestExecuting] = useState(false)
  const [testResult, setTestResult] = useState<{success: boolean, data?: any, error?: string, duration_ms?: number} | null>(null)

  // Undo/Redo history
  const [history, setHistory] = useState<Array<{ nodes: Node<AgentNodeData>[], edges: Edge[] }>>([])
  const [historyIndex, setHistoryIndex] = useState(-1)

  // Dynamic integration palette
  const [integrationPaletteItems, setIntegrationPaletteItems] = useState<IntegrationPaletteItem[]>(staticIntegrationPaletteItems)
  const [loadingIntegrations, setLoadingIntegrations] = useState(false)

  // Function to fetch integrations - extracted so it can be called on mount and on focus
  const fetchIntegrations = useCallback(async () => {
    setLoadingIntegrations(true)
    try {
      const response = await api.get('/api/connections/palette')
      if (response.data?.integrations) {
        const dynamicItems: IntegrationPaletteItem[] = response.data.integrations.map((int: any) => ({
          type: 'integration' as NodeType,
          integrationType: int.id as IntegrationType,
          label: int.display_name,
          description: int.description || int.category,
          icon: getIntegrationIcon(int.id, int.category),
          color: getCategoryColor(int.category),
          actions: int.actions || [],
          connected: int.connected,
          defaultData: {
            integrationConfig: {
              integrationType: int.id,
              action: int.actions?.[0] || '',
              parameters: {},
              isConnected: int.connected ?? false, // Pass connection status to node
            },
          },
        }))
        setIntegrationPaletteItems(dynamicItems)
      }
    } catch (err) {
      console.warn('Failed to fetch integrations, using static list:', err)
      // Keep static items as fallback
    } finally {
      setLoadingIntegrations(false)
    }
  }, [])

  // Fetch integrations on mount
  useEffect(() => {
    fetchIntegrations()
  }, [fetchIntegrations])

  // Re-fetch integrations when window regains focus (user may have connected from another tab)
  useEffect(() => {
    const handleFocus = () => {
      fetchIntegrations()
    }
    window.addEventListener('focus', handleFocus)
    return () => window.removeEventListener('focus', handleFocus)
  }, [fetchIntegrations])

  // Update existing integration nodes when palette connection status changes
  // This ensures nodes on canvas reflect the latest connection state
  useEffect(() => {
    if (integrationPaletteItems.length > 0 && nodes.length > 0) {
      setNodes((nds) =>
        nds.map((node) => {
          if (node.type === 'integration' && node.data.integrationConfig?.integrationType) {
            const integrationItem = integrationPaletteItems.find(
              item => item.integrationType === node.data.integrationConfig?.integrationType
            )
            const currentIsConnected = node.data.integrationConfig?.isConnected
            const newIsConnected = integrationItem?.connected ?? false

            // Only update if connection status actually changed
            if (currentIsConnected !== newIsConnected) {
              return {
                ...node,
                data: {
                  ...node.data,
                  integrationConfig: {
                    ...node.data.integrationConfig,
                    isConnected: newIsConnected,
                  },
                },
              }
            }
          }
          return node
        })
      )
    }
  }, [integrationPaletteItems]) // Re-run when palette items change

  // Save state to history (for undo/redo)
  const saveToHistory = useCallback(() => {
    const newHistory = history.slice(0, historyIndex + 1)
    newHistory.push({ nodes: JSON.parse(JSON.stringify(nodes)), edges: JSON.parse(JSON.stringify(edges)) })
    if (newHistory.length > 50) newHistory.shift() // Keep last 50 states
    setHistory(newHistory)
    setHistoryIndex(newHistory.length - 1)
  }, [nodes, edges, history, historyIndex])

  const undo = useCallback(() => {
    if (historyIndex > 0) {
      const prevState = history[historyIndex - 1]
      setNodes(prevState.nodes)
      setEdges(prevState.edges)
      setHistoryIndex(historyIndex - 1)
      showToast('Undo', 'success')
    }
  }, [historyIndex, history, setNodes, setEdges])

  const redo = useCallback(() => {
    if (historyIndex < history.length - 1) {
      const nextState = history[historyIndex + 1]
      setNodes(nextState.nodes)
      setEdges(nextState.edges)
      setHistoryIndex(historyIndex + 1)
      showToast('Redo', 'success')
    }
  }, [historyIndex, history, setNodes, setEdges])

  // Load workflow from URL parameter
  useEffect(() => {
    const id = searchParams.get('id')
    if (id) {
      loadWorkflow(id)
    }
  }, [searchParams])

  // Load template from location state
  useEffect(() => {
    const state = location.state as { template?: WorkflowTemplate } | null
    if (state?.template) {
      const template = state.template
      setWorkflowName(template.name)
      setNodes(template.nodes as Node<AgentNodeData>[])
      setEdges(template.edges)
      showToast(`Loaded template: ${template.name}`, 'success')
      // Clear location state to avoid reloading template on refresh
      window.history.replaceState({}, document.title)
    }
  }, [location.state])

  // Auto-hide toast after 3 seconds
  useEffect(() => {
    if (toast) {
      const timer = setTimeout(() => setToast(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [toast])

  // Clear test result when node or action changes
  useEffect(() => {
    setTestResult(null)
  }, [selectedNode?.id, selectedNode?.data?.integrationConfig?.action])

  // Fetch available actions when integration type changes
  useEffect(() => {
    const integrationType = selectedNode?.data?.integrationConfig?.integrationType
    if (selectedNode?.data?.type === 'integration' && integrationType && integrationType !== 'custom') {
      setLoadingActions(true)
      fetch(`/api/connections/${integrationType}/actions`)
        .then(res => res.ok ? res.json() : null)
        .then(data => {
          if (data?.actions) {
            setAvailableActions(data.actions)
          } else {
            setAvailableActions([])
          }
        })
        .catch(() => setAvailableActions([]))
        .finally(() => setLoadingActions(false))
    } else {
      setAvailableActions([])
    }
  }, [selectedNode?.data?.integrationConfig?.integrationType, selectedNode?.data?.type])

  // Test execute an integration action
  const handleTestExecute = async () => {
    if (!selectedNode?.data?.integrationConfig) return

    const { integrationType, action, parameters } = selectedNode.data.integrationConfig
    if (!integrationType || !action) {
      showToast('Please select an integration and action first', 'error')
      return
    }

    setTestExecuting(true)
    setTestResult(null)

    try {
      const response = await fetch(`/api/connections/${integrationType}/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          action_name: action,
          parameters: parameters || {},
          organization_id: 'default-org'
        })
      })

      const result = await response.json()
      setTestResult(result)

      if (result.success) {
        showToast(`Action executed successfully (${result.duration_ms}ms)`, 'success')
      } else {
        showToast(`Action failed: ${result.error}`, 'error')
      }
    } catch (err: any) {
      setTestResult({ success: false, error: err.message || 'Execution failed' })
      showToast('Failed to execute action', 'error')
    } finally {
      setTestExecuting(false)
    }
  }

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ctrl/Cmd + Z: Undo
      if ((e.ctrlKey || e.metaKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault()
        undo()
      }
      // Ctrl/Cmd + Shift + Z or Ctrl/Cmd + Y: Redo
      else if (((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'z') || ((e.ctrlKey || e.metaKey) && e.key === 'y')) {
        e.preventDefault()
        redo()
      }
      // Ctrl/Cmd + S: Save workflow
      else if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault()
        saveWorkflow()
      }
      // Ctrl/Cmd + N: New workflow
      else if ((e.ctrlKey || e.metaKey) && e.key === 'n') {
        e.preventDefault()
        newWorkflow()
      }
      // Ctrl/Cmd + B: Browse gallery
      else if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
        e.preventDefault()
        navigate('/workflows/gallery')
      }
      // Delete/Backspace: Delete selected node
      else if ((e.key === 'Delete' || e.key === 'Backspace') && selectedNode) {
        // Only delete if not typing in an input field
        if (document.activeElement?.tagName !== 'INPUT' && document.activeElement?.tagName !== 'TEXTAREA') {
          e.preventDefault()
          deleteSelectedNode()
          saveToHistory()
        }
      }
      // Escape: Deselect node or close shortcuts panel
      else if (e.key === 'Escape') {
        if (showShortcuts) {
          setShowShortcuts(false)
        } else if (selectedNode) {
          setSelectedNode(null)
        }
      }
      // ?: Toggle keyboard shortcuts help
      else if (e.key === '?' && !showShortcuts) {
        e.preventDefault()
        setShowShortcuts(true)
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [selectedNode, navigate, undo, redo, saveToHistory])

  const deleteSelectedNode = () => {
    if (!selectedNode) return

    // Remove node
    setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id))

    // Remove connected edges
    setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id))

    setSelectedNode(null)
    showToast('Node deleted', 'success')
  }

  const showToast = (message: string, type: 'success' | 'error') => {
    setToast({ message, type })
  }

  const onConnect = useCallback(
    (connection: Connection) => {
      setEdges((eds) => addEdge(connection, eds))
      setTimeout(() => saveToHistory(), 100)
    },
    [setEdges, saveToHistory]
  )

  const onNodeClick = useCallback((_event: React.MouseEvent, node: Node<AgentNodeData>) => {
    setSelectedNode(node)
    // Initialize param JSON text when selecting a node
    const params = node.data.integrationConfig?.parameters || {}
    setParamJsonText(JSON.stringify(params, null, 2))
    setParamJsonError(null)
  }, [])

  // Drag and drop handlers
  const onDragStart = useCallback((event: DragEvent, item: PaletteItem) => {
    event.dataTransfer.setData('application/reactflow', JSON.stringify(item))
    event.dataTransfer.effectAllowed = 'move'
  }, [])

  const onDragOver = useCallback((event: DragEvent) => {
    event.preventDefault()
    event.dataTransfer.dropEffect = 'move'
  }, [])

  const onDrop = useCallback(
    (event: DragEvent) => {
      event.preventDefault()

      const data = event.dataTransfer.getData('application/reactflow')
      if (!data) return

      const item: PaletteItem = JSON.parse(data)

      // Get the position where the node was dropped
      const reactFlowBounds = reactFlowWrapper.current?.getBoundingClientRect()
      if (!reactFlowBounds) return

      const position = project({
        x: event.clientX - reactFlowBounds.left,
        y: event.clientY - reactFlowBounds.top,
      })

      const newNode: Node<AgentNodeData> = {
        id: `${item.type}-${Date.now()}`,
        type: item.type,
        position,
        data: {
          label: item.label,
          type: item.type,
          status: 'idle',
          ...item.defaultData,
        },
      }

      setNodes((nds) => [...nds, newNode])
      setTimeout(() => saveToHistory(), 100)
    },
    [project, setNodes, saveToHistory]
  )

  const newWorkflow = () => {
    if (nodes.length > 0 || edges.length > 0) {
      if (!confirm('Clear current workflow? Any unsaved changes will be lost.')) {
        return
      }
    }
    setNodes([])
    setEdges([])
    setWorkflowName('Untitled Workflow')
    setWorkflowId(null)
    setSelectedNode(null)
    navigate('/workflows')
  }

  const handleSelectTemplate = (template: WorkflowTemplate) => {
    setWorkflowName(template.name)
    setNodes(template.nodes as Node<AgentNodeData>[])
    setEdges(template.edges)
    setShowTemplateModal(false)
    showToast(`Loaded template: ${template.name}`, 'success')
  }

  const saveWorkflow = async () => {
    if (!workflowName.trim()) {
      showToast('Please enter a workflow name', 'error')
      return
    }

    if (nodes.length === 0) {
      showToast('Add at least one node to save', 'error')
      return
    }

    setIsSaving(true)
    try {
      const workflowData = {
        name: workflowName,
        nodes: nodes,
        edges: edges,
      }

      // Use updateWorkflow if editing an existing workflow, otherwise createWorkflow
      let result
      if (workflowId) {
        result = await api.updateWorkflow(workflowId, workflowData)
        showToast('Workflow updated successfully', 'success')
      } else {
        result = await api.createWorkflow(workflowData)
        setWorkflowId(result.id)
        showToast('Workflow saved successfully', 'success')
      }
    } catch (error) {
      console.error('Error saving workflow:', error)
      showToast('Error saving workflow. Check console for details.', 'error')
    } finally {
      setIsSaving(false)
    }
  }

  const loadWorkflow = async (id: string) => {
    try {
      const workflow = await api.getWorkflowById(id)

      if (workflow) {
        setWorkflowName(workflow.name)
        setWorkflowId(workflow.id)

        // Refresh connection status for integration nodes
        const updatedNodes = (workflow.nodes as Node<AgentNodeData>[]).map(node => {
          if (node.type === 'integration' && node.data.integrationConfig?.integrationType) {
            // Find the matching integration in the palette to get current connection status
            const integrationItem = integrationPaletteItems.find(
              item => item.integrationType === node.data.integrationConfig?.integrationType
            )
            return {
              ...node,
              data: {
                ...node.data,
                integrationConfig: {
                  ...node.data.integrationConfig,
                  isConnected: integrationItem?.connected ?? false,
                },
              },
            }
          }
          return node
        })

        setNodes(updatedNodes)
        setEdges(workflow.edges as Edge[])
        showToast('Workflow loaded successfully', 'success')
      } else {
        showToast('Workflow not found', 'error')
      }
    } catch (error) {
      console.error('Error loading workflow:', error)
      showToast('Error loading workflow', 'error')
    }
  }

  const validateWorkflow = (): string[] => {
    const errors: string[] = []

    // Check for nodes
    if (nodes.length === 0) {
      errors.push('Workflow must have at least one node')
      return errors
    }

    // Check for disconnected nodes (except if there's only one node)
    if (nodes.length > 1) {
      const connectedNodes = new Set<string>()
      edges.forEach(edge => {
        connectedNodes.add(edge.source)
        connectedNodes.add(edge.target)
      })

      const disconnectedNodes = nodes.filter(node => !connectedNodes.has(node.id))
      if (disconnectedNodes.length > 0 && edges.length > 0) {
        errors.push(`${disconnectedNodes.length} disconnected node(s): ${disconnectedNodes.map(n => n.data.label).join(', ')}`)
      }
    }

    // Check for cycles (simple check)
    const hasIncomingEdge = new Set<string>()
    edges.forEach(edge => hasIncomingEdge.add(edge.target))
    const startNodes = nodes.filter(node => !hasIncomingEdge.has(node.id))

    if (startNodes.length === 0 && nodes.length > 0 && edges.length > 0) {
      errors.push('Workflow has a cycle - no start node found')
    }

    // Check for empty node labels
    const nodesWithoutLabels = nodes.filter(node => !node.data.label || node.data.label.trim() === '')
    if (nodesWithoutLabels.length > 0) {
      errors.push(`${nodesWithoutLabels.length} node(s) without labels`)
    }

    // Check for disconnected integrations (no credentials configured)
    const disconnectedIntegrations = nodes.filter(
      node => node.type === 'integration' && node.data.integrationConfig?.isConnected === false
    )
    if (disconnectedIntegrations.length > 0) {
      const integrationNames = disconnectedIntegrations.map(n => n.data.label).join(', ')
      errors.push(`Integration(s) not connected: ${integrationNames}. Please configure credentials in Integrations page.`)
    }

    return errors
  }

  const executeWorkflow = async (inputData?: Record<string, any>) => {
    // Close the test input modal
    setShowTestInputModal(false)

    // Refresh integration connection status before validation
    // This ensures we use the latest connection state, not stale data from when node was dropped
    const refreshedNodes = nodes.map((node) => {
      if (node.type === 'integration' && node.data.integrationConfig?.integrationType) {
        const integrationItem = integrationPaletteItems.find(
          item => item.integrationType === node.data.integrationConfig?.integrationType
        )
        return {
          ...node,
          data: {
            ...node.data,
            integrationConfig: {
              ...node.data.integrationConfig,
              isConnected: integrationItem?.connected ?? false,
            },
          },
        }
      }
      return node
    })

    // Update the nodes state with refreshed connection status
    setNodes(refreshedNodes)

    // Validate using the refreshed nodes directly (not stale state)
    const validateRefreshedWorkflow = (): string[] => {
      const errors: string[] = []

      if (refreshedNodes.length === 0) {
        errors.push('Workflow must have at least one node')
        return errors
      }

      if (refreshedNodes.length > 1) {
        const connectedNodeIds = new Set<string>()
        edges.forEach(edge => {
          connectedNodeIds.add(edge.source)
          connectedNodeIds.add(edge.target)
        })

        const disconnectedNodes = refreshedNodes.filter(node => !connectedNodeIds.has(node.id))
        if (disconnectedNodes.length > 0 && edges.length > 0) {
          errors.push(`${disconnectedNodes.length} disconnected node(s): ${disconnectedNodes.map(n => n.data.label).join(', ')}`)
        }
      }

      const hasIncomingEdge = new Set<string>()
      edges.forEach(edge => hasIncomingEdge.add(edge.target))
      const startNodes = refreshedNodes.filter(node => !hasIncomingEdge.has(node.id))

      if (startNodes.length === 0 && refreshedNodes.length > 0 && edges.length > 0) {
        errors.push('Workflow has a cycle - no start node found')
      }

      const nodesWithoutLabels = refreshedNodes.filter(node => !node.data.label || node.data.label.trim() === '')
      if (nodesWithoutLabels.length > 0) {
        errors.push(`${nodesWithoutLabels.length} node(s) without labels`)
      }

      // Check for disconnected integrations using REFRESHED data
      const disconnectedIntegrations = refreshedNodes.filter(
        node => node.type === 'integration' && node.data.integrationConfig?.isConnected === false
      )
      if (disconnectedIntegrations.length > 0) {
        const integrationNames = disconnectedIntegrations.map(n => n.data.label).join(', ')
        errors.push(`Integration(s) not connected: ${integrationNames}. Please configure credentials in Integrations page.`)
      }

      return errors
    }

    const errors = validateRefreshedWorkflow()
    if (errors.length > 0) {
      setValidationErrors(errors)
      showToast(`Validation failed: ${errors[0]}`, 'error')
      return
    }
    setValidationErrors([])

    if (testMode) {
      showToast('Running in test mode (dry run)', 'success')
      addExecutionLog('Test mode: Workflow will not execute actual agents', 'info')
    }

    // Reset execution state
    startTimeRef.current = Date.now()
    setIsExecuting(true)
    setExecutionLogs([])
    setShowLogs(true)
    setFailedNode(null)

    // Log the input data
    if (inputData && Object.keys(inputData).length > 0) {
      addExecutionLog(`Input data: ${JSON.stringify(inputData, null, 2)}`, 'info')
    }

    // Reset all node statuses to idle
    setNodes((nds) =>
      nds.map((node) => ({
        ...node,
        data: { ...node.data, status: 'idle', cost: undefined, executionTime: undefined, error: undefined },
      }))
    )

    // Reset edge animations
    setEdges((eds) => eds.map((edge) => ({ ...edge, animated: false })))

    try {
      // Always use WebSocket for live execution updates
      // Use different endpoint for saved vs unsaved workflows
      const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = workflowId
        ? `${wsProtocol}//${window.location.host}/api/workflows/${workflowId}/execute`
        : `${wsProtocol}//${window.location.host}/api/workflows/temp/execute`

      addExecutionLog(workflowId
        ? `Connecting to execute saved workflow (${workflowId})...`
        : 'Connecting to execute temporary workflow...', 'info')
      let connectionEstablished = false
      let websocket: WebSocket

      try {
        websocket = new WebSocket(wsUrl)
      } catch (wsError) {
        console.error('WebSocket creation error:', wsError)
        addExecutionLog(`Failed to create WebSocket connection: ${wsError}`, 'error')
        showToast('Failed to connect to execution engine', 'error')
        setIsExecuting(false)
        return
      }

      // Set a connection timeout - if we don't establish connection within 5 seconds, abort
      const connectionTimeout = setTimeout(() => {
        if (!connectionEstablished && websocket.readyState !== WebSocket.OPEN) {
          console.warn('WebSocket connection timeout')
          addExecutionLog('Connection timeout - server may be unavailable', 'error')
          showToast('Connection timeout - is the backend server running?', 'error')
          setIsExecuting(false)
          try {
            websocket.close()
          } catch (e) {
            // Ignore close errors
          }
        }
      }, 5000)

      websocket.onopen = () => {
        connectionEstablished = true
        clearTimeout(connectionTimeout)
        console.log('WebSocket connected')
        addExecutionLog('Connected to execution engine', 'success')

        // Send workflow data to start execution
        try {
          websocket.send(
            JSON.stringify({
              action: 'start',
              workflow: {
                nodes: nodes.map((n) => ({
                  id: n.id,
                  type: n.type,
                  position: n.position,
                  data: n.data,
                })),
                edges: edges.map((e) => ({
                  id: e.id,
                  source: e.source,
                  target: e.target,
                  label: e.label,
                })),
              },
              inputData: inputData || {},
            })
          )
          addExecutionLog('Workflow data sent, waiting for execution...', 'info')
        } catch (sendError) {
          console.error('Error sending workflow data:', sendError)
          addExecutionLog(`Error sending workflow data: ${sendError}`, 'error')
          setIsExecuting(false)
        }
      }

      websocket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          handleExecutionEvent(data)
        } catch (e) {
          console.error('Error processing WebSocket message:', e, event.data)
          addExecutionLog(`Error processing message: ${e}`, 'error')
        }
      }

      websocket.onerror = (error) => {
        clearTimeout(connectionTimeout)
        console.error('WebSocket error:', error)
        addExecutionLog('Connection error occurred - check if the backend server is running', 'error')
        showToast('Execution connection error - is the backend running?', 'error')
        setIsExecuting(false)
      }

      websocket.onclose = (event) => {
        clearTimeout(connectionTimeout)
        console.log('WebSocket closed', event.code, event.reason)

        // Check if connection was never established (immediate close)
        if (!connectionEstablished) {
          addExecutionLog('Failed to connect - backend server may be unavailable', 'error')
          showToast('Cannot connect to server. Please ensure the backend is running.', 'error')
        } else if (event.code !== 1000) {
          // Abnormal closure after connection was established
          const reason = event.reason || 'Unknown reason'
          addExecutionLog(`Connection closed unexpectedly (code: ${event.code}, reason: ${reason})`, 'error')
          showToast('Connection to server lost', 'error')
        } else {
          addExecutionLog('Disconnected from execution engine', 'info')
        }
        setIsExecuting(false)
        setWs(null)
      }

      setWs(websocket)
    } catch (error) {
      console.error('Error starting execution:', error)
      showToast('Failed to start execution', 'error')
      setIsExecuting(false)
    }
  }

  const handleExecutionEvent = (event: any) => {
    console.log('Execution event:', event)

    switch (event.event_type) {
      case 'execution_started':
        addExecutionLog(event.message || 'Workflow started', 'info')
        break

      case 'node_status_changed':
        updateNodeStatus(event.node_id, event.status, event.cost, event.execution_time, event.error)

        // Track failed node for retry
        if (event.status === 'error') {
          setFailedNode(event.node_id)
        }

        // 🔍 NODE OUTPUT CONSOLE LOGGING - for faster development debugging
        // Print node output to browser console so developers can inspect results
        // without relying on Discord or other external integrations
        if (event.status === 'success' && event.data) {
          const nodeLabel = event.message?.match(/Completed (.+)/)?.[1] || event.node_id
          console.group(`📦 Node Output: ${nodeLabel}`)
          console.log('%cNode ID:', 'font-weight: bold; color: #6366f1', event.node_id)
          console.log('%cStatus:', 'font-weight: bold; color: #22c55e', event.status)
          if (event.cost != null) {
            console.log('%cCost:', 'font-weight: bold; color: #f59e0b', `$${event.cost.toFixed(4)}`)
          }
          if (event.execution_time != null) {
            console.log('%cDuration:', 'font-weight: bold; color: #3b82f6', `${event.execution_time.toFixed(2)}s`)
          }
          console.log('%cOutput Data:', 'font-weight: bold; color: #8b5cf6')
          console.dir(event.data, { depth: null })
          console.groupEnd()
        } else if (event.status === 'error') {
          console.group(`❌ Node Error: ${event.node_id}`)
          console.error('Error:', event.error)
          console.groupEnd()
        }

        // Add cost and time info to log message for completed nodes
        let logMessage = event.message || `Node ${event.node_id} status: ${event.status}`
        if (event.status === 'success' && event.cost != null && typeof event.cost === 'number') {
          logMessage += ` | Cost: $${event.cost.toFixed(4)}`
          if (event.execution_time != null && typeof event.execution_time === 'number') {
            logMessage += ` | Time: ${event.execution_time.toFixed(2)}s`
          }
        } else if (event.status === 'error' && event.error) {
          logMessage += ` | Error: ${event.error}`
        }

        addExecutionLog(logMessage, event.status === 'error' ? 'error' : 'info')

        // Animate edges when node starts running
        if (event.status === 'running') {
          animateNodeEdges(event.node_id, true)
        } else if (event.status === 'success' || event.status === 'error') {
          animateNodeEdges(event.node_id, false)
        }
        break

      case 'execution_completed':
        addExecutionLog(event.message || 'Workflow completed', 'success')
        // Calculate and log final cost
        const finalCost = nodes.reduce((sum, node) => sum + (node.data.cost || 0), 0)
        addExecutionLog(`Total execution cost: $${finalCost.toFixed(4)}`, 'success')
        showToast('Workflow executed successfully!', 'success')

        // Add to execution history
        const duration = startTimeRef.current ? (Date.now() - startTimeRef.current) / 1000 : 0
        setExecutionHistory(prev => [{
          timestamp: new Date().toLocaleString(),
          duration,
          cost: finalCost,
          status: 'success' as const,
          nodeCount: nodes.length
        }, ...prev].slice(0, 10)) // Keep last 10 executions

        setIsExecuting(false)
        break

      case 'execution_failed':
        addExecutionLog(event.message || 'Workflow failed', 'error')
        showToast('Workflow execution failed', 'error')

        // Add to execution history
        const failDuration = startTimeRef.current ? (Date.now() - startTimeRef.current) / 1000 : 0
        setExecutionHistory(prev => [{
          timestamp: new Date().toLocaleString(),
          duration: failDuration,
          cost: totalCost,
          status: 'failed' as const,
          nodeCount: nodes.length
        }, ...prev].slice(0, 10))

        setIsExecuting(false)
        break

      case 'print_output':
        // Handle print node output - display in Execution Log
        const printData = event.data || {}
        const printLabel = printData.label || 'Output'
        const printMessage = printData.message || event.message || ''
        const logLevel = printData.logLevel || 'info'

        // Format the log entry with appropriate styling
        const logType = logLevel === 'error' ? 'error' : logLevel === 'warning' ? 'error' : 'info'
        const emoji = logLevel === 'error' ? '❌' : logLevel === 'warning' ? '⚠️' : logLevel === 'debug' ? '🔍' : '📤'
        addExecutionLog(`${emoji} [${printLabel}] ${printMessage}`, logType)

        // Also log to browser console for developer visibility
        console.group(`📤 Print Output: ${printLabel}`)
        console.log('%cMessage:', 'font-weight: bold; color: #0d9488', printMessage)
        console.log('%cLevel:', 'font-weight: bold; color: #6b7280', logLevel)
        if (printData.timestamp) {
          console.log('%cTimestamp:', 'font-weight: bold; color: #6b7280', printData.timestamp)
        }
        console.groupEnd()
        break

      case 'error':
        addExecutionLog(event.message || 'An error occurred', 'error')
        showToast(event.message || 'An error occurred', 'error')
        setIsExecuting(false)
        break
    }
  }

  const updateNodeStatus = (
    nodeId: string,
    status: string,
    cost?: number,
    executionTime?: number,
    error?: string
  ) => {
    setNodes((nds) => {
      const updatedNodes = nds.map((node) => {
        if (node.id === nodeId) {
          return {
            ...node,
            data: {
              ...node.data,
              status: status as any,
              cost,
              executionTime,
              error,
            },
          }
        }
        return node
      })

      // Update total cost after node status update
      const newTotalCost = updatedNodes.reduce((sum, node) => {
        return sum + (node.data.cost || 0)
      }, 0)
      setTotalCost(newTotalCost)

      // Check budget alert
      if (newTotalCost > budgetLimit && status === 'success') {
        showToast(`Budget exceeded! Total cost: $${newTotalCost.toFixed(4)}`, 'error')
      }

      return updatedNodes
    })
  }

  const calculateEstimatedCost = () => {
    // Estimate cost based on node types and LLM models
    const modelCosts: Record<string, Record<string, number>> = {
      supervisor: {
        'gpt-4': 0.05,
        'gpt-3.5-turbo': 0.002,
        'claude-3-5-sonnet-20241022': 0.03,
        'claude-2': 0.03,
      },
      worker: {
        'gpt-4': 0.03,
        'gpt-3.5-turbo': 0.001,
        'claude-3-5-sonnet-20241022': 0.02,
        'claude-2': 0.02,
      },
    }
    const toolCost = 0.0001

    return nodes.reduce((sum, node) => {
      const nodeType = node.data.type
      if (nodeType === 'supervisor' || nodeType === 'worker') {
        const model = node.data.llmModel || 'gpt-3.5-turbo'
        return sum + (modelCosts[nodeType][model] || 0.001)
      } else {
        return sum + toolCost
      }
    }, 0)
  }

  const animateNodeEdges = (nodeId: string, animated: boolean) => {
    setEdges((eds) =>
      eds.map((edge) => {
        if (edge.source === nodeId || edge.target === nodeId) {
          return { ...edge, animated }
        }
        return edge
      })
    )
  }

  const addExecutionLog = (message: string, type: string) => {
    setExecutionLogs((logs) => [
      ...logs,
      {
        timestamp: new Date().toLocaleTimeString(),
        message,
        type,
      },
    ])
  }

  const stopExecution = () => {
    if (ws) {
      ws.close()
      setWs(null)
      setIsExecuting(false)
      addExecutionLog('Execution stopped by user', 'info')
    }
  }

  const retryFailedNode = () => {
    if (!failedNode) return

    // Reset failed node status
    setNodes((nds) =>
      nds.map((node) => {
        if (node.id === failedNode) {
          return {
            ...node,
            data: { ...node.data, status: 'idle', error: undefined },
          }
        }
        return node
      })
    )

    const failedNodeLabel = nodes.find(n => n.id === failedNode)?.data.label
    addExecutionLog(`Retrying node: ${failedNodeLabel}`, 'info')
    showToast('Retrying failed node...', 'success')
    setFailedNode(null)

    // Re-execute the workflow
    executeWorkflow()
  }

  const exportWorkflow = () => {
    const workflow = {
      name: workflowName,
      nodes,
      edges,
    }
    const blob = new Blob([JSON.stringify(workflow, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${workflowName.replace(/\s+/g, '-').toLowerCase()}.json`
    link.click()
    URL.revokeObjectURL(url)
  }

  const importWorkflow = () => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.json'
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (file) {
        const reader = new FileReader()
        reader.onload = (event) => {
          try {
            const workflow = JSON.parse(event.target?.result as string)
            setWorkflowName(workflow.name)
            setNodes(workflow.nodes)
            setEdges(workflow.edges)
          } catch (error) {
            console.error('Error parsing workflow file:', error)
          }
        }
        reader.readAsText(file)
      }
    }
    input.click()
  }

  return (
    <div className="h-screen flex flex-col">
      {/* Top Toolbar */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex flex-col">
              <input
                type="text"
                value={workflowName}
                onChange={(e) => setWorkflowName(e.target.value)}
                className="text-2xl font-bold border-none focus:outline-none focus:ring-2 focus:ring-blue-500 rounded px-2"
                placeholder="Workflow Name"
              />
              {workflowId && (
                <span className="text-xs text-gray-400 font-mono px-2 select-all" title="Workflow ID (click to select)">
                  ID: {workflowId}
                </span>
              )}
            </div>
            <span className="text-sm text-gray-500">
              {nodes.length} nodes, {edges.length} connections
            </span>
            {isExecuting && totalCost > 0 && (
              <div className="flex items-center gap-2 px-3 py-1.5 bg-green-50 border border-green-200 rounded-lg">
                <DollarSign className="w-4 h-4 text-green-600" />
                <span className="text-sm font-semibold text-green-700">
                  ${totalCost.toFixed(4)}
                </span>
                {totalCost > budgetLimit && (
                  <AlertTriangle className="w-4 h-4 text-orange-600" />
                )}
              </div>
            )}
            {!isExecuting && nodes.length > 0 && (
              <button
                onClick={() => setShowCostBreakdown(true)}
                className="flex items-center gap-2 px-3 py-1.5 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-lg transition-colors"
                title="View cost breakdown"
              >
                <DollarSign className="w-4 h-4 text-gray-600" />
                <span className="text-sm font-medium text-gray-700">
                  Est. ${calculateEstimatedCost().toFixed(4)}
                </span>
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={newWorkflow}
              className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg flex items-center gap-2"
            >
              <FileText className="w-4 h-4" />
              New
            </button>
            <button
              onClick={() => navigate('/workflows/gallery')}
              className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg flex items-center gap-2"
            >
              <FolderOpen className="w-4 h-4" />
              Browse
            </button>
            <button
              onClick={importWorkflow}
              className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg flex items-center gap-2"
            >
              <Upload className="w-4 h-4" />
              Import
            </button>
            <button
              onClick={exportWorkflow}
              className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg flex items-center gap-2"
            >
              <Download className="w-4 h-4" />
              Export
            </button>

            {/* Undo/Redo Buttons */}
            <button
              onClick={undo}
              disabled={historyIndex <= 0}
              className="px-3 py-2 text-gray-700 hover:bg-gray-100 rounded-lg flex items-center gap-1 disabled:opacity-30 disabled:cursor-not-allowed"
              title="Undo (Ctrl+Z)"
            >
              <Undo2 className="w-4 h-4" />
            </button>
            <button
              onClick={redo}
              disabled={historyIndex >= history.length - 1}
              className="px-3 py-2 text-gray-700 hover:bg-gray-100 rounded-lg flex items-center gap-1 disabled:opacity-30 disabled:cursor-not-allowed"
              title="Redo (Ctrl+Y)"
            >
              <Redo2 className="w-4 h-4" />
            </button>

            {/* Test Mode Toggle */}
            <button
              onClick={() => setTestMode(!testMode)}
              className={`px-4 py-2 rounded-lg flex items-center gap-2 ${
                testMode
                  ? 'bg-yellow-100 text-yellow-900 border border-yellow-300'
                  : 'text-gray-700 hover:bg-gray-100'
              }`}
              title="Toggle test mode (dry run)"
            >
              <TestTube className="w-4 h-4" />
              {testMode && 'Test Mode'}
            </button>

            {/* Execution History */}
            {executionHistory.length > 0 && (
              <button
                onClick={() => setShowHistory(true)}
                className="px-4 py-2 text-gray-700 hover:bg-gray-100 rounded-lg flex items-center gap-2"
                title="View execution history"
              >
                <History className="w-4 h-4" />
              </button>
            )}

            <button
              onClick={() => setShowTemplateModal(true)}
              className="px-4 py-2 text-purple-600 border border-purple-600 hover:bg-purple-50 rounded-lg flex items-center gap-2"
              title="Browse workflow templates"
            >
              <Sparkles className="w-4 h-4" />
              Templates
            </button>

            <button
              onClick={saveWorkflow}
              disabled={isSaving}
              className="px-4 py-2 bg-blue-600 text-white hover:bg-blue-700 rounded-lg flex items-center gap-2 disabled:opacity-50"
            >
              <Save className="w-4 h-4" />
              {isSaving ? 'Saving...' : 'Save'}
            </button>
            {!isExecuting ? (
              <button
                onClick={() => setShowTestInputModal(true)}
                className="px-4 py-2 bg-green-600 text-white hover:bg-green-700 rounded-lg flex items-center gap-2"
              >
                <Play className="w-4 h-4" />
                Execute
              </button>
            ) : (
              <button
                onClick={stopExecution}
                className="px-4 py-2 bg-red-600 text-white hover:bg-red-700 rounded-lg flex items-center gap-2"
              >
                <XCircle className="w-4 h-4" />
                Stop
              </button>
            )}

            {/* Retry Failed Node Button */}
            {failedNode && !isExecuting && (
              <button
                onClick={retryFailedNode}
                className="px-4 py-2 bg-orange-600 text-white hover:bg-orange-700 rounded-lg flex items-center gap-2"
                title="Retry failed node"
              >
                <RotateCcw className="w-4 h-4" />
                Retry
              </button>
            )}

            <button
              onClick={() => setShowShortcuts(true)}
              className="px-3 py-2 text-gray-500 hover:bg-gray-100 rounded-lg flex items-center gap-1"
              title="Keyboard shortcuts (?)"
            >
              <HelpCircle className="w-5 h-5" />
            </button>
          </div>
        </div>

        {/* Validation Errors Banner */}
        {validationErrors.length > 0 && (
          <div className="bg-red-50 border-b border-red-200 px-6 py-3">
            <div className="flex items-start gap-3">
              <AlertCircle className="w-5 h-5 text-red-600 mt-0.5 shrink-0" />
              <div className="flex-1">
                <div className="font-semibold text-red-900">Workflow Validation Errors</div>
                <ul className="mt-1 space-y-1 text-sm text-red-700">
                  {validationErrors.map((error, index) => (
                    <li key={index}>• {error}</li>
                  ))}
                </ul>
              </div>
              <button
                onClick={() => setValidationErrors([])}
                className="text-red-600 hover:text-red-800"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="flex-1 flex">
        {/* Left Sidebar - Node Palette with Drag & Drop */}
        <div className="w-72 bg-gray-50 border-r border-gray-200 overflow-y-auto">
          <div className="p-4">
            <h3 className="text-lg font-semibold mb-2">Node Palette</h3>
            <p className="text-xs text-gray-500 mb-4">Drag nodes onto the canvas</p>

            {/* Triggers Section */}
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                <Zap className="w-4 h-4 text-orange-500" />
                Triggers
              </h4>
              <div className="space-y-2">
                {triggerPaletteItems.map((item, idx) => (
                  <DraggablePaletteItem
                    key={`trigger-${idx}`}
                    item={item}
                    onDragStart={onDragStart}
                  />
                ))}
              </div>
            </div>

            {/* Agents Section */}
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                <Crown className="w-4 h-4 text-purple-500" />
                Agents
              </h4>
              <div className="space-y-2">
                {agentPaletteItems.map((item, idx) => (
                  <DraggablePaletteItem
                    key={`agent-${idx}`}
                    item={item}
                    onDragStart={onDragStart}
                  />
                ))}
              </div>
            </div>

            {/* Logic Section */}
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                <GitBranch className="w-4 h-4 text-amber-500" />
                Logic
              </h4>
              <div className="space-y-2">
                {conditionPaletteItems.map((item, idx) => (
                  <DraggablePaletteItem
                    key={`condition-${idx}`}
                    item={item}
                    onDragStart={onDragStart}
                  />
                ))}
              </div>
            </div>

            {/* Data Section */}
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                <Database className="w-4 h-4 text-indigo-500" />
                Data & Knowledge
              </h4>
              <div className="space-y-2">
                {dataPaletteItems.map((item, idx) => (
                  <DraggablePaletteItem
                    key={`data-${idx}`}
                    item={item}
                    onDragStart={onDragStart}
                  />
                ))}
              </div>
            </div>

            {/* Utilities Section */}
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                <Terminal className="w-4 h-4 text-teal-500" />
                Utilities
              </h4>
              <div className="space-y-2">
                {utilityPaletteItems.map((item, idx) => (
                  <DraggablePaletteItem
                    key={`utility-${idx}`}
                    item={item}
                    onDragStart={onDragStart}
                  />
                ))}
              </div>
            </div>

            {/* Events & Automation Section */}
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                <Webhook className="w-4 h-4 text-purple-500" />
                Events & Automation
              </h4>
              <div className="space-y-2">
                {eventPaletteItems.map((item, idx) => (
                  <DraggablePaletteItem
                    key={`event-${idx}`}
                    item={item}
                    onDragStart={onDragStart}
                  />
                ))}
              </div>
            </div>

            {/* Integrations Section */}
            <div className="mb-4">
              <h4 className="text-sm font-semibold text-gray-700 mb-2 flex items-center gap-2">
                <Plug className="w-4 h-4 text-indigo-500" />
                Integrations
              </h4>
              <div className="space-y-2">
                {integrationPaletteItems.map((item, idx) => (
                  <DraggablePaletteItem
                    key={`integration-${idx}`}
                    item={item}
                    onDragStart={onDragStart}
                  />
                ))}
              </div>
            </div>

          </div>
        </div>

        {/* Center - Workflow Canvas */}
        <div className="flex-1 relative" ref={reactFlowWrapper}>
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onDragOver={onDragOver}
            onDrop={onDrop}
            nodeTypes={nodeTypes}
            fitView
            className="bg-gray-100"
          >
            <Background variant={BackgroundVariant.Dots} gap={16} size={1} />
            <Controls />
            <MiniMap
              nodeStrokeColor={(n) => {
                if (n.data.type === 'supervisor') return '#9333ea'
                if (n.data.type === 'worker') return '#3b82f6'
                if (n.data.type === 'trigger') return '#f97316'
                if (n.data.type === 'integration') return '#6366f1'
                if (n.data.type === 'condition') return '#f59e0b'
                return '#10b981'
              }}
              nodeColor={(n) => {
                if (n.data.type === 'supervisor') return '#e9d5ff'
                if (n.data.type === 'worker') return '#dbeafe'
                if (n.data.type === 'trigger') return '#ffedd5'
                if (n.data.type === 'integration') return '#e0e7ff'
                if (n.data.type === 'condition') return '#fef3c7'
                return '#d1fae5'
              }}
              nodeBorderRadius={8}
            />
            <Panel position="top-center" className="bg-white px-4 py-2 rounded-lg shadow-lg">
              <p className="text-sm text-gray-600">
                <strong>Tip:</strong> Drag nodes from the palette, connect by clicking handles
              </p>
            </Panel>
          </ReactFlow>
        </div>

        {/* Right Sidebar - Node Properties */}
        {selectedNode && (
          <div className="w-80 bg-white border-l border-gray-200 p-4 overflow-y-auto">
            <h3 className="text-lg font-semibold mb-4">Node Properties</h3>
            <div className="space-y-4">
              {/* Label - Common to all nodes */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Label
                </label>
                <input
                  type="text"
                  value={selectedNode.data.label}
                  onChange={(e) => {
                    setNodes((nds) =>
                      nds.map((n) =>
                        n.id === selectedNode.id
                          ? { ...n, data: { ...n.data, label: e.target.value } }
                          : n
                      )
                    )
                    setSelectedNode({
                      ...selectedNode,
                      data: { ...selectedNode.data, label: e.target.value },
                    })
                  }}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              {/* Node ID - For template references */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Node ID <span className="text-xs text-gray-500">(use in templates)</span>
                </label>
                <div className="flex items-center gap-2">
                  <code className="flex-1 px-3 py-2 bg-gray-100 rounded-lg text-gray-700 font-mono text-sm">
                    {selectedNode.id}
                  </code>
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(selectedNode.id)
                    }}
                    className="px-2 py-2 text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded"
                    title="Copy node ID"
                  >
                    📋
                  </button>
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Reference output: <code className="bg-gray-100 px-1 rounded">{`{{${selectedNode.id}.text}}`}</code>
                </p>
              </div>

              {/* Type - Common to all nodes */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Type
                </label>
                <div className="px-3 py-2 bg-gray-100 rounded-lg text-gray-700 capitalize">
                  {selectedNode.data.type}
                </div>
              </div>

              {/* Agent-specific: Model Selection Strategy */}
              {(selectedNode.data.type === 'supervisor' || selectedNode.data.type === 'worker') && (
                <div className="space-y-3">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Model Selection
                    </label>
                    <select
                      value={selectedNode.data.modelSelection || 'auto'}
                      onChange={(e) => {
                        const value = e.target.value
                        const newLlmModel = value.startsWith('llm:') ? value.replace('llm:', '') : null

                        // Update nodes state
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    modelSelection: value,
                                    llmModel: newLlmModel,
                                  },
                                }
                              : n
                          )
                        )

                        // Also update selectedNode state immediately for UI responsiveness
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            modelSelection: value,
                            llmModel: newLlmModel,
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    >
                      <optgroup label="Routing Strategy (Recommended)">
                        <option value="auto">🎯 Auto - Use Routing Strategy</option>
                        <option value="cost_optimized">💰 Cost Optimized</option>
                        <option value="latency_optimized">⚡ Latency Optimized</option>
                        <option value="quality_first">⭐ Quality First</option>
                      </optgroup>
                      <optgroup label="Specific Model Override">
                        <option value="llm:llama-3.3-70b-versatile">Llama 3.3 70B</option>
                        <option value="llm:llama-3.1-8b-instant">Llama 3.1 8B (Fast)</option>
                        <option value="llm:gpt-4o">GPT-4o</option>
                        <option value="llm:gpt-4o-mini">GPT-4o Mini</option>
                        <option value="llm:gpt-4-turbo">GPT-4 Turbo</option>
                        <option value="llm:gpt-3.5-turbo">GPT-3.5 Turbo</option>
                        <option value="llm:claude-3-5-sonnet-20241022">Claude 3.5 Sonnet</option>
                        <option value="llm:claude-3-opus-20240229">Claude 3 Opus</option>
                        <option value="llm:claude-3-haiku-20240307">Claude 3 Haiku</option>
                        <option value="llm:gemini-1.5-pro">Gemini 1.5 Pro</option>
                        <option value="llm:gemini-1.5-flash">Gemini 1.5 Flash</option>
                        <option value="llm:deepseek-chat">DeepSeek Chat</option>
                      </optgroup>
                    </select>
                  </div>

                  {/* Show info about selected strategy */}
                  {selectedNode.data.modelSelection === 'auto' && (
                    <div className="text-xs text-gray-600 bg-blue-50 border border-blue-200 rounded-lg p-2">
                      <p className="font-medium">Using routing strategy from:</p>
                      <ol className="list-decimal ml-4 mt-1 space-y-0.5">
                        <li>Workflow configuration (if set)</li>
                        <li>Organization defaults</li>
                      </ol>
                      <p className="mt-1 text-blue-700">Configure in LLM Settings → Strategy Configuration</p>
                    </div>
                  )}
                  {selectedNode.data.modelSelection === 'cost_optimized' && (
                    <div className="text-xs text-gray-600 bg-green-50 border border-green-200 rounded-lg p-2">
                      💰 Will select the cheapest model that's healthy (e.g., gpt-4o-mini, claude-haiku)
                    </div>
                  )}
                  {selectedNode.data.modelSelection === 'latency_optimized' && (
                    <div className="text-xs text-gray-600 bg-yellow-50 border border-yellow-200 rounded-lg p-2">
                      ⚡ Will select the fastest model based on measured latency
                    </div>
                  )}
                  {selectedNode.data.modelSelection === 'quality_first' && (
                    <div className="text-xs text-gray-600 bg-purple-50 border border-purple-200 rounded-lg p-2">
                      ⭐ Will select premium models (gpt-4, claude-opus) for best quality
                    </div>
                  )}
                  {selectedNode.data.modelSelection?.startsWith('llm:') && (
                    <div className="text-xs text-gray-600 bg-orange-50 border border-orange-200 rounded-lg p-2">
                      🔒 This agent will always use <strong>{selectedNode.data.llmModel}</strong>, bypassing routing
                    </div>
                  )}
                </div>
              )}

              {/* Agent-specific: Prompt */}
              {(selectedNode.data.type === 'supervisor' || selectedNode.data.type === 'worker') && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Prompt Configuration
                  </label>
                  <PromptSelector
                    promptSlug={selectedNode.data.promptSlug}
                    promptVersion={selectedNode.data.promptVersion}
                    manualPrompt={selectedNode.data.prompt}
                    promptVariables={selectedNode.data.promptVariables}
                    onPromptChange={(config) => {
                      setNodes((nds) =>
                        nds.map((n) =>
                          n.id === selectedNode.id
                            ? {
                                ...n,
                                data: {
                                  ...n.data,
                                  prompt: config.manualPrompt,
                                  promptSlug: config.promptSlug,
                                  promptVersion: config.promptVersion,
                                  promptVariables: config.promptVariables,
                                }
                              }
                            : n
                        )
                      )
                      setSelectedNode({
                        ...selectedNode,
                        data: {
                          ...selectedNode.data,
                          prompt: config.manualPrompt,
                          promptSlug: config.promptSlug,
                          promptVersion: config.promptVersion,
                          promptVariables: config.promptVariables,
                        },
                      })
                    }}
                    nodes={nodes}
                    edges={edges}
                    currentNodeId={selectedNode.id}
                  />
                </div>
              )}

              {/* Trigger-specific properties */}
              {selectedNode.data.type === 'trigger' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Trigger Type
                    </label>
                    <select
                      value={selectedNode.data.triggerConfig?.triggerType || 'manual'}
                      onChange={(e) => {
                        const newTriggerType = e.target.value as any
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    triggerConfig: {
                                      ...n.data.triggerConfig,
                                      triggerType: newTriggerType,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            triggerConfig: {
                              ...selectedNode.data.triggerConfig,
                              triggerType: newTriggerType,
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    >
                      <option value="manual">Manual</option>
                      <option value="webhook">Webhook</option>
                      <option value="cron">Schedule (Cron)</option>
                      <option value="event">Event</option>
                    </select>
                  </div>
                  {selectedNode.data.triggerConfig?.triggerType === 'cron' && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Cron Expression
                      </label>
                      <input
                        type="text"
                        value={selectedNode.data.triggerConfig?.cronExpression || ''}
                        placeholder="0 9 * * *"
                        onChange={(e) => {
                          const newCronExpression = e.target.value
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? {
                                    ...n,
                                    data: {
                                      ...n.data,
                                      triggerConfig: {
                                        ...n.data.triggerConfig,
                                        cronExpression: newCronExpression,
                                      },
                                    },
                                  }
                                : n
                            )
                          )
                          setSelectedNode({
                            ...selectedNode,
                            data: {
                              ...selectedNode.data,
                              triggerConfig: {
                                ...selectedNode.data.triggerConfig,
                                cronExpression: newCronExpression,
                              },
                            },
                          })
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                      />
                      <p className="text-xs text-gray-500 mt-1">e.g., "0 9 * * *" for daily at 9 AM</p>
                    </div>
                  )}
                </>
              )}

              {/* Condition-specific properties */}
              {selectedNode.data.type === 'condition' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Condition Expression
                    </label>
                    <textarea
                      value={selectedNode.data.conditionConfig?.expression || ''}
                      placeholder="e.g., result.status === 'success'"
                      onChange={(e) => {
                        const newExpression = e.target.value
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    conditionConfig: {
                                      ...n.data.conditionConfig,
                                      expression: newExpression,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            conditionConfig: {
                              ...selectedNode.data.conditionConfig,
                              expression: newExpression,
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                      rows={3}
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        True Label
                      </label>
                      <input
                        type="text"
                        value={selectedNode.data.conditionConfig?.trueLabel || 'Yes'}
                        onChange={(e) => {
                          const newTrueLabel = e.target.value
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? {
                                    ...n,
                                    data: {
                                      ...n.data,
                                      conditionConfig: {
                                        ...n.data.conditionConfig,
                                        trueLabel: newTrueLabel,
                                      },
                                    },
                                  }
                                : n
                            )
                          )
                          setSelectedNode({
                            ...selectedNode,
                            data: {
                              ...selectedNode.data,
                              conditionConfig: {
                                ...selectedNode.data.conditionConfig,
                                trueLabel: newTrueLabel,
                              },
                            },
                          })
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        False Label
                      </label>
                      <input
                        type="text"
                        value={selectedNode.data.conditionConfig?.falseLabel || 'No'}
                        onChange={(e) => {
                          const newFalseLabel = e.target.value
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? {
                                    ...n,
                                    data: {
                                      ...n.data,
                                      conditionConfig: {
                                        ...n.data.conditionConfig,
                                        falseLabel: newFalseLabel,
                                      },
                                    },
                                  }
                                : n
                            )
                          )
                          setSelectedNode({
                            ...selectedNode,
                            data: {
                              ...selectedNode.data,
                              conditionConfig: {
                                ...selectedNode.data.conditionConfig,
                                falseLabel: newFalseLabel,
                              },
                            },
                          })
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                      />
                    </div>
                  </div>
                </>
              )}

              {/* Tool/API-specific properties */}
              {selectedNode.data.type === 'tool' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      API Endpoint URL
                    </label>
                    <input
                      type="url"
                      value={selectedNode.data.toolConfig?.url || ''}
                      placeholder="https://api.example.com/endpoint"
                      onChange={(e) => {
                        const newUrl = e.target.value
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    toolConfig: {
                                      ...n.data.toolConfig,
                                      url: newUrl,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            toolConfig: {
                              ...selectedNode.data.toolConfig,
                              url: newUrl,
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        HTTP Method
                      </label>
                      <select
                        value={selectedNode.data.toolConfig?.method || 'GET'}
                        onChange={(e) => {
                          const newMethod = e.target.value as any
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? {
                                    ...n,
                                    data: {
                                      ...n.data,
                                      toolConfig: {
                                        ...n.data.toolConfig,
                                        method: newMethod,
                                      },
                                    },
                                  }
                                : n
                            )
                          )
                          setSelectedNode({
                            ...selectedNode,
                            data: {
                              ...selectedNode.data,
                              toolConfig: {
                                ...selectedNode.data.toolConfig,
                                method: newMethod,
                              },
                            },
                          })
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                      >
                        <option value="GET">GET</option>
                        <option value="POST">POST</option>
                        <option value="PUT">PUT</option>
                        <option value="DELETE">DELETE</option>
                        <option value="PATCH">PATCH</option>
                      </select>
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Timeout (ms)
                      </label>
                      <input
                        type="number"
                        value={selectedNode.data.toolConfig?.timeout || 30000}
                        onChange={(e) => {
                          const newTimeout = parseInt(e.target.value)
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? {
                                    ...n,
                                    data: {
                                      ...n.data,
                                      toolConfig: {
                                        ...n.data.toolConfig,
                                        timeout: newTimeout,
                                      },
                                    },
                                  }
                                : n
                            )
                          )
                          setSelectedNode({
                            ...selectedNode,
                            data: {
                              ...selectedNode.data,
                              toolConfig: {
                                ...selectedNode.data.toolConfig,
                                timeout: newTimeout,
                              },
                            },
                          })
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Request Body (JSON)
                    </label>
                    <textarea
                      value={selectedNode.data.toolConfig?.body || ''}
                      placeholder={'{\n  "key": "value",\n  "data": "{{previous_node.output}}"\n}'}
                      onChange={(e) => {
                        const newBody = e.target.value
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    toolConfig: {
                                      ...n.data.toolConfig,
                                      body: newBody,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            toolConfig: {
                              ...selectedNode.data.toolConfig,
                              body: newBody,
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                      rows={4}
                    />
                    <p className="text-xs text-gray-500 mt-1">Use {`{{node_id.field}}`} for dynamic values</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Authentication
                    </label>
                    <select
                      value={selectedNode.data.toolConfig?.auth?.type || 'none'}
                      onChange={(e) => {
                        const newAuthType = e.target.value as any
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    toolConfig: {
                                      ...n.data.toolConfig,
                                      auth: {
                                        ...n.data.toolConfig?.auth,
                                        type: newAuthType,
                                      },
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            toolConfig: {
                              ...selectedNode.data.toolConfig,
                              auth: {
                                ...selectedNode.data.toolConfig?.auth,
                                type: newAuthType,
                              },
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                    >
                      <option value="none">None</option>
                      <option value="api_key">API Key</option>
                      <option value="bearer">Bearer Token</option>
                      <option value="basic">Basic Auth</option>
                    </select>
                  </div>

                  {/* Auth fields based on type */}
                  {selectedNode.data.toolConfig?.auth?.type === 'api_key' && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Header Name
                        </label>
                        <input
                          type="text"
                          value={selectedNode.data.toolConfig?.auth?.headerName || 'X-API-Key'}
                          placeholder="X-API-Key"
                          onChange={(e) => {
                            const newHeaderName = e.target.value
                            setNodes((nds) =>
                              nds.map((n) =>
                                n.id === selectedNode.id
                                  ? {
                                      ...n,
                                      data: {
                                        ...n.data,
                                        toolConfig: {
                                          ...n.data.toolConfig,
                                          auth: {
                                            ...n.data.toolConfig?.auth,
                                            headerName: newHeaderName,
                                          },
                                        },
                                      },
                                    }
                                  : n
                              )
                            )
                            setSelectedNode({
                              ...selectedNode,
                              data: {
                                ...selectedNode.data,
                                toolConfig: {
                                  ...selectedNode.data.toolConfig,
                                  auth: {
                                    ...selectedNode.data.toolConfig?.auth,
                                    headerName: newHeaderName,
                                  },
                                },
                              },
                            })
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          API Key
                        </label>
                        <input
                          type="password"
                          value={selectedNode.data.toolConfig?.auth?.apiKey || ''}
                          placeholder="sk-..."
                          onChange={(e) => {
                            const newApiKey = e.target.value
                            setNodes((nds) =>
                              nds.map((n) =>
                                n.id === selectedNode.id
                                  ? {
                                      ...n,
                                      data: {
                                        ...n.data,
                                        toolConfig: {
                                          ...n.data.toolConfig,
                                          auth: {
                                            ...n.data.toolConfig?.auth,
                                            apiKey: newApiKey,
                                          },
                                        },
                                      },
                                    }
                                  : n
                              )
                            )
                            setSelectedNode({
                              ...selectedNode,
                              data: {
                                ...selectedNode.data,
                                toolConfig: {
                                  ...selectedNode.data.toolConfig,
                                  auth: {
                                    ...selectedNode.data.toolConfig?.auth,
                                    apiKey: newApiKey,
                                  },
                                },
                              },
                            })
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm font-mono"
                        />
                      </div>
                    </div>
                  )}

                  {selectedNode.data.toolConfig?.auth?.type === 'bearer' && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Bearer Token
                      </label>
                      <input
                        type="password"
                        value={selectedNode.data.toolConfig?.auth?.bearerToken || ''}
                        placeholder="eyJ..."
                        onChange={(e) => {
                          const newToken = e.target.value
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? {
                                    ...n,
                                    data: {
                                      ...n.data,
                                      toolConfig: {
                                        ...n.data.toolConfig,
                                        auth: {
                                          ...n.data.toolConfig?.auth,
                                          bearerToken: newToken,
                                        },
                                      },
                                    },
                                  }
                                : n
                            )
                          )
                          setSelectedNode({
                            ...selectedNode,
                            data: {
                              ...selectedNode.data,
                              toolConfig: {
                                ...selectedNode.data.toolConfig,
                                auth: {
                                  ...selectedNode.data.toolConfig?.auth,
                                  bearerToken: newToken,
                                },
                              },
                            },
                          })
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm font-mono"
                      />
                    </div>
                  )}

                  {selectedNode.data.toolConfig?.auth?.type === 'basic' && (
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Username
                        </label>
                        <input
                          type="text"
                          value={selectedNode.data.toolConfig?.auth?.username || ''}
                          onChange={(e) => {
                            const newUsername = e.target.value
                            setNodes((nds) =>
                              nds.map((n) =>
                                n.id === selectedNode.id
                                  ? {
                                      ...n,
                                      data: {
                                        ...n.data,
                                        toolConfig: {
                                          ...n.data.toolConfig,
                                          auth: {
                                            ...n.data.toolConfig?.auth,
                                            username: newUsername,
                                          },
                                        },
                                      },
                                    }
                                  : n
                              )
                            )
                            setSelectedNode({
                              ...selectedNode,
                              data: {
                                ...selectedNode.data,
                                toolConfig: {
                                  ...selectedNode.data.toolConfig,
                                  auth: {
                                    ...selectedNode.data.toolConfig?.auth,
                                    username: newUsername,
                                  },
                                },
                              },
                            })
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Password
                        </label>
                        <input
                          type="password"
                          value={selectedNode.data.toolConfig?.auth?.password || ''}
                          onChange={(e) => {
                            const newPassword = e.target.value
                            setNodes((nds) =>
                              nds.map((n) =>
                                n.id === selectedNode.id
                                  ? {
                                      ...n,
                                      data: {
                                        ...n.data,
                                        toolConfig: {
                                          ...n.data.toolConfig,
                                          auth: {
                                            ...n.data.toolConfig?.auth,
                                            password: newPassword,
                                          },
                                        },
                                      },
                                    }
                                  : n
                              )
                            )
                            setSelectedNode({
                              ...selectedNode,
                              data: {
                                ...selectedNode.data,
                                toolConfig: {
                                  ...selectedNode.data.toolConfig,
                                  auth: {
                                    ...selectedNode.data.toolConfig?.auth,
                                    password: newPassword,
                                  },
                                },
                              },
                            })
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 text-sm"
                        />
                      </div>
                    </div>
                  )}
                </>
              )}

              {/* Memory Node Properties */}
              {selectedNode.data.type === 'memory' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Operation
                    </label>
                    <select
                      value={selectedNode.data.memoryConfig?.operation || 'query'}
                      onChange={(e) => {
                        const newOperation = e.target.value as any
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    memoryConfig: {
                                      ...n.data.memoryConfig,
                                      operation: newOperation,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            memoryConfig: {
                              ...selectedNode.data.memoryConfig,
                              operation: newOperation,
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 text-sm"
                    >
                      <option value="store">Store - Save to memory</option>
                      <option value="query">Query - Search memory</option>
                      <option value="delete">Delete - Remove from memory</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Provider ID
                    </label>
                    <input
                      type="text"
                      value={selectedNode.data.memoryConfig?.providerId || ''}
                      placeholder="pinecone-main, qdrant-prod, etc."
                      onChange={(e) => {
                        const newProviderId = e.target.value
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    memoryConfig: {
                                      ...n.data.memoryConfig,
                                      providerId: newProviderId,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            memoryConfig: {
                              ...selectedNode.data.memoryConfig,
                              providerId: newProviderId,
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 text-sm font-mono"
                    />
                    <p className="text-xs text-gray-500 mt-1">Reference to configured vector database</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Namespace
                    </label>
                    <input
                      type="text"
                      value={selectedNode.data.memoryConfig?.namespace || ''}
                      placeholder="user-123, session-abc, etc."
                      onChange={(e) => {
                        const newNamespace = e.target.value
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    memoryConfig: {
                                      ...n.data.memoryConfig,
                                      namespace: newNamespace,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            memoryConfig: {
                              ...selectedNode.data.memoryConfig,
                              namespace: newNamespace,
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 text-sm font-mono"
                    />
                    <p className="text-xs text-gray-500 mt-1">Logical partition within the database</p>
                  </div>

                  {(selectedNode.data.memoryConfig?.operation === 'query' || !selectedNode.data.memoryConfig?.operation) && (
                    <>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Search Query
                        </label>
                        <textarea
                          value={selectedNode.data.memoryConfig?.query || ''}
                          placeholder="What information are you looking for?"
                          onChange={(e) => {
                            const newQuery = e.target.value
                            setNodes((nds) =>
                              nds.map((n) =>
                                n.id === selectedNode.id
                                  ? {
                                      ...n,
                                      data: {
                                        ...n.data,
                                        memoryConfig: {
                                          ...n.data.memoryConfig,
                                          query: newQuery,
                                        },
                                      },
                                    }
                                  : n
                              )
                            )
                            setSelectedNode({
                              ...selectedNode,
                              data: {
                                ...selectedNode.data,
                                memoryConfig: {
                                  ...selectedNode.data.memoryConfig,
                                  query: newQuery,
                                },
                              },
                            })
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 text-sm"
                          rows={3}
                        />
                        <p className="text-xs text-gray-500 mt-1">Use {`{{node_id.field}}`} for dynamic values</p>
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Result Limit
                        </label>
                        <input
                          type="number"
                          value={selectedNode.data.memoryConfig?.limit || 5}
                          min={1}
                          max={100}
                          onChange={(e) => {
                            const newLimit = parseInt(e.target.value)
                            setNodes((nds) =>
                              nds.map((n) =>
                                n.id === selectedNode.id
                                  ? {
                                      ...n,
                                      data: {
                                        ...n.data,
                                        memoryConfig: {
                                          ...n.data.memoryConfig,
                                          limit: newLimit,
                                        },
                                      },
                                    }
                                  : n
                              )
                            )
                            setSelectedNode({
                              ...selectedNode,
                              data: {
                                ...selectedNode.data,
                                memoryConfig: {
                                  ...selectedNode.data.memoryConfig,
                                  limit: newLimit,
                                },
                              },
                            })
                          }}
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 text-sm"
                        />
                      </div>
                    </>
                  )}

                  {selectedNode.data.memoryConfig?.operation === 'store' && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Content to Store
                      </label>
                      <textarea
                        value={selectedNode.data.memoryConfig?.content || ''}
                        placeholder="The information to store in memory"
                        onChange={(e) => {
                          const newContent = e.target.value
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? {
                                    ...n,
                                    data: {
                                      ...n.data,
                                      memoryConfig: {
                                        ...n.data.memoryConfig,
                                        content: newContent,
                                      },
                                    },
                                  }
                                : n
                            )
                          )
                          setSelectedNode({
                            ...selectedNode,
                            data: {
                              ...selectedNode.data,
                              memoryConfig: {
                                ...selectedNode.data.memoryConfig,
                                content: newContent,
                              },
                            },
                          })
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 text-sm"
                        rows={4}
                      />
                      <p className="text-xs text-gray-500 mt-1">Use {`{{node_id.field}}`} for dynamic values</p>
                    </div>
                  )}
                </>
              )}

              {/* Knowledge Node Properties */}
              {selectedNode.data.type === 'knowledge' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Connector ID
                    </label>
                    <input
                      type="text"
                      value={selectedNode.data.knowledgeConfig?.connectorId || ''}
                      placeholder="docs-connector, wiki-connector, etc."
                      onChange={(e) => {
                        const newConnectorId = e.target.value
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    knowledgeConfig: {
                                      ...n.data.knowledgeConfig,
                                      connectorId: newConnectorId,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            knowledgeConfig: {
                              ...selectedNode.data.knowledgeConfig,
                              connectorId: newConnectorId,
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 text-sm font-mono"
                    />
                    <p className="text-xs text-gray-500 mt-1">Reference to configured RAG connector</p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Search Query
                    </label>
                    <textarea
                      value={selectedNode.data.knowledgeConfig?.query || ''}
                      placeholder="What information to retrieve from the knowledge base?"
                      onChange={(e) => {
                        const newQuery = e.target.value
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    knowledgeConfig: {
                                      ...n.data.knowledgeConfig,
                                      query: newQuery,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            knowledgeConfig: {
                              ...selectedNode.data.knowledgeConfig,
                              query: newQuery,
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 text-sm"
                      rows={3}
                    />
                    <p className="text-xs text-gray-500 mt-1">Use {`{{node_id.field}}`} for dynamic values</p>
                  </div>

                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Result Limit
                      </label>
                      <input
                        type="number"
                        value={selectedNode.data.knowledgeConfig?.limit || 5}
                        min={1}
                        max={50}
                        onChange={(e) => {
                          const newLimit = parseInt(e.target.value)
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? {
                                    ...n,
                                    data: {
                                      ...n.data,
                                      knowledgeConfig: {
                                        ...n.data.knowledgeConfig,
                                        limit: newLimit,
                                      },
                                    },
                                  }
                                : n
                            )
                          )
                          setSelectedNode({
                            ...selectedNode,
                            data: {
                              ...selectedNode.data,
                              knowledgeConfig: {
                                ...selectedNode.data.knowledgeConfig,
                                limit: newLimit,
                              },
                            },
                          })
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 text-sm"
                      />
                    </div>

                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Min Score
                      </label>
                      <input
                        type="number"
                        value={selectedNode.data.knowledgeConfig?.minScore || 0.7}
                        min={0}
                        max={1}
                        step={0.1}
                        onChange={(e) => {
                          const newMinScore = parseFloat(e.target.value)
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? {
                                    ...n,
                                    data: {
                                      ...n.data,
                                      knowledgeConfig: {
                                        ...n.data.knowledgeConfig,
                                        minScore: newMinScore,
                                      },
                                    },
                                  }
                                : n
                            )
                          )
                          setSelectedNode({
                            ...selectedNode,
                            data: {
                              ...selectedNode.data,
                              knowledgeConfig: {
                                ...selectedNode.data.knowledgeConfig,
                                minScore: newMinScore,
                              },
                            },
                          })
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 text-sm"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={selectedNode.data.knowledgeConfig?.rerank || false}
                        onChange={(e) => {
                          const newRerank = e.target.checked
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? {
                                    ...n,
                                    data: {
                                      ...n.data,
                                      knowledgeConfig: {
                                        ...n.data.knowledgeConfig,
                                        rerank: newRerank,
                                      },
                                    },
                                  }
                                : n
                            )
                          )
                          setSelectedNode({
                            ...selectedNode,
                            data: {
                              ...selectedNode.data,
                              knowledgeConfig: {
                                ...selectedNode.data.knowledgeConfig,
                                rerank: newRerank,
                              },
                            },
                          })
                        }}
                        className="rounded border-gray-300 text-teal-600 focus:ring-teal-500"
                      />
                      <span className="text-sm font-medium text-gray-700">
                        Enable Re-ranking
                      </span>
                    </label>
                    <p className="text-xs text-gray-500 mt-1 ml-6">
                      Re-rank results using a cross-encoder model for better relevance
                    </p>
                  </div>
                </>
              )}

              {/* Integration-specific properties */}
              {selectedNode.data.type === 'integration' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Service
                    </label>
                    <select
                      value={selectedNode.data.integrationConfig?.integrationType || 'custom'}
                      onChange={(e) => {
                        const newType = e.target.value as IntegrationType
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    integrationConfig: {
                                      ...n.data.integrationConfig,
                                      integrationType: newType,
                                      action: '',
                                      parameters: {},
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        // Also update selectedNode to trigger actions fetch
                        setSelectedNode(prev => prev ? {
                          ...prev,
                          data: {
                            ...prev.data,
                            integrationConfig: {
                              ...prev.data.integrationConfig,
                              integrationType: newType,
                              action: '',
                              parameters: {},
                            },
                          },
                        } : null)
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                    >
                      {integrationPaletteItems.map((item) => (
                        <option key={item.integrationType} value={item.integrationType}>
                          {item.label}{item.connected ? ' (connected)' : ''}
                        </option>
                      ))}
                      <option value="custom">Custom API</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Action
                    </label>
                    {loadingActions ? (
                      <div className="w-full px-3 py-2 border border-gray-300 rounded-lg bg-gray-50 text-gray-500">
                        Loading actions...
                      </div>
                    ) : availableActions.length > 0 ? (
                      <select
                        value={selectedNode.data.integrationConfig?.action || ''}
                        onChange={(e) => {
                          const newAction = e.target.value
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? {
                                    ...n,
                                    data: {
                                      ...n.data,
                                      integrationConfig: {
                                        ...n.data.integrationConfig,
                                        action: newAction,
                                      },
                                    },
                                  }
                                : n
                            )
                          )
                          setSelectedNode(prev => prev ? {
                            ...prev,
                            data: {
                              ...prev.data,
                              integrationConfig: {
                                ...prev.data.integrationConfig,
                                action: newAction,
                              },
                            },
                          } : null)
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      >
                        <option value="">Select an action...</option>
                        {availableActions.map((action) => (
                          <option key={action.name} value={action.name}>
                            {action.name} {action.description ? `- ${action.description}` : ''}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <input
                        type="text"
                        value={selectedNode.data.integrationConfig?.action || ''}
                        placeholder="e.g., send_message"
                        onChange={(e) => {
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? {
                                    ...n,
                                    data: {
                                      ...n.data,
                                      integrationConfig: {
                                        ...n.data.integrationConfig,
                                        action: e.target.value,
                                      },
                                    },
                                  }
                                : n
                            )
                          )
                        }}
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
                      />
                    )}
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Parameters (JSON)
                    </label>
                    <VariablePicker
                      value={paramJsonText}
                      onChange={(text) => {
                        setParamJsonText(text)
                        try {
                          const params = JSON.parse(text)
                          setParamJsonError(null)
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? {
                                    ...n,
                                    data: {
                                      ...n.data,
                                      integrationConfig: {
                                        ...n.data.integrationConfig,
                                        parameters: params,
                                      },
                                    },
                                  }
                                : n
                            )
                          )
                          setSelectedNode(prev => prev ? {
                            ...prev,
                            data: {
                              ...prev.data,
                              integrationConfig: {
                                ...prev.data.integrationConfig,
                                parameters: params,
                              },
                            },
                          } : null)
                        } catch {
                          setParamJsonError('Invalid JSON')
                        }
                      }}
                      nodes={nodes}
                      edges={edges}
                      currentNodeId={selectedNode.id}
                      placeholder='{"channel_id": "123", "content": "Hello {{input.name}}!"}'
                      rows={6}
                      className={paramJsonError ? 'border-red-500' : ''}
                    />
                    {paramJsonError && (
                      <p className="text-red-500 text-xs mt-1">{paramJsonError}</p>
                    )}
                    <p className="text-gray-500 text-xs mt-1">
                      For Discord: {`{"channel_id": "YOUR_ID", "content": "{{input.message}}"}`}
                    </p>
                  </div>

                  {/* Test Execute Button */}
                  <div className="pt-2">
                    <button
                      onClick={handleTestExecute}
                      disabled={testExecuting || !selectedNode.data.integrationConfig?.action}
                      className={`w-full px-4 py-2 rounded-lg flex items-center justify-center gap-2 ${
                        testExecuting
                          ? 'bg-gray-400 cursor-not-allowed'
                          : 'bg-green-600 hover:bg-green-700 text-white'
                      }`}
                    >
                      {testExecuting ? (
                        <>
                          <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                          Executing...
                        </>
                      ) : (
                        <>
                          <Play className="w-4 h-4" />
                          Test Execute
                        </>
                      )}
                    </button>
                  </div>

                  {/* Test Result Display */}
                  {testResult && (
                    <div className={`p-3 rounded-lg border ${
                      testResult.success
                        ? 'bg-green-50 border-green-200'
                        : 'bg-red-50 border-red-200'
                    }`}>
                      <div className="flex items-center justify-between mb-2">
                        <span className={`font-medium text-sm ${
                          testResult.success ? 'text-green-700' : 'text-red-700'
                        }`}>
                          {testResult.success ? '✓ Success' : '✗ Failed'}
                        </span>
                        {testResult.duration_ms && (
                          <span className="text-xs text-gray-500">
                            {testResult.duration_ms}ms
                          </span>
                        )}
                      </div>
                      {testResult.error && (
                        <p className="text-red-600 text-xs mb-2">{testResult.error}</p>
                      )}
                      {testResult.data && (
                        <div className="mt-2">
                          <p className="text-xs font-medium text-gray-700 mb-1">Response:</p>
                          <pre className="text-xs bg-white p-2 rounded border overflow-auto max-h-40">
                            {JSON.stringify(testResult.data, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </>
              )}

              {/* Webhook Node Properties */}
              {selectedNode.data.type === 'webhook' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      HTTP Method
                    </label>
                    <select
                      value={selectedNode.data.webhookConfig?.method || 'POST'}
                      onChange={(e) => {
                        const newMethod = e.target.value as 'POST' | 'GET'
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    webhookConfig: {
                                      ...n.data.webhookConfig,
                                      method: newMethod,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            webhookConfig: {
                              ...selectedNode.data.webhookConfig,
                              method: newMethod,
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 text-sm"
                    >
                      <option value="POST">POST</option>
                      <option value="GET">GET</option>
                      <option value="PUT">PUT</option>
                      <option value="PATCH">PATCH</option>
                      <option value="DELETE">DELETE</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Authentication Type
                    </label>
                    <select
                      value={selectedNode.data.webhookConfig?.authentication?.type || 'none'}
                      onChange={(e) => {
                        const newAuthType = e.target.value as WebhookAuthType
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    webhookConfig: {
                                      ...n.data.webhookConfig,
                                      authentication: {
                                        ...n.data.webhookConfig?.authentication,
                                        type: newAuthType,
                                      },
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            webhookConfig: {
                              ...selectedNode.data.webhookConfig,
                              authentication: {
                                ...selectedNode.data.webhookConfig?.authentication,
                                type: newAuthType,
                              },
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 text-sm"
                    >
                      <option value="none">None</option>
                      <option value="basic">Basic Auth</option>
                      <option value="bearer">Bearer Token</option>
                      <option value="api-key">API Key</option>
                    </select>
                  </div>

                  {selectedNode.data.webhookConfig?.authentication?.type === 'bearer' && (
                    <div>
                      <label className="block text-sm font-medium text-gray-700 mb-1">
                        Bearer Token
                      </label>
                      <input
                        type="password"
                        value={selectedNode.data.webhookConfig?.authentication?.token || ''}
                        onChange={(e) => {
                          const newToken = e.target.value
                          setNodes((nds) =>
                            nds.map((n) =>
                              n.id === selectedNode.id
                                ? {
                                    ...n,
                                    data: {
                                      ...n.data,
                                      webhookConfig: {
                                        ...n.data.webhookConfig,
                                        authentication: {
                                          ...n.data.webhookConfig?.authentication,
                                          token: newToken,
                                        },
                                      },
                                    },
                                  }
                                : n
                            )
                          )
                          setSelectedNode({
                            ...selectedNode,
                            data: {
                              ...selectedNode.data,
                              webhookConfig: {
                                ...selectedNode.data.webhookConfig,
                                authentication: {
                                  ...selectedNode.data.webhookConfig?.authentication,
                                  token: newToken,
                                },
                              },
                            },
                          })
                        }}
                        placeholder="Enter bearer token"
                        className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 text-sm"
                      />
                    </div>
                  )}

                  {selectedNode.data.webhookConfig?.authentication?.type === 'api-key' && (
                    <>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          API Key Name
                        </label>
                        <input
                          type="text"
                          value={selectedNode.data.webhookConfig?.authentication?.keyName || ''}
                          onChange={(e) => {
                            const newKeyName = e.target.value
                            setNodes((nds) =>
                              nds.map((n) =>
                                n.id === selectedNode.id
                                  ? {
                                      ...n,
                                      data: {
                                        ...n.data,
                                        webhookConfig: {
                                          ...n.data.webhookConfig,
                                          authentication: {
                                            ...n.data.webhookConfig?.authentication,
                                            keyName: newKeyName,
                                          },
                                        },
                                      },
                                    }
                                  : n
                              )
                            )
                            setSelectedNode({
                              ...selectedNode,
                              data: {
                                ...selectedNode.data,
                                webhookConfig: {
                                  ...selectedNode.data.webhookConfig,
                                  authentication: {
                                    ...selectedNode.data.webhookConfig?.authentication,
                                    keyName: newKeyName,
                                  },
                                },
                              },
                            })
                          }}
                          placeholder="e.g., X-API-Key"
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          API Key Value
                        </label>
                        <input
                          type="password"
                          value={selectedNode.data.webhookConfig?.authentication?.keyValue || ''}
                          onChange={(e) => {
                            const newKeyValue = e.target.value
                            setNodes((nds) =>
                              nds.map((n) =>
                                n.id === selectedNode.id
                                  ? {
                                      ...n,
                                      data: {
                                        ...n.data,
                                        webhookConfig: {
                                          ...n.data.webhookConfig,
                                          authentication: {
                                            ...n.data.webhookConfig?.authentication,
                                            keyValue: newKeyValue,
                                          },
                                        },
                                      },
                                    }
                                  : n
                              )
                            )
                            setSelectedNode({
                              ...selectedNode,
                              data: {
                                ...selectedNode.data,
                                webhookConfig: {
                                  ...selectedNode.data.webhookConfig,
                                  authentication: {
                                    ...selectedNode.data.webhookConfig?.authentication,
                                    keyValue: newKeyValue,
                                  },
                                },
                              },
                            })
                          }}
                          placeholder="Enter API key"
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 text-sm"
                        />
                      </div>
                    </>
                  )}

                  {selectedNode.data.webhookConfig?.authentication?.type === 'basic' && (
                    <>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Username
                        </label>
                        <input
                          type="text"
                          value={selectedNode.data.webhookConfig?.authentication?.username || ''}
                          onChange={(e) => {
                            const newUsername = e.target.value
                            setNodes((nds) =>
                              nds.map((n) =>
                                n.id === selectedNode.id
                                  ? {
                                      ...n,
                                      data: {
                                        ...n.data,
                                        webhookConfig: {
                                          ...n.data.webhookConfig,
                                          authentication: {
                                            ...n.data.webhookConfig?.authentication,
                                            username: newUsername,
                                          },
                                        },
                                      },
                                    }
                                  : n
                              )
                            )
                            setSelectedNode({
                              ...selectedNode,
                              data: {
                                ...selectedNode.data,
                                webhookConfig: {
                                  ...selectedNode.data.webhookConfig,
                                  authentication: {
                                    ...selectedNode.data.webhookConfig?.authentication,
                                    username: newUsername,
                                  },
                                },
                              },
                            })
                          }}
                          placeholder="Enter username"
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-1">
                          Password
                        </label>
                        <input
                          type="password"
                          value={selectedNode.data.webhookConfig?.authentication?.password || ''}
                          onChange={(e) => {
                            const newPassword = e.target.value
                            setNodes((nds) =>
                              nds.map((n) =>
                                n.id === selectedNode.id
                                  ? {
                                      ...n,
                                      data: {
                                        ...n.data,
                                        webhookConfig: {
                                          ...n.data.webhookConfig,
                                          authentication: {
                                            ...n.data.webhookConfig?.authentication,
                                            password: newPassword,
                                          },
                                        },
                                      },
                                    }
                                  : n
                              )
                            )
                            setSelectedNode({
                              ...selectedNode,
                              data: {
                                ...selectedNode.data,
                                webhookConfig: {
                                  ...selectedNode.data.webhookConfig,
                                  authentication: {
                                    ...selectedNode.data.webhookConfig?.authentication,
                                    password: newPassword,
                                  },
                                },
                              },
                            })
                          }}
                          placeholder="Enter password"
                          className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 text-sm"
                        />
                      </div>
                    </>
                  )}

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Response Status Code
                    </label>
                    <input
                      type="number"
                      value={selectedNode.data.webhookConfig?.responseStatus || 200}
                      onChange={(e) => {
                        const newStatus = parseInt(e.target.value)
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    webhookConfig: {
                                      ...n.data.webhookConfig,
                                      responseStatus: newStatus,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            webhookConfig: {
                              ...selectedNode.data.webhookConfig,
                              responseStatus: newStatus,
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 text-sm"
                      min="100"
                      max="599"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      HTTP status code to return when webhook is triggered
                    </p>
                  </div>
                </>
              )}

              {/* HITL Node Properties */}
              {selectedNode.data.type === 'hitl' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Approval Type
                    </label>
                    <select
                      value={selectedNode.data.hitlConfig?.approvalType || 'any'}
                      onChange={(e) => {
                        const newType = e.target.value as 'any' | 'all' | 'majority'
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    hitlConfig: {
                                      ...n.data.hitlConfig,
                                      approvalType: newType,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            hitlConfig: {
                              ...selectedNode.data.hitlConfig,
                              approvalType: newType,
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 text-sm"
                    >
                      <option value="any">Any Approver</option>
                      <option value="all">All Approvers</option>
                    </select>
                    <p className="text-xs text-gray-500 mt-1">
                      {selectedNode.data.hitlConfig?.approvalType === 'any'
                        ? 'Workflow continues when any approver accepts'
                        : 'Workflow continues only when all approvers accept'}
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Timeout (minutes)
                    </label>
                    <input
                      type="number"
                      value={selectedNode.data.hitlConfig?.timeout || 60}
                      onChange={(e) => {
                        const newTimeout = parseInt(e.target.value)
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    hitlConfig: {
                                      ...n.data.hitlConfig,
                                      timeout: newTimeout,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            hitlConfig: {
                              ...selectedNode.data.hitlConfig,
                              timeout: newTimeout,
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 text-sm"
                      min="1"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Timeout Action
                    </label>
                    <select
                      value={selectedNode.data.hitlConfig?.timeoutAction || 'reject'}
                      onChange={(e) => {
                        const newAction = e.target.value as 'reject' | 'approve' | 'retry'
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    hitlConfig: {
                                      ...n.data.hitlConfig,
                                      timeoutAction: newAction,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            hitlConfig: {
                              ...selectedNode.data.hitlConfig,
                              timeoutAction: newAction,
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 text-sm"
                    >
                      <option value="reject">Reject</option>
                      <option value="approve">Approve</option>
                    </select>
                    <p className="text-xs text-gray-500 mt-1">
                      Action to take if approval times out
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Notification Channels
                    </label>
                    <div className="space-y-2">
                      {(['email', 'slack', 'sms'] as const).map((channel) => (
                        <label key={channel} className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            checked={selectedNode.data.hitlConfig?.notifyVia?.includes(channel) || false}
                            onChange={(e) => {
                              const currentChannels = selectedNode.data.hitlConfig?.notifyVia || []
                              const newChannels = e.target.checked
                                ? [...currentChannels, channel]
                                : currentChannels.filter(c => c !== channel)

                              setNodes((nds) =>
                                nds.map((n) =>
                                  n.id === selectedNode.id
                                    ? {
                                        ...n,
                                        data: {
                                          ...n.data,
                                          hitlConfig: {
                                            ...n.data.hitlConfig,
                                            notifyVia: newChannels,
                                          },
                                        },
                                      }
                                    : n
                                )
                              )
                              setSelectedNode({
                                ...selectedNode,
                                data: {
                                  ...selectedNode.data,
                                  hitlConfig: {
                                    ...selectedNode.data.hitlConfig,
                                    notifyVia: newChannels,
                                  },
                                },
                              })
                            }}
                            className="rounded border-gray-300 text-amber-600 focus:ring-amber-500"
                          />
                          <span className="text-sm text-gray-700 capitalize">{channel}</span>
                        </label>
                      ))}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Approvers
                    </label>
                    <textarea
                      value={selectedNode.data.hitlConfig?.approvers?.join('\n') || ''}
                      onChange={(e) => {
                        const newApprovers = e.target.value.split('\n').filter(a => a.trim())
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    hitlConfig: {
                                      ...n.data.hitlConfig,
                                      approvers: newApprovers,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            hitlConfig: {
                              ...selectedNode.data.hitlConfig,
                              approvers: newApprovers,
                            },
                          },
                        })
                      }}
                      placeholder="Enter email addresses (one per line)"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-amber-500 text-sm"
                      rows={4}
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      List of email addresses for approvers
                    </p>
                  </div>
                </>
              )}

              {/* Print Node Properties */}
              {selectedNode.data.type === 'print' && (
                <>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Label
                    </label>
                    <input
                      type="text"
                      value={selectedNode.data.printConfig?.label || 'Output'}
                      onChange={(e) => {
                        const newLabel = e.target.value
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    printConfig: {
                                      ...n.data.printConfig,
                                      label: newLabel,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            printConfig: {
                              ...selectedNode.data.printConfig,
                              label: newLabel,
                            },
                          },
                        })
                      }}
                      placeholder="e.g., Debug Output, API Response"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 text-sm"
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Label shown in the Execution Log
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Message
                    </label>
                    <textarea
                      value={selectedNode.data.printConfig?.message || ''}
                      onChange={(e) => {
                        const newMessage = e.target.value
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    printConfig: {
                                      ...n.data.printConfig,
                                      message: newMessage,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            printConfig: {
                              ...selectedNode.data.printConfig,
                              message: newMessage,
                            },
                          },
                        })
                      }}
                      placeholder="Enter message to print. Use {{node_id.field}} for variables."
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 text-sm font-mono"
                      rows={4}
                    />
                    <p className="text-xs text-gray-500 mt-1">
                      Supports variable templates like {'{{input.name}}'} or {'{{worker.content}}'}
                    </p>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      Log Level
                    </label>
                    <select
                      value={selectedNode.data.printConfig?.logLevel || 'info'}
                      onChange={(e) => {
                        const newLevel = e.target.value as 'error' | 'warning' | 'info' | 'debug'
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    printConfig: {
                                      ...n.data.printConfig,
                                      logLevel: newLevel,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            printConfig: {
                              ...selectedNode.data.printConfig,
                              logLevel: newLevel,
                            },
                          },
                        })
                      }}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-teal-500 text-sm"
                    >
                      <option value="info">Info</option>
                      <option value="debug">Debug</option>
                      <option value="warning">Warning</option>
                      <option value="error">Error</option>
                    </select>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      checked={selectedNode.data.printConfig?.includeTimestamp !== false}
                      onChange={(e) => {
                        setNodes((nds) =>
                          nds.map((n) =>
                            n.id === selectedNode.id
                              ? {
                                  ...n,
                                  data: {
                                    ...n.data,
                                    printConfig: {
                                      ...n.data.printConfig,
                                      includeTimestamp: e.target.checked,
                                    },
                                  },
                                }
                              : n
                          )
                        )
                        setSelectedNode({
                          ...selectedNode,
                          data: {
                            ...selectedNode.data,
                            printConfig: {
                              ...selectedNode.data.printConfig,
                              includeTimestamp: e.target.checked,
                            },
                          },
                        })
                      }}
                      className="rounded border-gray-300 text-teal-600 focus:ring-teal-500"
                    />
                    <span className="text-sm text-gray-700">Include timestamp</span>
                  </div>
                </>
              )}

              {/* Capabilities - for agents */}
              {selectedNode.data.capabilities && selectedNode.data.capabilities.length > 0 && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Capabilities
                  </label>
                  <div className="flex flex-wrap gap-2">
                    {selectedNode.data.capabilities.map((cap, idx) => (
                      <span
                        key={idx}
                        className="px-2 py-1 bg-blue-100 text-blue-800 text-xs rounded"
                      >
                        {cap}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Status */}
              {selectedNode.data.status && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Status
                  </label>
                  <div className="flex items-center gap-2">
                    <div
                      className={`w-3 h-3 rounded-full ${
                        selectedNode.data.status === 'success'
                          ? 'bg-green-500'
                          : selectedNode.data.status === 'error'
                          ? 'bg-red-500'
                          : selectedNode.data.status === 'running'
                          ? 'bg-yellow-500'
                          : 'bg-gray-400'
                      }`}
                    />
                    <span className="capitalize">{selectedNode.data.status}</span>
                  </div>
                </div>
              )}

              {/* Cost */}
              {selectedNode.data.cost != null && typeof selectedNode.data.cost === 'number' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Cost
                  </label>
                  <div className="text-lg font-semibold text-gray-900">
                    ${selectedNode.data.cost.toFixed(4)}
                  </div>
                </div>
              )}

              {/* Delete Node Button */}
              <div className="pt-4 border-t border-gray-200">
                <button
                  onClick={() => {
                    setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id))
                    setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id))
                    setSelectedNode(null)
                    showToast('Node deleted', 'success')
                  }}
                  className="w-full px-4 py-2 bg-red-100 hover:bg-red-200 text-red-700 rounded-lg flex items-center justify-center gap-2"
                >
                  <XCircle className="w-4 h-4" />
                  Delete Node
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50">
          <div
            className={`px-6 py-4 rounded-lg shadow-lg flex items-center gap-3 transition-all ${
              toast.type === 'success'
                ? 'bg-green-600 text-white'
                : 'bg-red-600 text-white'
            }`}
          >
            {toast.type === 'success' ? (
              <CheckCircle className="w-5 h-5" />
            ) : (
              <XCircle className="w-5 h-5" />
            )}
            <span className="font-medium">{toast.message}</span>
          </div>
        </div>
      )}

      {/* Execution Log Panel - Always render if there are logs, just toggle visibility */}
      {executionLogs.length > 0 && (
        <div
          className={`execution-log-panel fixed bottom-0 right-0 bg-white border-t border-gray-200 shadow-lg z-50 transition-all duration-300 ${
            showLogs ? 'translate-y-0' : 'translate-y-full'
          }`}
          style={{ maxHeight: '40vh' }}
        >
          <div className="flex items-center justify-between px-6 py-3 border-b border-gray-200 bg-gray-50">
            <div className="flex items-center gap-3">
              <h3 className="text-lg font-semibold text-gray-900">Execution Log</h3>
              <span className="text-sm text-gray-500">({executionLogs.length} entries)</span>
              {isExecuting && (
                <span className="flex items-center gap-2 text-sm text-blue-600">
                  <span className="inline-block w-2 h-2 bg-blue-600 rounded-full animate-pulse"></span>
                  Executing...
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => setExecutionLogs([])}
                className="px-2 py-1 text-sm text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded"
                title="Clear logs"
              >
                Clear
              </button>
              <button
                onClick={() => setShowLogs(false)}
                className="text-gray-500 hover:text-gray-700 p-1 rounded hover:bg-gray-100"
                title="Hide logs"
              >
                <XCircle className="w-5 h-5" />
              </button>
            </div>
          </div>
          <div className="px-6 py-4 max-h-64 overflow-y-auto">
            <div className="space-y-2 font-mono text-sm">
              {executionLogs.map((log, index) => (
                <div
                  key={index}
                  className={`flex items-start gap-3 py-1 ${
                    log.type === 'error'
                      ? 'text-red-600'
                      : log.type === 'success'
                      ? 'text-green-600'
                      : 'text-gray-700'
                  }`}
                >
                  <span className="text-gray-400 shrink-0">{log.timestamp}</span>
                  <span className="break-words">{log.message}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Toggle button to show logs when hidden */}
      {executionLogs.length > 0 && !showLogs && (
        <button
          onClick={() => setShowLogs(true)}
          className="fixed bottom-4 right-4 px-4 py-2 bg-gray-800 text-white rounded-lg shadow-lg hover:bg-gray-700 z-50 flex items-center gap-2"
          title="Show execution logs"
        >
          <FileText className="w-4 h-4" />
          Logs ({executionLogs.length})
        </button>
      )}

      {/* Test Input Data Modal */}
      {showTestInputModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-lg shadow-2xl p-6 max-w-lg w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-bold text-gray-900">Execute Workflow</h3>
              <button
                onClick={() => setShowTestInputModal(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Test Input Data (JSON)
              </label>
              <p className="text-sm text-gray-500 mb-2">
                This data will be available in nodes as <code className="bg-gray-100 px-1 rounded">{'{{input.field}}'}</code> or via the trigger node.
              </p>
              <textarea
                value={testInputData}
                onChange={(e) => setTestInputData(e.target.value)}
                className="w-full h-48 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 font-mono text-sm"
                placeholder='{"ticket_id": "123", "title": "Example"}'
              />
              {(() => {
                try {
                  JSON.parse(testInputData)
                  return null
                } catch (e) {
                  return <p className="text-sm text-red-600 mt-1">Invalid JSON: {(e as Error).message}</p>
                }
              })()}
            </div>

            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowTestInputModal(false)}
                className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  try {
                    const parsedInput = JSON.parse(testInputData)
                    executeWorkflow(parsedInput)
                  } catch (e) {
                    showToast('Invalid JSON input data', 'error')
                  }
                }}
                className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 flex items-center gap-2"
              >
                <Play className="w-4 h-4" />
                Run Workflow
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Keyboard Shortcuts Help */}
      {showShortcuts && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-lg shadow-2xl p-6 max-w-md w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-xl font-bold text-gray-900">Keyboard Shortcuts</h3>
              <button
                onClick={() => setShowShortcuts(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XCircle className="w-6 h-6" />
              </button>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between py-2 border-b border-gray-200">
                <span className="text-gray-700">Save workflow</span>
                <kbd className="px-2 py-1 bg-gray-100 border border-gray-300 rounded text-sm font-mono">
                  Ctrl/⌘ + S
                </kbd>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-gray-200">
                <span className="text-gray-700">New workflow</span>
                <kbd className="px-2 py-1 bg-gray-100 border border-gray-300 rounded text-sm font-mono">
                  Ctrl/⌘ + N
                </kbd>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-gray-200">
                <span className="text-gray-700">Browse gallery</span>
                <kbd className="px-2 py-1 bg-gray-100 border border-gray-300 rounded text-sm font-mono">
                  Ctrl/⌘ + B
                </kbd>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-gray-200">
                <span className="text-gray-700">Delete selected node</span>
                <kbd className="px-2 py-1 bg-gray-100 border border-gray-300 rounded text-sm font-mono">
                  Delete / Backspace
                </kbd>
              </div>
              <div className="flex items-center justify-between py-2 border-b border-gray-200">
                <span className="text-gray-700">Deselect node</span>
                <kbd className="px-2 py-1 bg-gray-100 border border-gray-300 rounded text-sm font-mono">
                  Escape
                </kbd>
              </div>
              <div className="flex items-center justify-between py-2">
                <span className="text-gray-700">Show this help</span>
                <kbd className="px-2 py-1 bg-gray-100 border border-gray-300 rounded text-sm font-mono">
                  ?
                </kbd>
              </div>
            </div>
            <div className="mt-6 pt-4 border-t border-gray-200">
              <p className="text-xs text-gray-500 text-center">
                Press <kbd className="px-1 py-0.5 bg-gray-100 border border-gray-300 rounded text-xs">Escape</kbd> to close
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Cost Breakdown Modal */}
      {showCostBreakdown && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-lg shadow-2xl p-6 max-w-2xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-xl font-bold text-gray-900">Cost Breakdown</h3>
                <p className="text-sm text-gray-500 mt-1">Estimated execution costs by node</p>
              </div>
              <button
                onClick={() => setShowCostBreakdown(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XCircle className="w-6 h-6" />
              </button>
            </div>

            {/* Budget Settings */}
            <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <label className="text-sm font-medium text-blue-900">Budget Limit</label>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-blue-700">$</span>
                  <input
                    type="number"
                    value={budgetLimit}
                    onChange={(e) => setBudgetLimit(parseFloat(e.target.value) || 0)}
                    step="0.01"
                    min="0"
                    className="w-24 px-2 py-1 border border-blue-300 rounded text-sm text-right"
                  />
                </div>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-blue-700">Estimated Total:</span>
                <span className="font-bold text-blue-900">${calculateEstimatedCost().toFixed(4)}</span>
              </div>
              {calculateEstimatedCost() > budgetLimit && (
                <div className="mt-2 flex items-center gap-2 text-sm text-orange-700">
                  <AlertTriangle className="w-4 h-4" />
                  <span>Warning: Estimated cost exceeds budget</span>
                </div>
              )}
            </div>

            {/* Node Cost Breakdown */}
            <div className="space-y-3">
              <h4 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">Nodes</h4>
              {nodes.length === 0 ? (
                <p className="text-sm text-gray-500 italic">No nodes in workflow</p>
              ) : (
                nodes.map((node) => {
                  const nodeType = node.data.type
                  const modelCostEstimates: Record<string, Record<string, number>> = {
                    supervisor: {
                      'gpt-4': 0.05,
                      'gpt-3.5-turbo': 0.002,
                      'claude-3-5-sonnet-20241022': 0.03,
                      'claude-2': 0.03,
                    },
                    worker: {
                      'gpt-4': 0.03,
                      'gpt-3.5-turbo': 0.001,
                      'claude-3-5-sonnet-20241022': 0.02,
                      'claude-2': 0.02,
                    },
                  }
                  const toolCostEstimate = 0.0001

                  let estimatedCost = 0
                  if (nodeType === 'supervisor' || nodeType === 'worker') {
                    const model = node.data.llmModel || 'gpt-3.5-turbo'
                    estimatedCost = modelCostEstimates[nodeType][model] || 0.001
                  } else {
                    estimatedCost = toolCostEstimate
                  }

                  const actualCost = node.data.cost

                  return (
                    <div
                      key={node.id}
                      className="flex items-center justify-between p-3 bg-gray-50 rounded-lg border border-gray-200"
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-3 h-3 rounded-full ${
                            nodeType === 'supervisor'
                              ? 'bg-purple-500'
                              : nodeType === 'worker'
                              ? 'bg-blue-500'
                              : 'bg-green-500'
                          }`}
                        />
                        <div>
                          <div className="text-sm font-medium text-gray-900">{node.data.label}</div>
                          <div className="text-xs text-gray-500">
                            {nodeType === 'tool' ? 'API Call' : node.data.llmModel || 'N/A'}
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        {actualCost !== undefined ? (
                          <div>
                            <div className="text-sm font-semibold text-green-700">
                              ${actualCost.toFixed(4)}
                            </div>
                            <div className="text-xs text-gray-500">actual</div>
                          </div>
                        ) : (
                          <div>
                            <div className="text-sm font-medium text-gray-700">
                              ${estimatedCost.toFixed(4)}
                            </div>
                            <div className="text-xs text-gray-500">estimated</div>
                          </div>
                        )}
                      </div>
                    </div>
                  )
                })
              )}
            </div>

            {/* Summary */}
            <div className="mt-6 pt-4 border-t border-gray-200">
              <div className="flex items-center justify-between text-lg font-bold">
                <span className="text-gray-900">Total Estimated Cost:</span>
                <span className="text-green-700">${calculateEstimatedCost().toFixed(4)}</span>
              </div>
              {totalCost > 0 && (
                <div className="flex items-center justify-between text-sm mt-2">
                  <span className="text-gray-600">Actual Cost (Last Execution):</span>
                  <span className="font-semibold text-green-600">${totalCost.toFixed(4)}</span>
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="mt-6 pt-4 border-t border-gray-200">
              <p className="text-xs text-gray-500 text-center">
                Costs are estimated based on typical LLM usage. Actual costs may vary.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Execution History Modal */}
      {showHistory && (
        <div className="fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center">
          <div className="bg-white rounded-lg shadow-2xl p-6 max-w-3xl w-full mx-4 max-h-[80vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <div>
                <h3 className="text-xl font-bold text-gray-900">Execution History</h3>
                <p className="text-sm text-gray-500 mt-1">Last {executionHistory.length} workflow executions</p>
              </div>
              <button
                onClick={() => setShowHistory(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XCircle className="w-6 h-6" />
              </button>
            </div>

            {/* Execution History List */}
            <div className="space-y-3">
              {executionHistory.length === 0 ? (
                <p className="text-sm text-gray-500 italic text-center py-8">No execution history yet</p>
              ) : (
                executionHistory.map((execution, index) => (
                  <div
                    key={index}
                    className="p-4 bg-gray-50 rounded-lg border border-gray-200 hover:border-gray-300 transition-colors"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-3">
                        <div
                          className={`w-3 h-3 rounded-full ${
                            execution.status === 'success' ? 'bg-green-500' : 'bg-red-500'
                          }`}
                        />
                        <div>
                          <div className="text-sm font-medium text-gray-900">
                            {execution.status === 'success' ? 'Successful Execution' : 'Failed Execution'}
                          </div>
                          <div className="text-xs text-gray-500">{execution.timestamp}</div>
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-sm font-semibold text-gray-900">
                          ${(execution.cost ?? 0).toFixed(4)}
                        </div>
                        <div className="text-xs text-gray-500">
                          {(execution.duration ?? 0).toFixed(1)}s
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-4 mt-2 text-xs text-gray-600">
                      <span>{execution.nodeCount} nodes</span>
                      <span>•</span>
                      <span>
                        {((execution.cost ?? 0) / (execution.nodeCount || 1)).toFixed(4)} avg cost/node
                      </span>
                      <span>•</span>
                      <span>
                        {((execution.duration ?? 0) / (execution.nodeCount || 1)).toFixed(2)}s avg time/node
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>

            {/* Summary Stats */}
            {executionHistory.length > 0 && (
              <div className="mt-6 pt-4 border-t border-gray-200 grid grid-cols-3 gap-4">
                <div className="text-center">
                  <div className="text-2xl font-bold text-green-700">
                    {executionHistory.filter(e => e.status === 'success').length}
                  </div>
                  <div className="text-xs text-gray-600 mt-1">Successful</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-red-700">
                    {executionHistory.filter(e => e.status === 'failed').length}
                  </div>
                  <div className="text-xs text-gray-600 mt-1">Failed</div>
                </div>
                <div className="text-center">
                  <div className="text-2xl font-bold text-blue-700">
                    ${(executionHistory.reduce((sum, e) => sum + (e.cost ?? 0), 0) / (executionHistory.length || 1)).toFixed(4)}
                  </div>
                  <div className="text-xs text-gray-600 mt-1">Avg Cost</div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Template Modal */}
      <TemplateModal
        isOpen={showTemplateModal}
        category="workflow"
        onClose={() => setShowTemplateModal(false)}
        onSelectTemplate={handleSelectTemplate}
      />
    </div>
  )
}

// Export wrapped in ReactFlowProvider
export default function WorkflowDesigner() {
  return (
    <ReactFlowProvider>
      <WorkflowDesignerInner />
    </ReactFlowProvider>
  )
}
