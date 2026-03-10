/**
 * Onboarding Wizard Component
 *
 * 4-step wizard guiding new users through their first Orchestly experience:
 * 1. Welcome — value props overview
 * 2. Connect Integration — Slack / GitHub OAuth
 * 3. Choose Template — pre-built workflow templates
 * 4. Run First Workflow — deploy & launch
 *
 * Dismissible. Tracks completion in user preferences via PUT /api/v1/auth/me.
 */

import { useState } from 'react';
import {
  Zap,
  GitBranch,
  MessageSquare,
  ArrowRight,
  ArrowLeft,
  CheckCircle,
  X,
  Sparkles,
  Bot,
  BarChart3,
  Github,
  Link,
  FileText,
  Database,
  Headphones,
  Rocket,
} from 'lucide-react';

interface OnboardingWizardProps {
  onComplete: () => void;
  onDismiss: () => void;
}

const STEPS = ['Welcome', 'Connect', 'Template', 'Launch'] as const;

type TemplateId = 'customer-support' | 'content-pipeline' | 'data-processing';

interface Template {
  id: TemplateId;
  title: string;
  description: string;
  icon: typeof Bot;
  color: string;
  nodes: number;
}

const TEMPLATES: Template[] = [
  {
    id: 'customer-support',
    title: 'Customer Support',
    description: 'Triage tickets, generate responses, escalate to humans',
    icon: Headphones,
    color: '#6366f1',
    nodes: 5,
  },
  {
    id: 'content-pipeline',
    title: 'Content Pipeline',
    description: 'Draft, review, and publish blog posts with AI',
    icon: FileText,
    color: '#10b981',
    nodes: 4,
  },
  {
    id: 'data-processing',
    title: 'Data Processing',
    description: 'Extract, transform, and load data between services',
    icon: Database,
    color: '#f59e0b',
    nodes: 6,
  },
];

