/**
 * Compact Workflow Visualization for Time-Travel Debugger
 *
 * Shows workflow DAG with execution state highlighting
 */

import { memo, useMemo } from 'react'
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  BackgroundVariant,
  ReactFlowProvider,
} from 'reactflow'
import 'reactflow/dist/style.css'
import type { ExecutionStep } from '@/types/llm'

// Reuse existing node components
import SupervisorNode from './workflow/SupervisorNode'
import WorkerNode from './workflow/WorkerNode'
import ToolNode from './workflow/ToolNode'
import TriggerNode from './workflow/TriggerNode'
import IntegrationNode from './workflow/IntegrationNode'
import ConditionNode from './workflow/ConditionNode'

const nodeTypes = {
  supervisor: SupervisorNode,
  worker: WorkerNode,
  tool: ToolNode,
  trigger: TriggerNode,
  integration: IntegrationNode,
  condition: ConditionNode,
  // Map database node types to React components
  llm: WorkerNode,
  webhook: TriggerNode,
  http: ToolNode,
  input: TriggerNode,
  output: ToolNode,
}

interface WorkflowVisualizationProps {
  nodes: any[]
  edges: any[]
  currentStep?: ExecutionStep
  completedSteps?: ExecutionStep[]
}

/**
 * Normalize database nodes to ReactFlow format
 * Database format: { id: "1", type: "webhook", label: "Lead Webhook" }
 * ReactFlow format: { id: "1", type: "webhook", position: {x, y}, data: {...} }
 */
function normalizeNodes(nodes: any[]): Node[] {
  if (!nodes || nodes.length === 0) return []

  // Check if nodes are already in ReactFlow format
  const isReactFlowFormat = nodes[0]?.position && nodes[0]?.data

  if (isReactFlowFormat) {
    return nodes
  }

  // Convert simple database format to ReactFlow format
  // Auto-layout nodes horizontally with spacing
  return nodes.map((node, index) => ({
    id: node.id?.toString() || `node-${index}`,
    type: node.type || 'tool',
    position: {
      x: index * 250,
      y: 100
    },
    data: {
      label: node.label || `Node ${node.id}`,
      type: node.type || 'tool',
      status: 'idle',
    },
  }))
}

/**
 * Normalize database edges to ReactFlow format
 * Database format: { source: "1", target: "2" }
 * ReactFlow format: { id: "1-2", source: "1", target: "2" }
 */
function normalizeEdges(edges: any[]): Edge[] {
  if (!edges || edges.length === 0) return []

  // Check if edges already have IDs
  const hasIds = edges[0]?.id !== undefined

  if (hasIds) {
    return edges
  }

  // Add IDs to edges
  return edges.map((edge) => ({
    id: edge.id || `${edge.source}-${edge.target}`,
    source: edge.source?.toString() || '',
    target: edge.target?.toString() || '',
    type: edge.type,
    label: edge.label,
    animated: edge.animated,
    style: edge.style,
  }))
}

function WorkflowVisualizationInner({
  nodes,
  edges,
  currentStep,
  completedSteps = [],
}: WorkflowVisualizationProps) {
  // Normalize nodes and edges to ReactFlow format
  const normalizedNodes = useMemo(() => normalizeNodes(nodes), [nodes])
  const normalizedEdges = useMemo(() => normalizeEdges(edges), [edges])

  // Map steps to node IDs for highlighting
  const completedNodeIds = useMemo(() => {
    return new Set(completedSteps.map(step => step.name.toLowerCase().replace(/\s+/g, '-')))
  }, [completedSteps])

  const currentNodeId = currentStep?.name.toLowerCase().replace(/\s+/g, '-')

  // Enhance nodes with execution status
  const enhancedNodes: Node[] = useMemo(() => {
    return normalizedNodes.map(node => {
      const nodeId = node.id
      const step = completedSteps.find(s => s.name.toLowerCase().replace(/\s+/g, '-') === nodeId) || currentStep

      let status: 'idle' | 'pending' | 'running' | 'success' | 'error' = 'idle'
      if (currentNodeId === nodeId && currentStep?.status === 'running') {
        status = 'running'
      } else if (completedNodeIds.has(nodeId)) {
        const completedStep = completedSteps.find(s => s.name.toLowerCase().replace(/\s+/g, '-') === nodeId)
        status = completedStep?.status === 'failed' ? 'error' : 'success'
      } else if (currentStep && completedSteps.length > 0) {
        status = 'pending'
      }

      return {
        ...node,
        data: {
          ...node.data,
          status,
          cost: step?.state.cost,
          executionTime: step?.duration,
          error: step?.state.error,
        },
      }
    })
  }, [normalizedNodes, currentStep, completedSteps, completedNodeIds, currentNodeId])

  const enhancedEdges: Edge[] = useMemo(() => {
    return normalizedEdges.map(edge => ({
      ...edge,
      animated: completedNodeIds.has(edge.source),
      style: {
        ...edge.style,
        stroke: completedNodeIds.has(edge.source) ? '#10b981' : '#94a3b8',
        strokeWidth: completedNodeIds.has(edge.source) ? 2 : 1,
      },
    }))
  }, [normalizedEdges, completedNodeIds])

  return (
    <div className="h-full w-full">
      <ReactFlow
        nodes={enhancedNodes}
        edges={enhancedEdges}
        nodeTypes={nodeTypes}
        fitView
        attributionPosition="bottom-left"
        proOptions={{ hideAttribution: true }}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={true}
        zoomOnScroll={true}
        panOnDrag={true}
        minZoom={0.3}
        maxZoom={2}
      >
        <Background variant={BackgroundVariant.Dots} gap={12} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  )
}

export const WorkflowVisualization = memo(function WorkflowVisualization(props: WorkflowVisualizationProps) {
  return (
    <ReactFlowProvider>
      <WorkflowVisualizationInner {...props} />
    </ReactFlowProvider>
  )
})
