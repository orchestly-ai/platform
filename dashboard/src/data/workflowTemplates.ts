/**
 * Workflow Templates
 * Pre-built templates for agents and workflows
 */

import type { Node, Edge } from 'reactflow';
import { AgentNodeData } from '../types';

export type TemplateCategory = 'agent' | 'workflow';

export interface WorkflowTemplate {
  id: string;
  name: string;
  description: string;
  category: TemplateCategory;
  tags: string[];
  icon: string;
  color: string;
  nodes: Node<AgentNodeData>[];
  edges: Edge[];
  estimatedCost?: number;
}

// Agent Templates (single-node workflows)
export const agentTemplates: WorkflowTemplate[] = [
  {
    id: 'customer-support-classifier',
    name: 'Customer Support Classifier',
    description: 'Automatically classify support tickets by intent and urgency',
    category: 'agent',
    tags: ['support', 'classification', 'gpt-4'],
    icon: '🎫',
    color: '#6366f1',
    estimatedCost: 0.02,
    nodes: [
      {
        id: 'agent-1',
        type: 'worker',
        position: { x: 250, y: 200 },
        data: {
          label: 'Support Classifier',
          type: 'worker',
          llmModel: 'gpt-4',
          capabilities: ['classification', 'intent-detection'],
          status: 'idle',
        },
      },
    ],
    edges: [],
  },
  {
    id: 'code-reviewer',
    name: 'Code Review Agent',
    description: 'Review code for security issues and best practices',
    category: 'agent',
    tags: ['development', 'code-review', 'claude'],
    icon: '💻',
    color: '#f59e0b',
    estimatedCost: 0.03,
    nodes: [
      {
        id: 'agent-1',
        type: 'worker',
        position: { x: 250, y: 200 },
        data: {
          label: 'Code Reviewer',
          type: 'worker',
          llmModel: 'claude-3-5-sonnet-20241022',
          capabilities: ['code-review', 'security-scan'],
          status: 'idle',
        },
      },
    ],
    edges: [],
  },
  {
    id: 'lead-scorer',
    name: 'Lead Scoring Agent',
    description: 'Score leads based on ICP fit and engagement',
    category: 'agent',
    tags: ['sales', 'scoring', 'gpt-4'],
    icon: '📊',
    color: '#22c55e',
    estimatedCost: 0.02,
    nodes: [
      {
        id: 'agent-1',
        type: 'worker',
        position: { x: 250, y: 200 },
        data: {
          label: 'Lead Scorer',
          type: 'worker',
          llmModel: 'gpt-4',
          capabilities: ['scoring', 'analysis'],
          status: 'idle',
        },
      },
    ],
    edges: [],
  },
  {
    id: 'content-moderator',
    name: 'Content Moderator',
    description: 'Check user-generated content for policy violations',
    category: 'agent',
    tags: ['moderation', 'safety', 'gpt-4'],
    icon: '🛡️',
    color: '#ef4444',
    estimatedCost: 0.01,
    nodes: [
      {
        id: 'agent-1',
        type: 'worker',
        position: { x: 250, y: 200 },
        data: {
          label: 'Content Moderator',
          type: 'worker',
          llmModel: 'gpt-4',
          capabilities: ['moderation', 'policy-check'],
          status: 'idle',
        },
      },
    ],
    edges: [],
  },
  {
    id: 'email-writer',
    name: 'Email Writer Agent',
    description: 'Draft professional emails based on context',
    category: 'agent',
    tags: ['communication', 'email', 'claude'],
    icon: '✉️',
    color: '#8b5cf6',
    estimatedCost: 0.02,
    nodes: [
      {
        id: 'agent-1',
        type: 'worker',
        position: { x: 250, y: 200 },
        data: {
          label: 'Email Writer',
          type: 'worker',
          llmModel: 'claude-3-5-sonnet-20241022',
          capabilities: ['writing', 'communication'],
          status: 'idle',
        },
      },
    ],
    edges: [],
  },
];

