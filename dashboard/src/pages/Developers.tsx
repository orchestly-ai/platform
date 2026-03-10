/**
 * Developers Page - Integration guides and API documentation
 * Helps developers integrate their applications with the Orchestly platform
 */

import { useState } from 'react';
import {
  Code,
  Copy,
  CheckCircle,
  ExternalLink,
  Key,
  Zap,
  BookOpen,
  Terminal,
  Globe,
  Settings,
  ChevronRight,
  Play,
  FileCode,
  Package,
} from 'lucide-react';
import { NavLink } from 'react-router-dom';
import { Highlight, themes } from 'prism-react-renderer';

type Tab = 'quickstart' | 'python' | 'javascript' | 'rest';

export function DevelopersPage() {
  const [activeTab, setActiveTab] = useState<Tab>('quickstart');
  const [copiedSnippet, setCopiedSnippet] = useState<string | null>(null);

  // Get platform API URL — replace any dev port with the backend port
  const platformUrl = window.location.origin.replace(/:\d+$/, ':8000');

  const copyToClipboard = (text: string, id: string) => {
    navigator.clipboard.writeText(text);
    setCopiedSnippet(id);
    setTimeout(() => setCopiedSnippet(null), 2000);
  };

  // Map display labels to Prism language keys
  const langMap: Record<string, string> = {
    bash: 'bash',
    python: 'python',
    typescript: 'typescript',
    javascript: 'javascript',
    json: 'json',
    curl: 'bash',
    http: 'http',
    'environment variables': 'bash',
  };

  const CodeBlock = ({ code, language, id }: { code: string; language: string; id: string }) => {
    const prismLang = langMap[language.toLowerCase()] || 'bash';

    return (
      <div style={{ position: 'relative', marginTop: '12px' }}>
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          padding: '8px 16px',
          background: 'var(--bg-tertiary)',
          borderRadius: '8px 8px 0 0',
          borderBottom: '1px solid var(--border-color)',
        }}>
          <span style={{ fontSize: '12px', fontWeight: 500, color: 'var(--text-muted)', textTransform: 'uppercase' }}>
            {language}
          </span>
          <button
            onClick={() => copyToClipboard(code, id)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '4px 10px',
              background: 'transparent',
              border: 'none',
              color: copiedSnippet === id ? 'var(--success-color)' : 'var(--text-secondary)',
              cursor: 'pointer',
              fontSize: '12px',
              borderRadius: '4px',
            }}
          >
            {copiedSnippet === id ? <CheckCircle size={14} /> : <Copy size={14} />}
            {copiedSnippet === id ? 'Copied!' : 'Copy'}
          </button>
        </div>
        <Highlight theme={themes.oneDark} code={code.trim()} language={prismLang}>
          {({ style, tokens, getLineProps, getTokenProps }) => (
            <pre style={{
              ...style,
              margin: 0,
              padding: '16px',
              borderRadius: '0 0 8px 8px',
              overflow: 'auto',
              fontSize: '13px',
              lineHeight: '1.5',
              fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
            }}>
              {tokens.map((line, i) => (
                <div key={i} {...getLineProps({ line })}>
                  {line.map((token, key) => (
                    <span key={key} {...getTokenProps({ token })} />
                  ))}
                </div>
              ))}
            </pre>
          )}
        </Highlight>
      </div>
    );
  };

  const renderQuickstart = () => (
    <div>
      {/* Platform Info Card */}
      <div className="chart-card" style={{ marginBottom: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px' }}>
          <div style={{
            width: '48px',
            height: '48px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, var(--primary-color), #8b5cf6)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            flexShrink: 0,
          }}>
            <Globe size={24} color="white" />
          </div>
          <div style={{ flex: 1 }}>
            <h3 style={{ margin: '0 0 8px', fontSize: '16px', fontWeight: 600 }}>Platform URL</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <code style={{
                flex: 1,
                padding: '10px 14px',
                background: 'var(--bg-secondary)',
                borderRadius: '6px',
                fontSize: '14px',
                fontFamily: 'monospace',
              }}>
                {platformUrl}
              </code>
              <button
                className="btn-secondary"
                style={{ padding: '10px' }}
                onClick={() => copyToClipboard(platformUrl, 'platform-url')}
              >
                {copiedSnippet === 'platform-url' ? <CheckCircle size={16} /> : <Copy size={16} />}
              </button>
            </div>
            <p style={{ margin: '8px 0 0', fontSize: '13px', color: 'var(--text-muted)' }}>
              Use this URL to connect your applications to the Orchestly platform
            </p>
          </div>
        </div>
      </div>

      {/* Getting Started Steps */}
      <h3 style={{ fontSize: '18px', fontWeight: 600, margin: '0 0 16px' }}>Getting Started</h3>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
        {/* Step 1 */}
        <div className="chart-card" style={{ display: 'flex', gap: '16px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            background: 'var(--primary-color)',
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 600,
            fontSize: '14px',
            flexShrink: 0,
          }}>
            1
          </div>
          <div style={{ flex: 1 }}>
            <h4 style={{ margin: '0 0 8px', fontSize: '15px', fontWeight: 600 }}>Get your API Key</h4>
            <p style={{ margin: '0 0 12px', fontSize: '14px', color: 'var(--text-secondary)' }}>
              Create an API key from the Settings page. This key authenticates your application with the platform.
            </p>
            <NavLink to="/settings" className="btn-primary" style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', textDecoration: 'none', color: '#fff' }}>
              <Key size={16} />
              Go to API Keys
              <ChevronRight size={16} />
            </NavLink>
          </div>
        </div>

        {/* Step 2 */}
        <div className="chart-card" style={{ display: 'flex', gap: '16px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            background: 'var(--primary-color)',
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 600,
            fontSize: '14px',
            flexShrink: 0,
          }}>
            2
          </div>
          <div style={{ flex: 1 }}>
            <h4 style={{ margin: '0 0 8px', fontSize: '15px', fontWeight: 600 }}>Configure your application</h4>
            <p style={{ margin: '0 0 12px', fontSize: '14px', color: 'var(--text-secondary)' }}>
              Add the platform URL and API key to your application's configuration:
            </p>
            <CodeBlock
              language="Environment Variables"
              id="env-config"
              code={`ORCHESTLY_API_URL=${platformUrl}
ORCHESTLY_API_KEY=your-api-key-here
ORCHESTLY_ORG_ID=your-organization`}
            />
          </div>
        </div>

        {/* Step 3 */}
        <div className="chart-card" style={{ display: 'flex', gap: '16px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            background: 'var(--primary-color)',
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 600,
            fontSize: '14px',
            flexShrink: 0,
          }}>
            3
          </div>
          <div style={{ flex: 1 }}>
            <h4 style={{ margin: '0 0 8px', fontSize: '15px', fontWeight: 600 }}>Register your agent</h4>
            <p style={{ margin: '0 0 12px', fontSize: '14px', color: 'var(--text-secondary)' }}>
              Register your AI agent with the platform to enable orchestration, cost tracking, and monitoring.
            </p>
            <CodeBlock
              language="curl"
              id="register-agent"
              code={`curl -X POST "${platformUrl}/api/v1/agents/register" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: your-api-key" \\
  -d '{
    "name": "My-Application-Agent",
    "organization_id": "your-organization",
    "framework": "custom",
    "capabilities": [
      {
        "name": "task_processing",
        "description": "Process AI tasks",
        "avg_cost_per_task": 0.05
      }
    ],
    "cost_limit_daily": 100.0
  }'`}
            />
          </div>
        </div>

        {/* Step 4 */}
        <div className="chart-card" style={{ display: 'flex', gap: '16px' }}>
          <div style={{
            width: '32px',
            height: '32px',
            borderRadius: '50%',
            background: 'var(--primary-color)',
            color: 'white',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontWeight: 600,
            fontSize: '14px',
            flexShrink: 0,
          }}>
            4
          </div>
          <div style={{ flex: 1 }}>
            <h4 style={{ margin: '0 0 8px', fontSize: '15px', fontWeight: 600 }}>Execute tasks through the platform</h4>
            <p style={{ margin: '0 0 12px', fontSize: '14px', color: 'var(--text-secondary)' }}>
              Route your LLM calls through the platform to benefit from cost optimization, fallback handling, and monitoring.
            </p>
            <CodeBlock
              language="curl"
              id="execute-task"
              code={`curl -X POST "${platformUrl}/api/v1/llm/chat" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: your-api-key" \\
  -d '{
    "messages": [
      {"role": "user", "content": "Analyze this data..."}
    ],
    "model": "auto",
    "agent_id": "your-agent-id"
  }'`}
            />
          </div>
        </div>
      </div>

      {/* Quick Links */}
      <h3 style={{ fontSize: '18px', fontWeight: 600, margin: '32px 0 16px' }}>Resources</h3>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(250px, 1fr))', gap: '16px' }}>
        <a
          href={`${platformUrl}/docs`}
          target="_blank"
          rel="noopener noreferrer"
          className="chart-card"
          style={{ textDecoration: 'none', color: 'inherit', display: 'flex', alignItems: 'center', gap: '12px' }}
        >
          <BookOpen size={24} style={{ color: 'var(--primary-color)' }} />
          <div style={{ flex: 1 }}>
            <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 600 }}>API Documentation</h4>
            <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>Interactive Swagger/OpenAPI docs</p>
          </div>
          <ExternalLink size={16} style={{ color: 'var(--text-muted)' }} />
        </a>

        <a
          href={`${platformUrl}/redoc`}
          target="_blank"
          rel="noopener noreferrer"
          className="chart-card"
          style={{ textDecoration: 'none', color: 'inherit', display: 'flex', alignItems: 'center', gap: '12px' }}
        >
          <FileCode size={24} style={{ color: 'var(--primary-color)' }} />
          <div style={{ flex: 1 }}>
            <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 600 }}>ReDoc Reference</h4>
            <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>Clean API reference documentation</p>
          </div>
          <ExternalLink size={16} style={{ color: 'var(--text-muted)' }} />
        </a>

        <NavLink
          to="/settings"
          className="chart-card"
          style={{ textDecoration: 'none', color: 'inherit', display: 'flex', alignItems: 'center', gap: '12px' }}
        >
          <Key size={24} style={{ color: 'var(--primary-color)' }} />
          <div style={{ flex: 1 }}>
            <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 600 }}>API Keys</h4>
            <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>Manage your API credentials</p>
          </div>
          <ChevronRight size={16} style={{ color: 'var(--text-muted)' }} />
        </NavLink>

        <NavLink
          to="/agents"
          className="chart-card"
          style={{ textDecoration: 'none', color: 'inherit', display: 'flex', alignItems: 'center', gap: '12px' }}
        >
          <Settings size={24} style={{ color: 'var(--primary-color)' }} />
          <div style={{ flex: 1 }}>
            <h4 style={{ margin: 0, fontSize: '14px', fontWeight: 600 }}>View Agents</h4>
            <p style={{ margin: '4px 0 0', fontSize: '12px', color: 'var(--text-muted)' }}>Monitor registered agents</p>
          </div>
          <ChevronRight size={16} style={{ color: 'var(--text-muted)' }} />
        </NavLink>
      </div>
    </div>
  );

  const renderPythonExamples = () => (
    <div>
      <h3 style={{ fontSize: '18px', fontWeight: 600, margin: '0 0 16px' }}>Python Integration</h3>

      <div className="chart-card" style={{ marginBottom: '24px' }}>
        <h4 style={{ margin: '0 0 12px', fontSize: '15px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Package size={18} />
          Installation
        </h4>
        <CodeBlock
          language="bash"
          id="python-install"
          code={`pip install orchestly  # Official Orchestly Python SDK`}
        />
      </div>

      <div className="chart-card" style={{ marginBottom: '24px' }}>
        <h4 style={{ margin: '0 0 12px', fontSize: '15px', fontWeight: 600 }}>Orchestly Client</h4>
        <p style={{ margin: '0 0 12px', fontSize: '14px', color: 'var(--text-secondary)' }}>
          Create a reusable client for interacting with the platform:
        </p>
        <CodeBlock
          language="python"
          id="python-client"
          code={`import httpx
import os
from typing import Optional, Dict, Any, List

class OrchestlyClient:
    """Client for Orchestly Platform"""

    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        organization_id: str = None
    ):
        self.base_url = base_url or os.getenv("ORCHESTLY_API_URL", "${platformUrl}")
        self.api_key = api_key or os.getenv("ORCHESTLY_API_KEY")
        self.organization_id = organization_id or os.getenv("ORCHESTLY_ORG_ID", "default")
        self.agent_id: Optional[str] = None

    async def health_check(self) -> Dict[str, Any]:
        """Check if platform is healthy"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/health",
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()

    async def register_agent(
        self,
        name: str,
        capabilities: List[Dict],
        cost_limit_daily: float = 100.0,
        framework: str = "custom"
    ) -> str:
        """Register agent with the platform"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/api/v1/agents/register",
                headers=self._get_headers(),
                json={
                    "name": name,
                    "organization_id": self.organization_id,
                    "framework": framework,
                    "capabilities": capabilities,
                    "cost_limit_daily": cost_limit_daily
                }
            )
            response.raise_for_status()
            data = response.json()
            self.agent_id = data.get("agent_id")
            return self.agent_id

    async def chat_completion(
        self,
        messages: List[Dict],
        model: str = "auto",
        **kwargs
    ) -> Dict[str, Any]:
        """Execute LLM chat through orchestration"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.base_url}/api/v1/llm/chat",
                headers=self._get_headers(),
                json={
                    "messages": messages,
                    "model": model,
                    "agent_id": self.agent_id,
                    **kwargs
                }
            )
            response.raise_for_status()
            return response.json()

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-API-Key": self.api_key or "debug"
        }

# Usage example
async def main():
    client = OrchestlyClient()

    # Register agent
    agent_id = await client.register_agent(
        name="MyApp-Agent",
        capabilities=[{
            "name": "text_analysis",
            "description": "Analyze text content",
            "avg_cost_per_task": 0.05
        }]
    )
    print(f"Registered agent: {agent_id}")

    # Execute chat
    result = await client.chat_completion(
        messages=[{"role": "user", "content": "Hello, world!"}]
    )
    print(f"Response: {result}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())`}
        />
      </div>

      <div className="chart-card">
        <h4 style={{ margin: '0 0 12px', fontSize: '15px', fontWeight: 600 }}>Fallback Handling</h4>
        <p style={{ margin: '0 0 12px', fontSize: '14px', color: 'var(--text-secondary)' }}>
          Handle cases when the orchestration platform is unavailable:
        </p>
        <CodeBlock
          language="python"
          id="python-fallback"
          code={`async def execute_with_fallback(client: OrchestlyClient, messages: list):
    """Execute with automatic fallback to direct API calls"""
    try:
        # Try Orchestly first
        result = await client.chat_completion(messages)
        if not result.get("fallback_mode"):
            return result, True  # Orchestrated
    except Exception as e:
        print(f"Orchestly unavailable: {e}")

    # Fallback to direct API call
    # Replace with your preferred LLM provider
    import openai
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=messages
    )
    return {"content": response.choices[0].message.content}, False`}
        />
      </div>
    </div>
  );

  const renderJavaScriptExamples = () => (
    <div>
      <h3 style={{ fontSize: '18px', fontWeight: 600, margin: '0 0 16px' }}>JavaScript/TypeScript Integration</h3>

      <div className="chart-card" style={{ marginBottom: '24px' }}>
        <h4 style={{ margin: '0 0 12px', fontSize: '15px', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '8px' }}>
          <Package size={18} />
          Installation
        </h4>
        <CodeBlock
          language="bash"
          id="js-install"
          code={`npm install @orchestly/sdk  # Official Orchestly TypeScript SDK`}
        />
      </div>

      <div className="chart-card" style={{ marginBottom: '24px' }}>
        <h4 style={{ margin: '0 0 12px', fontSize: '15px', fontWeight: 600 }}>Orchestly Client</h4>
        <CodeBlock
          language="typescript"
          id="js-client"
          code={`import { OrchestlyClient } from '@orchestly/sdk';

// Initialize the client
const client = new OrchestlyClient({
  baseUrl: process.env.ORCHESTLY_API_URL || '${platformUrl}',
  apiKey: process.env.ORCHESTLY_API_KEY,
  organizationId: process.env.ORCHESTLY_ORG_ID || 'default',
});

async function main() {
  // Health check
  const health = await client.healthCheck();
  console.log('Platform status:', health.status);

  // Register agent
  const agentId = await client.registerAgent('MyApp-Agent', [
    { name: 'text_analysis', description: 'Analyze text', avg_cost_per_task: 0.05 }
  ]);
  console.log('Registered agent:', agentId);

  // Execute chat completion
  const result = await client.chatCompletion([
    { role: 'user', content: 'Hello, world!' }
  ]);
  console.log('Response:', result);
}

main().catch(console.error);`}
        />
      </div>

      <div className="chart-card">
        <h4 style={{ margin: '0 0 12px', fontSize: '15px', fontWeight: 600 }}>React Hook Example</h4>
        <CodeBlock
          language="typescript"
          id="react-hook"
          code={`import { useState, useEffect, useCallback } from 'react';
import { OrchestlyClient } from '@orchestly/sdk';

const client = new OrchestlyClient();

export function useOrchestly() {
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [agentId, setAgentId] = useState<string | null>(null);

  useEffect(() => {
    async function init() {
      try {
        await client.healthCheck();
        setConnected(true);

        const id = await client.registerAgent('ReactApp-Agent', [
          { name: 'ui_assistance', description: 'UI help', avg_cost_per_task: 0.03 }
        ]);
        setAgentId(id);
      } catch (error) {
        console.error('Orchestly unavailable:', error);
        setConnected(false);
      } finally {
        setLoading(false);
      }
    }
    init();
  }, []);

  const chat = useCallback(async (message: string) => {
    return client.chatCompletion([{ role: 'user', content: message }]);
  }, []);

  return { connected, loading, agentId, chat };
}`}
        />
      </div>
    </div>
  );

  const renderRestExamples = () => (
    <div>
      <h3 style={{ fontSize: '18px', fontWeight: 600, margin: '0 0 16px' }}>REST API Reference</h3>

      <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '24px' }}>
        <a
          href={`${platformUrl}/docs`}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-primary"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', textDecoration: 'none', color: '#fff' }}
        >
          <Play size={16} />
          Interactive API Docs (Swagger)
          <ExternalLink size={14} />
        </a>
        <a
          href={`${platformUrl}/redoc`}
          target="_blank"
          rel="noopener noreferrer"
          className="btn-secondary"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', textDecoration: 'none' }}
        >
          <FileCode size={16} />
          API Reference (ReDoc)
          <ExternalLink size={14} />
        </a>
      </div>

      <div className="chart-card" style={{ marginBottom: '24px' }}>
        <h4 style={{ margin: '0 0 8px', fontSize: '15px', fontWeight: 600 }}>Authentication</h4>
        <p style={{ margin: '0 0 12px', fontSize: '14px', color: 'var(--text-secondary)' }}>
          All API requests require an API key passed in the <code>X-API-Key</code> header:
        </p>
        <CodeBlock
          language="http"
          id="rest-auth"
          code={`GET /api/v1/agents HTTP/1.1
Host: ${platformUrl.replace('http://', '').replace('https://', '')}
X-API-Key: your-api-key-here
Content-Type: application/json`}
        />
      </div>

      <div className="chart-card" style={{ marginBottom: '24px' }}>
        <h4 style={{ margin: '0 0 8px', fontSize: '15px', fontWeight: 600 }}>Core Endpoints</h4>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
          {[
            { method: 'GET', path: '/health', desc: 'Health check endpoint' },
            { method: 'POST', path: '/api/v1/agents/register', desc: 'Register a new agent' },
            { method: 'GET', path: '/api/v1/agents', desc: 'List all agents' },
            { method: 'POST', path: '/api/v1/llm/chat', desc: 'Execute LLM chat completion' },
            { method: 'GET', path: '/api/v1/metrics', desc: 'Get usage metrics' },
            { method: 'GET', path: '/api/v1/costs/summary', desc: 'Get cost summary' },
          ].map((endpoint) => (
            <div key={endpoint.path} style={{ display: 'flex', alignItems: 'center', gap: '12px', padding: '12px 16px', background: 'var(--bg-secondary)', borderRadius: '6px' }}>
              <span style={{
                padding: '4px 8px',
                borderRadius: '4px',
                fontSize: '11px',
                fontWeight: 600,
                background: endpoint.method === 'GET' ? 'rgba(16, 185, 129, 0.1)' : 'rgba(99, 102, 241, 0.1)',
                color: endpoint.method === 'GET' ? '#10b981' : 'var(--primary-color)',
              }}>
                {endpoint.method}
              </span>
              <code style={{ fontSize: '13px', fontFamily: 'monospace' }}>{endpoint.path}</code>
              <span style={{ fontSize: '13px', color: 'var(--text-muted)', marginLeft: 'auto' }}>{endpoint.desc}</span>
            </div>
          ))}
        </div>
      </div>

      <div className="chart-card">
        <h4 style={{ margin: '0 0 8px', fontSize: '15px', fontWeight: 600 }}>Example: Chat Completion</h4>
        <CodeBlock
          language="curl"
          id="rest-chat"
          code={`curl -X POST "${platformUrl}/api/v1/llm/chat" \\
  -H "Content-Type: application/json" \\
  -H "X-API-Key: your-api-key" \\
  -d '{
    "messages": [
      {"role": "system", "content": "You are a helpful assistant."},
      {"role": "user", "content": "What is the weather like?"}
    ],
    "model": "auto",
    "agent_id": "your-agent-id",
    "temperature": 0.7,
    "max_tokens": 500
  }'`}
        />
        <h5 style={{ margin: '24px 0 8px', fontSize: '14px', fontWeight: 600 }}>Response</h5>
        <CodeBlock
          language="json"
          id="rest-chat-response"
          code={`{
  "content": "I don't have access to real-time weather data...",
  "model": "llama-3.3-70b-versatile",
  "usage": {
    "prompt_tokens": 28,
    "completion_tokens": 45,
    "total_tokens": 73
  },
  "cost": 0.0023,
  "provider": "groq"
}`}
        />
      </div>
    </div>
  );

  const tabs = [
    { id: 'quickstart' as const, label: 'Quick Start', icon: Zap },
    { id: 'python' as const, label: 'Python', icon: Terminal },
    { id: 'javascript' as const, label: 'JavaScript', icon: Code },
    { id: 'rest' as const, label: 'REST API', icon: Globe },
  ];

  const renderContent = () => {
    switch (activeTab) {
      case 'quickstart': return renderQuickstart();
      case 'python': return renderPythonExamples();
      case 'javascript': return renderJavaScriptExamples();
      case 'rest': return renderRestExamples();
      default: return null;
    }
  };

  return (
    <div>
      {/* Page Header */}
      <div className="page-header">
        <div className="page-title">
          <h1>Developers</h1>
          <p>Integrate your applications with the Orchestly platform</p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <a
            href={`${platformUrl}/docs`}
            target="_blank"
            rel="noopener noreferrer"
            className="btn-secondary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '8px', textDecoration: 'none' }}
          >
            <BookOpen size={16} />
            API Docs
            <ExternalLink size={14} />
          </a>
        </div>
      </div>

      {/* Tab Navigation */}
      <div style={{ display: 'flex', gap: '8px', marginBottom: '24px', borderBottom: '1px solid var(--border-color)', paddingBottom: '0' }}>
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                padding: '12px 20px',
                border: 'none',
                background: 'transparent',
                color: activeTab === tab.id ? 'var(--primary-color)' : 'var(--text-secondary)',
                fontSize: '14px',
                fontWeight: 500,
                cursor: 'pointer',
                borderBottom: activeTab === tab.id ? '2px solid var(--primary-color)' : '2px solid transparent',
                marginBottom: '-1px',
              }}
            >
              <Icon size={18} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Content */}
      {renderContent()}
    </div>
  );
}

export default DevelopersPage;
