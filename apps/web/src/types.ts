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

export interface ApiErrorEnvelope {
  error?: {
    code?: string
    message?: string
    request_id?: string | null
  }
}

