/**
 * Prompt Registry Types
 *
 * Type definitions for the Prompt Registry feature
 */

export interface PromptTemplate {
  id: string
  organization_id: string
  name: string
  slug: string
  description: string | null
  category: string | null
  default_version_id: string | null
  is_active: boolean
  created_at: string
  updated_at: string
  created_by: string | null
}

export interface PromptVersion {
  id: string
  template_id: string
  version: string
  content: string
  variables: string[]
  model_hint: string | null
  metadata: Record<string, any>
  is_published: boolean
  published_at: string | null
  created_at: string
  created_by: string | null
}

export interface PromptUsageStats {
  id: string
  version_id: string
  date: string
  invocations: number
  avg_latency_ms: number | null
  avg_tokens: number | null
  success_rate: number | null
}

export interface RenderPromptRequest {
  version?: string
  variables: Record<string, any>
}

export interface RenderPromptResponse {
  template_id: string
  version_id: string
  version: string
  content: string
  rendered_content: string
  variables: Record<string, any>
  model_hint: string | null
}

export interface CreateTemplateRequest {
  name: string
  description?: string
  category?: string
}

export interface CreateVersionRequest {
  version: string
  content: string
  model_hint?: string
  metadata?: Record<string, any>
}

export interface UpdateTemplateRequest {
  name?: string
  description?: string
  category?: string
  is_active?: boolean
}

export type PromptCategory =
  | 'classification'
  | 'generation'
  | 'extraction'
  | 'summarization'
  | 'translation'
  | 'conversation'
  | 'code'
  | 'analysis'
  | 'other'
