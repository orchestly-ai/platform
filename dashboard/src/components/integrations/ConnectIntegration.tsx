import React, { useState, useEffect } from 'react'
import { X, Check, AlertCircle, Loader2, ExternalLink, Key, Shield, Zap, CheckCircle2 } from 'lucide-react'
import api from '../../services/api'

interface AuthField {
  name: string
  label: string
  type: string
  required: boolean
  help?: string
  placeholder?: string
}

interface IntegrationAuthConfig {
  integration_id: string
  integration_name: string
  auth_type: string
  requires_oauth: boolean
  fields: AuthField[]
  oauth_provider?: string
  nango_public_key?: string
}

interface ConnectIntegrationProps {
  integrationId: string
  integrationName?: string
  integrationIcon?: string
  onConnected?: (installationId: string) => void
  onClose?: () => void
  organizationId?: string
}

type ConnectionState = 'idle' | 'loading' | 'connected' | 'error'
type TestState = 'idle' | 'testing' | 'success' | 'failed'

export const ConnectIntegration: React.FC<ConnectIntegrationProps> = ({
  integrationId,
  integrationName,
  integrationIcon,
  onConnected,
  onClose,
  organizationId,
}) => {
  const [authConfig, setAuthConfig] = useState<IntegrationAuthConfig | null>(null)
  const [credentials, setCredentials] = useState<Record<string, string>>({})
  const [connectionState, setConnectionState] = useState<ConnectionState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [showHelp, setShowHelp] = useState<string | null>(null)
  const [testState, setTestState] = useState<TestState>('idle')
  const [testMessage, setTestMessage] = useState<string | null>(null)

  // Fetch auth config on mount
  useEffect(() => {
    fetchAuthConfig()
  }, [integrationId])

  const fetchAuthConfig = async () => {
    try {
      setConnectionState('loading')
      const response = await api.get(`/api/connections/${integrationId}/config`)
      setAuthConfig(response.data)
      setConnectionState('idle')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load integration config')
      setConnectionState('error')
    }
  }

  const handleCredentialChange = (fieldName: string, value: string) => {
    setCredentials(prev => ({ ...prev, [fieldName]: value }))
    setError(null)
  }

  const handleConnect = async () => {
    if (!authConfig) return

    // Validate required fields
    for (const field of authConfig.fields) {
      if (field.required && !credentials[field.name]) {
        setError(`${field.label} is required`)
        return
      }
    }

    try {
      setConnectionState('loading')
      setError(null)

      const response = await api.post(`/api/connections/${integrationId}/connect`, {
        credentials,
        organization_id: organizationId,
      })

      if (response.data.success) {
        setConnectionState('connected')
        onConnected?.(response.data.installation_id)
      } else {
        setError(response.data.message || 'Connection failed')
        setConnectionState('error')
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to connect')
      setConnectionState('error')
    }
  }

  const handleOAuthConnect = async () => {
    if (!authConfig?.nango_public_key) {
      setError('OAuth not configured')
      return
    }

    try {
      setConnectionState('loading')

      // Initialize Nango OAuth
      // In production, use the Nango SDK:
      // const nango = new Nango({ publicKey: authConfig.nango_public_key })
      // await nango.auth(authConfig.oauth_provider || integrationId, organizationId)

      // For now, show instructions
      setError('OAuth integration requires Nango SDK. Please configure NANGO_PUBLIC_KEY.')
      setConnectionState('idle')

    } catch (err: any) {
      setError(err.message || 'OAuth failed')
      setConnectionState('error')
    }
  }

  const handleTestConnection = async () => {
    if (!authConfig) return

    // Validate required fields before testing
    for (const field of authConfig.fields) {
      if (field.required && !credentials[field.name]) {
        setError(`${field.label} is required`)
        return
      }
    }

    try {
      setTestState('testing')
      setTestMessage(null)
      setError(null)

      // First, temporarily connect to test credentials
      const connectResponse = await api.post(`/api/connections/${integrationId}/connect`, {
        credentials,
        organization_id: organizationId,
      })

      if (!connectResponse.data.success) {
        setTestState('failed')
        setTestMessage(connectResponse.data.message || 'Connection failed')
        return
      }

      // Now test the connection
      const testUrl = organizationId
        ? `/api/connections/${integrationId}/test?organization_id=${organizationId}`
        : `/api/connections/${integrationId}/test`
      const testResponse = await api.post(testUrl, null)

      if (testResponse.data.success) {
        setTestState('success')
        setTestMessage('Credentials are valid! Click Connect to save.')
      } else {
        setTestState('failed')
        setTestMessage(testResponse.data.message || 'Test failed')
      }
    } catch (err: any) {
      setTestState('failed')
      setTestMessage(err.response?.data?.detail || 'Test failed')
    }
  }

  const hasCredentials = () => {
    if (!authConfig) return false
    return authConfig.fields
      .filter(f => f.required)
      .every(f => credentials[f.name]?.trim())
  }

  const renderAuthForm = () => {
    if (!authConfig) return null

    if (authConfig.requires_oauth) {
      return (
        <div className="space-y-4">
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
            <div className="flex items-start gap-3">
              <Shield className="w-5 h-5 text-blue-500 mt-0.5" />
              <div>
                <h4 className="font-medium text-blue-900">OAuth Connection</h4>
                <p className="text-sm text-blue-700 mt-1">
                  Click the button below to securely connect your {authConfig.integration_name} account.
                  You'll be redirected to authorize access.
                </p>
              </div>
            </div>
          </div>

          <button
            onClick={handleOAuthConnect}
            disabled={connectionState === 'loading'}
            className="w-full py-3 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {connectionState === 'loading' ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <ExternalLink className="w-5 h-5" />
            )}
            Connect with {authConfig.integration_name}
          </button>

          {/* Fallback to manual token entry */}
          {authConfig.fields.length > 0 && (
            <div className="mt-6 pt-6 border-t border-gray-200">
              <p className="text-sm text-gray-600 mb-4">
                Or enter credentials manually:
              </p>
              {renderCredentialFields()}
            </div>
          )}
        </div>
      )
    }

    return renderCredentialFields()
  }

  const renderCredentialFields = () => {
    if (!authConfig) return null

    return (
      <div className="space-y-4">
        {authConfig.fields.map(field => (
          <div key={field.name}>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-sm font-medium text-gray-700">
                {field.label}
                {field.required && <span className="text-red-500 ml-1">*</span>}
              </label>
              {field.help && (
                <button
                  type="button"
                  onClick={() => setShowHelp(showHelp === field.name ? null : field.name)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <AlertCircle className="w-4 h-4" />
                </button>
              )}
            </div>

            {showHelp === field.name && field.help && (
              <div className="mb-2 p-3 bg-gray-50 rounded-lg text-sm text-gray-600 whitespace-pre-wrap">
                {field.help}
              </div>
            )}

            <div className="relative">
              <input
                type={field.type === 'password' ? 'password' : 'text'}
                value={credentials[field.name] || ''}
                onChange={(e) => handleCredentialChange(field.name, e.target.value)}
                placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}`}
                className="w-full px-3 py-2 pl-10 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
              <Key className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
            </div>
          </div>
        ))}

        {/* Test Connection Result */}
        {testMessage && (
          <div className={`p-3 rounded-lg flex items-start gap-2 ${
            testState === 'success'
              ? 'bg-green-50 border border-green-200'
              : 'bg-yellow-50 border border-yellow-200'
          }`}>
            {testState === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-5 h-5 text-yellow-500 flex-shrink-0 mt-0.5" />
            )}
            <p className={`text-sm ${testState === 'success' ? 'text-green-700' : 'text-yellow-700'}`}>
              {testMessage}
            </p>
          </div>
        )}

        {/* Button Group */}
        <div className="flex gap-3">
          {/* Test Connection Button */}
          <button
            onClick={handleTestConnection}
            disabled={!hasCredentials() || testState === 'testing' || connectionState === 'loading'}
            className="flex-1 py-3 px-4 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2 border border-gray-300"
          >
            {testState === 'testing' ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : testState === 'success' ? (
              <CheckCircle2 className="w-5 h-5 text-green-500" />
            ) : (
              <Zap className="w-5 h-5" />
            )}
            {testState === 'testing' ? 'Testing...' : 'Test'}
          </button>

          {/* Connect Button */}
          <button
            onClick={handleConnect}
            disabled={connectionState === 'loading'}
            className="flex-[2] py-3 px-4 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {connectionState === 'loading' ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Check className="w-5 h-5" />
            )}
            Connect
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-gray-200">
          <div className="flex items-center gap-3">
            {integrationIcon && (
              <img src={integrationIcon} alt="" className="w-8 h-8 rounded" />
            )}
            <div>
              <h2 className="text-lg font-semibold text-gray-900">
                Connect {integrationName || authConfig?.integration_name || integrationId}
              </h2>
              <p className="text-sm text-gray-500">
                {authConfig?.auth_type === 'oauth2' ? 'OAuth' : 'API Key'} authentication
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 text-gray-400 hover:text-gray-600 rounded-lg hover:bg-gray-100"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-5">
          {connectionState === 'connected' ? (
            <div className="text-center py-6">
              <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <Check className="w-8 h-8 text-green-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">Connected!</h3>
              <p className="text-gray-600 mb-6">
                {authConfig?.integration_name || integrationId} has been successfully connected.
              </p>
              <button
                onClick={onClose}
                className="px-6 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200"
              >
                Close
              </button>
            </div>
          ) : (
            <>
              {error && (
                <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg flex items-start gap-2">
                  <AlertCircle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}

              {connectionState === 'loading' && !authConfig ? (
                <div className="flex items-center justify-center py-12">
                  <Loader2 className="w-8 h-8 animate-spin text-blue-500" />
                </div>
              ) : (
                renderAuthForm()
              )}
            </>
          )}
        </div>

        {/* Footer */}
        {connectionState !== 'connected' && (
          <div className="px-6 py-4 bg-gray-50 border-t border-gray-200">
            <p className="text-xs text-gray-500 text-center">
              Your credentials are encrypted and stored securely.
              {authConfig?.requires_oauth && ' OAuth tokens are managed by Nango.'}
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

export default ConnectIntegration
