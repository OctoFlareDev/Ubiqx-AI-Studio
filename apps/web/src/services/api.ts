import type {
  AiTask,
  ApiErrorEnvelope,
  Asset,
  ExportJob,
  ImportJob,
  Profile,
  Project,
  Scene,
  SceneNode,
} from '@/types'

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1'
const TOKEN_KEY = 'ubiqx.local-api-key'

let accessToken = localStorage.getItem(TOKEN_KEY) ?? ''

export class ApiError extends Error {
  status: number
  code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

async function request<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers)
  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`)
  }
  if (init.body && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (response.status === 204) {
    return undefined as T
  }
  if (!response.ok) {
    if (response.status === 401 && retry && !path.startsWith('/auth/bootstrap')) {
      accessToken = ''
      localStorage.removeItem(TOKEN_KEY)
      await ensureSession()
      return request<T>(path, init, false)
    }
    let envelope: ApiErrorEnvelope = {}
    try {
      envelope = (await response.json()) as ApiErrorEnvelope
    } catch {
      // Fall through to the generic message below.
    }
    const message = envelope.error?.message ?? response.statusText
    throw new ApiError(response.status, envelope.error?.code ?? 'request_failed', message)
  }
  return (await response.json()) as T
}

async function requestBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  })
  if (!response.ok) {
    throw await responseError(response)
  }
  return response.blob()
}

async function requestText(path: string): Promise<string> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  })
  if (!response.ok) {
    throw await responseError(response)
  }
  return response.text()
}

async function responseError(response: Response): Promise<ApiError> {
  let envelope: ApiErrorEnvelope = {}
  try {
    envelope = (await response.json()) as ApiErrorEnvelope
  } catch {
    // Fall through to the generic message below.
  }
  return new ApiError(
    response.status,
    envelope.error?.code ?? 'request_failed',
    envelope.error?.message ?? response.statusText,
  )
}

export async function ensureSession(): Promise<Profile> {
  if (accessToken) {
    try {
      return await request<Profile>('/auth/profile', {}, false)
    } catch {
      accessToken = ''
      localStorage.removeItem(TOKEN_KEY)
    }
  }
  const result = await request<{ user: Profile; api_key: string }>('/auth/bootstrap', { method: 'POST' }, false)
  accessToken = result.api_key
  localStorage.setItem(TOKEN_KEY, accessToken)
  return result.user
}

export function hasSession(): boolean {
  return Boolean(accessToken)
}

export const api = {
  profile: () => request<Profile>('/auth/profile'),
  listProjects: () => request<{ items: Project[]; next_cursor: string | null }>('/projects'),
  createProject: (payload: { name: string; width?: number; height?: number }) =>
    request<Project>('/projects', { method: 'POST', body: JSON.stringify(payload) }),
  updateProject: (projectId: string, payload: { name?: string }) =>
    request<Project>(`/projects/${projectId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  archiveProject: (projectId: string) =>
    request<Project>(`/projects/${projectId}/archive`, { method: 'POST' }),
  restoreProject: (projectId: string) =>
    request<Project>(`/projects/${projectId}/restore`, { method: 'POST' }),
  deleteProject: (projectId: string) =>
    request<void>(`/projects/${projectId}`, { method: 'DELETE' }),
  getScene: (projectId: string) => request<Scene>(`/projects/${projectId}/scene`),
  listNodes: (sceneId: string) => request<SceneNode[]>(`/scenes/${sceneId}/nodes`),
  createNode: (
    projectId: string,
    payload: {
      parent_id?: string | null
      type: 'image' | 'group' | 'layer' | 'text' | 'shape'
      name: string
      asset_id?: string | null
      transform?: Record<string, number>
      opacity?: number
      text_properties?: Record<string, unknown> | null
      style_properties?: Record<string, unknown> | null
      effect_metadata?: Record<string, unknown> | null
    },
  ) => request<SceneNode>(`/projects/${projectId}/scene/nodes`, { method: 'POST', body: JSON.stringify(payload) }),
  updateNode: (
    sceneId: string,
    nodeId: string,
    payload: {
      name?: string
      visible?: boolean
      locked?: boolean
      opacity?: number
      transform?: Record<string, number>
      asset_id?: string | null
      text_properties?: Record<string, unknown> | null
      style_properties?: Record<string, unknown> | null
      effect_metadata?: Record<string, unknown> | null
    },
  ) => request<SceneNode>(`/scenes/${sceneId}/nodes/${nodeId}`, { method: 'PATCH', body: JSON.stringify(payload) }),
  listAssets: (projectId: string) => request<Asset[]>(`/projects/${projectId}/assets`),
  getAssetContent: (assetId: string) => requestBlob(`/assets/${assetId}/content`),
  uploadAsset: (projectId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Asset>(`/projects/${projectId}/assets`, { method: 'POST', body: form })
  },
  deleteAsset: (assetId: string) => request<void>(`/assets/${assetId}`, { method: 'DELETE' }),
  createImport: (projectId: string, sourceAssetId: string, adapter: 'psd' | 'raster' | 'svg' = 'psd') =>
    request<ImportJob>(`/projects/${projectId}/imports`, {
      method: 'POST',
      body: JSON.stringify({ source_asset_id: sourceAssetId, adapter }),
    }),
  getImport: (importId: string) => request<ImportJob>(`/imports/${importId}`),
  cancelImport: (importId: string) =>
    request<ImportJob>(`/imports/${importId}/cancel`, { method: 'POST' }),
  createExport: (projectId: string) =>
    request<ExportJob>(`/projects/${projectId}/exports`, {
      method: 'POST',
      body: JSON.stringify({ target: 'html5' }),
    }),
  getExport: (exportId: string) => request<ExportJob>(`/exports/${exportId}`),
  downloadExport: (exportId: string) => requestBlob(`/exports/${exportId}/download`),
  getExportPreview: (exportId: string) => requestText(`/exports/${exportId}/preview`),
  createAiTask: (
    projectId: string,
    inputAssetId: string,
    operation: 'upscale' | 'remove_background',
  ) =>
    request<AiTask>(`/projects/${projectId}/ai-tasks`, {
      method: 'POST',
      body: JSON.stringify({
        operation,
        provider: 'local',
        input_asset_id: inputAssetId,
        options: operation === 'upscale' ? { scale: 2 } : {},
      }),
    }),
  getAiTask: (taskId: string) => request<AiTask>(`/ai-tasks/${taskId}`),
  listAiTasks: (projectId: string) =>
    request<{ items: AiTask[]; next_cursor: string | null }>(`/projects/${projectId}/ai-tasks`),
  cancelAiTask: (taskId: string) =>
    request<AiTask>(`/ai-tasks/${taskId}/cancel`, { method: 'POST' }),
}