export function OnboardingWizard({ onComplete, onDismiss }: OnboardingWizardProps) {
  const [step, setStep] = useState(0);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateId | null>(null);
  const [connectedIntegrations, setConnectedIntegrations] = useState<string[]>([]);

  const currentStep = STEPS[step];

  const handleNext = () => {
    if (step < STEPS.length - 1) {
      setStep(step + 1);
    }
  };

  const handleBack = () => {
    if (step > 0) {
      setStep(step - 1);
    }
  };

  const handleConnectIntegration = (name: string) => {
    // Toggle connection state (in real app, would trigger OAuth flow)
    setConnectedIntegrations((prev) =>
      prev.includes(name) ? prev.filter((n) => n !== name) : [...prev, name]
    );
  };

  const handleLaunch = () => {
    onComplete();
  };

  return (
    <div
      data-testid="onboarding-wizard"
      style={{
        background: 'var(--bg-primary)',
        border: '1px solid var(--border-color)',
        borderRadius: '16px',
        padding: '32px',
        maxWidth: '720px',
        margin: '0 auto',
        position: 'relative',
      }}
    >
      {/* Dismiss button */}
      <button
        data-testid="dismiss-button"
        onClick={onDismiss}
        style={{
          position: 'absolute',
          top: '16px',
          right: '16px',
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          color: 'var(--text-muted)',
          padding: '4px',
          borderRadius: '6px',
        }}
        aria-label="Dismiss onboarding"
      >
        <X size={20} />
      </button>

      {/* Step indicator */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'center',
          gap: '8px',
          marginBottom: '24px',
        }}
      >
        {STEPS.map((s, i) => (
          <div
            key={s}
            data-testid={`step-indicator-${i}`}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
            }}
          >
            <div
              style={{
                width: '28px',
                height: '28px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '12px',
                fontWeight: 600,
                background:
                  i < step
                    ? '#10b981'
                    : i === step
                    ? '#6366f1'
                    : 'var(--bg-secondary)',
                color: i <= step ? '#fff' : 'var(--text-muted)',
                transition: 'all 0.2s',
              }}
            >
              {i < step ? <CheckCircle size={14} /> : i + 1}
            </div>
            <span
              style={{
                fontSize: '12px',
                fontWeight: i === step ? 600 : 400,
                color: i === step ? 'var(--text-primary)' : 'var(--text-muted)',
              }}
            >
              {s}
            </span>
            {i < STEPS.length - 1 && (
              <div
                style={{
                  width: '24px',
                  height: '2px',
                  background:
                    i < step ? '#10b981' : 'var(--border-color)',
                  margin: '0 4px',
                }}
              />
            )}
          </div>
        ))}
      </div>

      {/* Step content */}
      <div style={{ minHeight: '280px' }}>
        {/* Step 1: Welcome */}
        {currentStep === 'Welcome' && (
          <div data-testid="step-welcome" style={{ textAlign: 'center' }}>
            <div
              style={{
                width: '64px',
                height: '64px',
                borderRadius: '16px',
                background: 'linear-gradient(135deg, #6366f1, #8b5cf6)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px',
              }}
            >
              <Sparkles size={32} color="#fff" />
            </div>
            <h2
              style={{
                fontSize: '24px',
                fontWeight: 700,
                marginBottom: '8px',
                color: 'var(--text-primary)',
              }}
            >
              Welcome to Orchestly
            </h2>
            <p
              style={{
                color: 'var(--text-secondary)',
                marginBottom: '24px',
                maxWidth: '480px',
                margin: '0 auto 24px',
              }}
            >
              Build, deploy, and manage AI agent workflows in minutes.
            </p>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: 'repeat(3, 1fr)',
                gap: '16px',
                textAlign: 'left',
              }}
            >
              {[
                {
                  icon: Bot,
                  title: 'AI Agents',
                  desc: 'Deploy autonomous agents with any LLM',
                },
                {
                  icon: GitBranch,
                  title: 'Visual Workflows',
                  desc: 'Drag-and-drop workflow builder',
                },
                {
                  icon: BarChart3,
                  title: 'Full Observability',
                  desc: 'Costs, latency, and audit logs',
                },
              ].map((item) => (
                <div
                  key={item.title}
                  style={{
                    padding: '16px',
                    background: 'var(--bg-secondary)',
                    borderRadius: '12px',
                  }}
                >
                  <item.icon
                    size={20}
                    style={{ color: '#6366f1', marginBottom: '8px' }}
                  />
                  <div
                    style={{
                      fontWeight: 600,
                      fontSize: '14px',
                      marginBottom: '4px',
                    }}
                  >
                    {item.title}
                  </div>
                  <div
                    style={{
                      fontSize: '12px',
                      color: 'var(--text-muted)',
                    }}
                  >
                    {item.desc}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Step 2: Connect Integration */}
        {currentStep === 'Connect' && (
          <div data-testid="step-connect">
            <h2
              style={{
                fontSize: '20px',
                fontWeight: 700,
                marginBottom: '8px',
                textAlign: 'center',
              }}
            >
              Connect an Integration
            </h2>
            <p
              style={{
                color: 'var(--text-secondary)',
                marginBottom: '24px',
                textAlign: 'center',
              }}
            >
              Connect your tools so workflows can interact with them.
            </p>
            <div
              style={{
                display: 'grid',
                gridTemplateColumns: '1fr 1fr',
                gap: '16px',
              }}
            >
              {[
                {
                  name: 'slack',
                  label: 'Slack',
                  icon: MessageSquare,
                  color: '#E01E5A',
                },
                {
                  name: 'github',
                  label: 'GitHub',
                  icon: Github,
                  color: '#333',
                },
              ].map((integration) => {
                const connected = connectedIntegrations.includes(
                  integration.name
                );
                return (
                  <button
                    key={integration.name}
                    data-testid={`connect-${integration.name}`}
                    onClick={() =>
                      handleConnectIntegration(integration.name)
                    }
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '12px',
                      padding: '16px 20px',
                      border: `2px solid ${connected ? '#10b981' : 'var(--border-color)'}`,
                      borderRadius: '12px',
                      background: connected
                        ? 'rgba(16, 185, 129, 0.05)'
                        : 'var(--bg-primary)',
                      cursor: 'pointer',
                      transition: 'all 0.2s',
                    }}
                  >
                    <integration.icon
                      size={24}
                      style={{ color: integration.color }}
                    />
                    <div style={{ flex: 1, textAlign: 'left' }}>
                      <div style={{ fontWeight: 600 }}>
                        {integration.label}
                      </div>
                      <div
                        style={{
                          fontSize: '12px',
                          color: 'var(--text-muted)',
                        }}
                      >
                        {connected ? 'Connected' : 'Click to connect'}
                      </div>
                    </div>
                    {connected && (
                      <CheckCircle size={20} style={{ color: '#10b981' }} />
                    )}
                    {!connected && (
                      <Link size={16} style={{ color: 'var(--text-muted)' }} />
                    )}
                  </button>
                );
              })}
            </div>
            <p
              style={{
                fontSize: '12px',
                color: 'var(--text-muted)',
                textAlign: 'center',
                marginTop: '16px',
              }}
            >
              You can skip this step and connect integrations later.
            </p>
          </div>
        )}

        {/* Step 3: Choose Template */}
        {currentStep === 'Template' && (
          <div data-testid="step-template">
            <h2
              style={{
                fontSize: '20px',
                fontWeight: 700,
                marginBottom: '8px',
                textAlign: 'center',
              }}
            >
              Choose a Template
            </h2>
            <p
              style={{
                color: 'var(--text-secondary)',
                marginBottom: '24px',
                textAlign: 'center',
              }}
            >
              Start with a pre-built workflow and customize it.
            </p>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
              }}
            >
              {TEMPLATES.map((template) => {
                const selected = selectedTemplate === template.id;
                return (
                  <button
                    key={template.id}
                    data-testid={`template-${template.id}`}
                    onClick={() => setSelectedTemplate(template.id)}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: '16px',
                      padding: '16px 20px',
                      border: `2px solid ${selected ? template.color : 'var(--border-color)'}`,
                      borderRadius: '12px',
                      background: selected
                        ? `${template.color}08`
                        : 'var(--bg-primary)',
                      cursor: 'pointer',
                      textAlign: 'left',
                      transition: 'all 0.2s',
                    }}
                  >
                    <div
                      style={{
                        width: '40px',
                        height: '40px',
                        borderRadius: '10px',
                        background: `${template.color}15`,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        flexShrink: 0,
                      }}
                    >
                      <template.icon
                        size={20}
                        style={{ color: template.color }}
                      />
                    </div>
                    <div style={{ flex: 1 }}>
                      <div style={{ fontWeight: 600, marginBottom: '2px' }}>
                        {template.title}
                      </div>
                      <div
                        style={{
                          fontSize: '13px',
                          color: 'var(--text-muted)',
                        }}
                      >
                        {template.description}
                      </div>
                    </div>
                    <div
                      style={{
                        fontSize: '12px',
                        color: 'var(--text-muted)',
                        whiteSpace: 'nowrap',
                      }}
                    >
                      {template.nodes} nodes
                    </div>
                    {selected && (
                      <CheckCircle
                        size={20}
                        style={{ color: template.color }}
                      />
                    )}
                  </button>
                );
              })}
            </div>
          </div>
        )}

        {/* Step 4: Launch */}
        {currentStep === 'Launch' && (
          <div data-testid="step-launch" style={{ textAlign: 'center' }}>
            <div
              style={{
                width: '64px',
                height: '64px',
                borderRadius: '16px',
                background: 'linear-gradient(135deg, #10b981, #059669)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                margin: '0 auto 16px',
              }}
            >
              <Rocket size={32} color="#fff" />
            </div>
            <h2
              style={{
                fontSize: '24px',
                fontWeight: 700,
                marginBottom: '8px',
              }}
            >
              Ready to Launch!
            </h2>
            <p
              style={{
                color: 'var(--text-secondary)',
                marginBottom: '24px',
                maxWidth: '400px',
                margin: '0 auto 24px',
              }}
            >
              {selectedTemplate
                ? `Your "${TEMPLATES.find((t) => t.id === selectedTemplate)?.title}" workflow will be created and opened in the builder.`
                : 'Click below to explore the workflow builder.'}
            </p>
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: '12px',
                padding: '16px',
                background: 'var(--bg-secondary)',
                borderRadius: '12px',
                textAlign: 'left',
                maxWidth: '400px',
                margin: '0 auto',
              }}
            >
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <CheckCircle size={16} style={{ color: '#10b981' }} />
                <span style={{ fontSize: '14px' }}>Account created</span>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <CheckCircle
                  size={16}
                  style={{
                    color: connectedIntegrations.length > 0 ? '#10b981' : 'var(--text-muted)',
                  }}
                />
                <span style={{ fontSize: '14px' }}>
                  {connectedIntegrations.length > 0
                    ? `${connectedIntegrations.length} integration(s) connected`
                    : 'No integrations (you can add later)'}
                </span>
              </div>
              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                <CheckCircle
                  size={16}
                  style={{
                    color: selectedTemplate ? '#10b981' : 'var(--text-muted)',
                  }}
                />
                <span style={{ fontSize: '14px' }}>
                  {selectedTemplate
                    ? `Template: ${TEMPLATES.find((t) => t.id === selectedTemplate)?.title}`
                    : 'No template selected'}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Navigation buttons */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          marginTop: '24px',
          paddingTop: '16px',
          borderTop: '1px solid var(--border-color)',
        }}
      >
        <button
          data-testid="back-button"
          onClick={handleBack}
          disabled={step === 0}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '6px',
            padding: '10px 20px',
            border: '1px solid var(--border-color)',
            borderRadius: '8px',
            background: 'transparent',
            cursor: step === 0 ? 'default' : 'pointer',
            opacity: step === 0 ? 0.3 : 1,
            color: 'var(--text-primary)',
            fontWeight: 500,
          }}
        >
          <ArrowLeft size={16} />
          Back
        </button>

        {step < STEPS.length - 1 ? (
          <button
            data-testid="next-button"
            onClick={handleNext}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '10px 24px',
              border: 'none',
              borderRadius: '8px',
              background: '#6366f1',
              color: '#fff',
              cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            Next
            <ArrowRight size={16} />
          </button>
        ) : (
          <button
            data-testid="launch-button"
            onClick={handleLaunch}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '10px 24px',
              border: 'none',
              borderRadius: '8px',
              background: '#10b981',
              color: '#fff',
              cursor: 'pointer',
              fontWeight: 600,
            }}
          >
            <Rocket size={16} />
            Deploy & Run
          </button>
        )}
      </div>
    </div>
  );
}

export default OnboardingWizard;
