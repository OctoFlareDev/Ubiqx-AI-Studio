export type ProjectStatus = 'active' | 'archived' | 'deleted'

export interface Profile {
  id: string
  display_name: string
  created_at: string
}

export interface Project {
  id: string
  name: string
  root_scene_id: string | null
  status: ProjectStatus
  created_at: string
  updated_at: string
  last_autosaved_at: string | null
}

export interface Asset {
  id: string
  project_id: string
  content_hash: string
  media_type: string
  original_name: string
  width: number | null
  height: number | null
  byte_size: number
  source: string
  metadata: Record<string, unknown>
  created_at: string
}

export interface Scene {
  id: string
  project_id: string
  root_node_id: string | null
  width: number
  height: number
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export interface SceneNode {
  id: string
  scene_id: string
  parent_id: string | null
  type: string
  name: string
  visible: boolean
  locked: boolean
  opacity: number
  transform: Record<string, number>
  asset_id: string | null
  text_properties: Record<string, unknown> | null
  style_properties: Record<string, unknown> | null
  effect_metadata: Record<string, unknown> | null
  order_index: number
  created_at: string
  updated_at: string
}

export interface ImportJob {
  id: string
  project_id: string
  source_asset_id: string
  adapter: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  progress: number
  warnings: Array<Record<string, unknown>>
  error: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface ExportManifest {
  format_version: number
  target: string
  scene: {
    id: string
    width: number
    height: number
    metadata: Record<string, unknown>
  }
  files: Record<string, { sha256: string; byte_size: number }>
  referenced_assets: Array<Record<string, unknown>>
  validation: {
    passed: boolean
    node_count: number
    asset_count: number
    warning_count: number
  }
}

export interface ExportJob {
  id: string
  project_id: string
  target: string
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  manifest: ExportManifest
  warnings: Array<Record<string, unknown>>
  error: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface AiTask {
  id: string
  project_id: string
  provider: string
  operation: 'upscale' | 'remove_background'
  input_asset_id: string
  output_asset_id: string | null
  options: Record<string, unknown>
  status: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
  progress: number
  retry_count: number
  last_error: string | null
  usage: Record<string, unknown>
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface ApiErrorEnvelope {
  error?: {
    code?: string
    message?: string
    request_id?: string | null
  }
}