// Workflow Templates (multi-node workflows)
export const workflowTemplates: WorkflowTemplate[] = [
  {
    id: 'customer-support-triage',
    name: 'Customer Support Triage',
    description: 'Automatically classify and route support tickets to the right team based on intent and urgency',
    category: 'workflow',
    tags: ['support', 'classification', 'routing'],
    icon: '🎧',
    color: '#6366f1',
    estimatedCost: 0.05,
    nodes: [
      {
        id: 'trigger-1',
        type: 'trigger',
        position: { x: 100, y: 200 },
        data: {
          label: 'New Ticket',
          type: 'trigger',
          triggerConfig: { triggerType: 'webhook' },
          status: 'idle',
        },
      },
      {
        id: 'worker-1',
        type: 'worker',
        position: { x: 350, y: 200 },
        data: {
          label: 'Classify Intent',
          type: 'worker',
          llmModel: 'gpt-4',
          capabilities: ['classification'],
          status: 'idle',
        },
      },
      {
        id: 'condition-1',
        type: 'condition',
        position: { x: 600, y: 200 },
        data: {
          label: 'High Priority?',
          type: 'condition',
          conditionConfig: { expression: 'urgency === "high"', trueLabel: 'Urgent', falseLabel: 'Normal' },
          status: 'idle',
        },
      },
      {
        id: 'integration-1',
        type: 'integration',
        position: { x: 850, y: 100 },
        data: {
          label: 'Slack Alert',
          type: 'integration',
          integrationConfig: { integrationType: 'slack', action: 'send_message', parameters: { channel: '#support-urgent' } },
          status: 'idle',
        },
      },
      {
        id: 'integration-2',
        type: 'integration',
        position: { x: 850, y: 300 },
        data: {
          label: 'Assign to Queue',
          type: 'integration',
          integrationConfig: { integrationType: 'zendesk', action: 'update_ticket', parameters: {} },
          status: 'idle',
        },
      },
    ],
    edges: [
      { id: 'e1-2', source: 'trigger-1', target: 'worker-1' },
      { id: 'e2-3', source: 'worker-1', target: 'condition-1' },
      { id: 'e3-4', source: 'condition-1', target: 'integration-1', label: 'Urgent' },
      { id: 'e3-5', source: 'condition-1', target: 'integration-2', label: 'Normal' },
    ],
  },
  {
    id: 'lead-qualification',
    name: 'Lead Qualification Pipeline',
    description: 'Score and qualify leads automatically, enriching with company data and routing to sales',
    category: 'workflow',
    tags: ['sales', 'leads', 'enrichment'],
    icon: '👥',
    color: '#22c55e',
    estimatedCost: 0.08,
    nodes: [
      {
        id: 'trigger-1',
        type: 'trigger',
        position: { x: 100, y: 200 },
        data: {
          label: 'New Lead',
          type: 'trigger',
          triggerConfig: { triggerType: 'webhook' },
          status: 'idle',
        },
      },
      {
        id: 'integration-1',
        type: 'integration',
        position: { x: 350, y: 200 },
        data: {
          label: 'Enrich Data',
          type: 'integration',
          integrationConfig: { integrationType: 'custom', action: 'enrich_company', parameters: {} },
          status: 'idle',
        },
      },
      {
        id: 'worker-1',
        type: 'worker',
        position: { x: 600, y: 200 },
        data: {
          label: 'Score Lead',
          type: 'worker',
          llmModel: 'gpt-4',
          capabilities: ['scoring', 'analysis'],
          status: 'idle',
        },
      },
      {
        id: 'condition-1',
        type: 'condition',
        position: { x: 850, y: 200 },
        data: {
          label: 'Qualified?',
          type: 'condition',
          conditionConfig: { expression: 'score >= 70', trueLabel: 'MQL', falseLabel: 'Nurture' },
          status: 'idle',
        },
      },
      {
        id: 'integration-2',
        type: 'integration',
        position: { x: 1100, y: 100 },
        data: {
          label: 'Create Opportunity',
          type: 'integration',
          integrationConfig: { integrationType: 'salesforce', action: 'create_lead', parameters: {} },
          status: 'idle',
        },
      },
      {
        id: 'integration-3',
        type: 'integration',
        position: { x: 1100, y: 300 },
        data: {
          label: 'Add to Nurture',
          type: 'integration',
          integrationConfig: { integrationType: 'hubspot', action: 'create_contact', parameters: {} },
          status: 'idle',
        },
      },
    ],
    edges: [
      { id: 'e1-2', source: 'trigger-1', target: 'integration-1' },
      { id: 'e2-3', source: 'integration-1', target: 'worker-1' },
      { id: 'e3-4', source: 'worker-1', target: 'condition-1' },
      { id: 'e4-5', source: 'condition-1', target: 'integration-2', label: 'MQL' },
      { id: 'e4-6', source: 'condition-1', target: 'integration-3', label: 'Nurture' },
    ],
  },
  {
    id: 'code-review-automation',
    name: 'Code Review Automation',
    description: 'Automatically review pull requests for security issues, code quality, and best practices',
    category: 'workflow',
    tags: ['development', 'code-review', 'security'],
    icon: '🔍',
    color: '#f59e0b',
    estimatedCost: 0.12,
    nodes: [
      {
        id: 'trigger-1',
        type: 'trigger',
        position: { x: 100, y: 200 },
        data: {
          label: 'PR Opened',
          type: 'trigger',
          triggerConfig: { triggerType: 'webhook' },
          status: 'idle',
        },
      },
      {
        id: 'worker-1',
        type: 'worker',
        position: { x: 350, y: 100 },
        data: {
          label: 'Security Scan',
          type: 'worker',
          llmModel: 'claude-3-5-sonnet-20241022',
          capabilities: ['security-scan'],
          status: 'idle',
        },
      },
      {
        id: 'worker-2',
        type: 'worker',
        position: { x: 350, y: 300 },
        data: {
          label: 'Code Quality Review',
          type: 'worker',
          llmModel: 'claude-3-5-sonnet-20241022',
          capabilities: ['code-review'],
          status: 'idle',
        },
      },
      {
        id: 'supervisor-1',
        type: 'supervisor',
        position: { x: 600, y: 200 },
        data: {
          label: 'Summarize Reviews',
          type: 'supervisor',
          llmModel: 'gpt-4',
          capabilities: ['coordination', 'summarization'],
          status: 'idle',
        },
      },
      {
        id: 'condition-1',
        type: 'condition',
        position: { x: 850, y: 200 },
        data: {
          label: 'Issues Found?',
          type: 'condition',
          conditionConfig: { expression: 'issues.length > 0', trueLabel: 'Has Issues', falseLabel: 'All Clear' },
          status: 'idle',
        },
      },
      {
        id: 'integration-1',
        type: 'integration',
        position: { x: 1100, y: 100 },
        data: {
          label: 'Comment on PR',
          type: 'integration',
          integrationConfig: { integrationType: 'github', action: 'create_issue', parameters: {} },
          status: 'idle',
        },
      },
      {
        id: 'integration-2',
        type: 'integration',
        position: { x: 1100, y: 300 },
        data: {
          label: 'Approve PR',
          type: 'integration',
          integrationConfig: { integrationType: 'github', action: 'create_pr', parameters: {} },
          status: 'idle',
        },
      },
    ],
    edges: [
      { id: 'e1-2', source: 'trigger-1', target: 'worker-1' },
      { id: 'e1-3', source: 'trigger-1', target: 'worker-2' },
      { id: 'e2-4', source: 'worker-1', target: 'supervisor-1' },
      { id: 'e3-4', source: 'worker-2', target: 'supervisor-1' },
      { id: 'e4-5', source: 'supervisor-1', target: 'condition-1' },
      { id: 'e5-6', source: 'condition-1', target: 'integration-1', label: 'Has Issues' },
      { id: 'e5-7', source: 'condition-1', target: 'integration-2', label: 'All Clear' },
    ],
  },
  {
    id: 'content-moderation-hitl',
    name: 'Content Moderation with HITL',
    description: 'Moderate user-generated content for policy violations with human-in-the-loop escalation',
    category: 'workflow',
    tags: ['moderation', 'safety', 'human-in-loop'],
    icon: '🛡️',
    color: '#ef4444',
    estimatedCost: 0.04,
    nodes: [
      {
        id: 'trigger-1',
        type: 'trigger',
        position: { x: 100, y: 200 },
        data: {
          label: 'New Content',
          type: 'trigger',
          triggerConfig: { triggerType: 'webhook' },
          status: 'idle',
        },
      },
      {
        id: 'worker-1',
        type: 'worker',
        position: { x: 350, y: 200 },
        data: {
          label: 'Classify Content',
          type: 'worker',
          llmModel: 'gpt-4',
          capabilities: ['moderation', 'classification'],
          status: 'idle',
        },
      },
      {
        id: 'condition-1',
        type: 'condition',
        position: { x: 600, y: 200 },
        data: {
          label: 'Needs Review?',
          type: 'condition',
          conditionConfig: { expression: 'confidence < 0.9', trueLabel: 'Review', falseLabel: 'Auto-decide' },
          status: 'idle',
        },
      },
      {
        id: 'integration-1',
        type: 'integration',
        position: { x: 850, y: 100 },
        data: {
          label: 'Escalate to Human',
          type: 'integration',
          integrationConfig: { integrationType: 'slack', action: 'send_message', parameters: { channel: '#trust-safety' } },
          status: 'idle',
        },
      },
      {
        id: 'integration-2',
        type: 'integration',
        position: { x: 850, y: 300 },
        data: {
          label: 'Auto-approve',
          type: 'integration',
          integrationConfig: { integrationType: 'custom', action: 'publish_content', parameters: {} },
          status: 'idle',
        },
      },
    ],
    edges: [
      { id: 'e1-2', source: 'trigger-1', target: 'worker-1' },
      { id: 'e2-3', source: 'worker-1', target: 'condition-1' },
      { id: 'e3-4', source: 'condition-1', target: 'integration-1', label: 'Review' },
      { id: 'e3-5', source: 'condition-1', target: 'integration-2', label: 'Auto-decide' },
    ],
  },
  {
    id: 'email-response-automation',
    name: 'Email Response Automation',
    description: 'Draft and send email responses based on incoming messages and context',
    category: 'workflow',
    tags: ['communication', 'email', 'automation'],
    icon: '✉️',
    color: '#8b5cf6',
    estimatedCost: 0.06,
    nodes: [
      {
        id: 'trigger-1',
        type: 'trigger',
        position: { x: 100, y: 200 },
        data: {
          label: 'Email Received',
          type: 'trigger',
          triggerConfig: { triggerType: 'webhook' },
          status: 'idle',
        },
      },
      {
        id: 'worker-1',
        type: 'worker',
        position: { x: 350, y: 200 },
        data: {
          label: 'Analyze Intent',
          type: 'worker',
          llmModel: 'gpt-4',
          capabilities: ['classification', 'intent-detection'],
          status: 'idle',
        },
      },
      {
        id: 'worker-2',
        type: 'worker',
        position: { x: 600, y: 200 },
        data: {
          label: 'Draft Response',
          type: 'worker',
          llmModel: 'claude-3-5-sonnet-20241022',
          capabilities: ['writing', 'communication'],
          status: 'idle',
        },
      },
      {
        id: 'integration-1',
        type: 'integration',
        position: { x: 850, y: 200 },
        data: {
          label: 'Send Email',
          type: 'integration',
          integrationConfig: { integrationType: 'sendgrid', action: 'send_email', parameters: {} },
          status: 'idle',
        },
      },
    ],
    edges: [
      { id: 'e1-2', source: 'trigger-1', target: 'worker-1' },
      { id: 'e2-3', source: 'worker-1', target: 'worker-2' },
      { id: 'e3-4', source: 'worker-2', target: 'integration-1' },
    ],
  },
];

// Combined templates
export const allTemplates: WorkflowTemplate[] = [...agentTemplates, ...workflowTemplates];

// Helper function to get templates by category
export function getTemplatesByCategory(category: TemplateCategory): WorkflowTemplate[] {
  return allTemplates.filter(template => template.category === category);
}

// Helper function to get template by id
export function getTemplateById(id: string): WorkflowTemplate | undefined {
  return allTemplates.find(template => template.id === id);
}
