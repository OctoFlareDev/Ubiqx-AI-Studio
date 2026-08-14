import type { ApiErrorEnvelope, Asset, Profile, Project, Scene, SceneNode, ImportJob, ExportJob, AiTask } from '@/types'
import { generatedClient, setGeneratedAccessToken } from '@/services/generated-client'

const API_BASE = import.meta.env.VITE_API_BASE ?? '/api/v1'

let accessToken = ''

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

  const response = await fetch(`${API_BASE}${path}`, { ...init, headers, credentials: 'include' })
  if (response.status === 204) {
    return undefined as T
  }
  if (!response.ok) {
    if (response.status === 401 && retry && !path.startsWith('/auth/bootstrap')) {
      accessToken = ''
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

type GeneratedResult<T> = {
  data?: T
  error?: unknown
  response: Response
}

async function generatedRequest<T>(
  requestFactory: () => Promise<GeneratedResult<unknown>>,
  retry = true,
): Promise<T> {
  const result = await requestFactory()
  if (result.response.status === 401 && retry) {
    accessToken = ''
    setGeneratedAccessToken('')
    await ensureSession()
    return generatedRequest(requestFactory, false)
  }
  if (!result.response.ok) {
    const envelope = (result.error ?? {}) as ApiErrorEnvelope
    throw new ApiError(
      result.response.status,
      envelope.error?.code ?? 'request_failed',
      envelope.error?.message ?? result.response.statusText,
    )
  }
  return result.data as T
}

async function requestBlob(path: string): Promise<Blob> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    credentials: 'include',
  })
  if (!response.ok) {
    throw await responseError(response)
  }
  return response.blob()
}

async function requestText(path: string): Promise<string> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
    credentials: 'include',
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

function versionParams(version?: number): { 'If-Match'?: string } {
  return version === undefined ? {} : { 'If-Match': `"${version}"` }
}

function generatedTransform(transform?: Record<string, number>) {
  return {
    x: transform?.x ?? 0,
    y: transform?.y ?? 0,
    width: transform?.width ?? 100,
    height: transform?.height ?? 100,
    rotation: transform?.rotation ?? 0,
    scale_x: transform?.scale_x ?? 1,
    scale_y: transform?.scale_y ?? 1,
  }
}

export async function ensureSession(): Promise<Profile> {
  if (accessToken) {
    try {
      return await generatedRequest<Profile>(
        () => generatedClient.GET('/api/v1/auth/profile', {}),
        false,
      )
    } catch {
      accessToken = ''
      setGeneratedAccessToken('')
    }
  }
  const result = await generatedRequest<{ user: Profile; api_key: string }>(
    () => generatedClient.POST('/api/v1/auth/bootstrap', {}),
    false,
  )
  accessToken = ''
  setGeneratedAccessToken('')
  return result.user
}

export function hasSession(): boolean {
  return Boolean(accessToken)
}

export const api = {
  profile: () => generatedRequest<Profile>(() => generatedClient.GET('/api/v1/auth/profile', {})),
  listProjects: (status: 'active' | 'archived' = 'active') =>
    generatedRequest<{ items: Project[]; next_cursor: string | null }>(() => generatedClient.GET('/api/v1/projects', { params: { query: { status } } })),
  createProject: (payload: { name: string; width?: number; height?: number }) =>
    generatedRequest<Project>(() => generatedClient.POST('/api/v1/projects', { body: { ...payload, width: payload.width ?? 1920, height: payload.height ?? 1080 } })),
  updateProject: (projectId: string, payload: { name?: string; last_autosaved_at?: string }, version?: number) =>
    generatedRequest<Project>(() =>
      generatedClient.PATCH('/api/v1/projects/{project_id}', {
        params: { path: { project_id: projectId }, header: versionParams(version) },
        body: payload,
      }),
    ),
  archiveProject: (projectId: string, version?: number) =>
    generatedRequest<Project>(() =>
      generatedClient.POST('/api/v1/projects/{project_id}/archive', {
        params: { path: { project_id: projectId }, header: versionParams(version) },
      }),
    ),
  restoreProject: (projectId: string, version?: number) =>
    generatedRequest<Project>(() =>
      generatedClient.POST('/api/v1/projects/{project_id}/restore', {
        params: { path: { project_id: projectId }, header: versionParams(version) },
      }),
    ),
  deleteProject: (projectId: string, version?: number) =>
    generatedRequest<void>(() =>
      generatedClient.DELETE('/api/v1/projects/{project_id}', {
        params: { path: { project_id: projectId }, header: versionParams(version) },
      }),
    ),
  getScene: (projectId: string) =>
    generatedRequest<Scene>(() => generatedClient.GET('/api/v1/projects/{project_id}/scene', { params: { path: { project_id: projectId } } })),
  listNodes: (sceneId: string) =>
    generatedRequest<SceneNode[]>(() => generatedClient.GET('/api/v1/scenes/{scene_id}/nodes', { params: { path: { scene_id: sceneId } } })),
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
  ) =>
    generatedRequest<SceneNode>(() =>
      generatedClient.POST('/api/v1/projects/{project_id}/scene/nodes', {
        params: { path: { project_id: projectId } },
        body: {
          ...payload,
          opacity: payload.opacity ?? 1,
          transform: generatedTransform(payload.transform),
        },
      }),
    ),
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
    version?: number,
  ) =>
    generatedRequest<SceneNode>(() =>
      generatedClient.PATCH('/api/v1/scenes/{scene_id}/nodes/{node_id}', {
        params: {
          path: { scene_id: sceneId, node_id: nodeId },
          header: versionParams(version),
        },
        body: (() => {
          const { transform, ...rest } = payload
          return transform ? { ...rest, transform: generatedTransform(transform) } : rest
        })(),
      }),
    ),
  listAssets: (projectId: string) =>
    generatedRequest<Asset[]>(() => generatedClient.GET('/api/v1/projects/{project_id}/assets', { params: { path: { project_id: projectId } } })),
  assetContentUrl: (assetId: string) => `${API_BASE}/assets/${assetId}/content`,
  getAssetContent: (assetId: string) => requestBlob(`/assets/${assetId}/content`),
  uploadAsset: (projectId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return request<Asset>(`/projects/${projectId}/assets`, { method: 'POST', body: form })
  },
  deleteAsset: (assetId: string) =>
    generatedRequest<void>(() => generatedClient.DELETE('/api/v1/assets/{asset_id}', { params: { path: { asset_id: assetId } } })),
  createImport: (projectId: string, sourceAssetId: string, adapter: 'psd' | 'raster' | 'svg' = 'psd') =>
    generatedRequest<ImportJob>(() =>
      generatedClient.POST('/api/v1/projects/{project_id}/imports', {
        params: { path: { project_id: projectId } },
        body: { source_asset_id: sourceAssetId, adapter },
      }),
    ),
  getImport: (importId: string) =>
    generatedRequest<ImportJob>(() => generatedClient.GET('/api/v1/imports/{import_id}', { params: { path: { import_id: importId } } })),
  cancelImport: (importId: string) =>
    generatedRequest<ImportJob>(() => generatedClient.POST('/api/v1/imports/{import_id}/cancel', { params: { path: { import_id: importId } } })),
  createExport: (projectId: string) =>
    generatedRequest<ExportJob>(() =>
      generatedClient.POST('/api/v1/projects/{project_id}/exports', {
        params: { path: { project_id: projectId } },
        body: { target: 'html5' },
      }),
    ),
  getExport: (exportId: string) =>
    generatedRequest<ExportJob>(() => generatedClient.GET('/api/v1/exports/{export_id}', { params: { path: { export_id: exportId } } })),
  downloadExport: (exportId: string) => requestBlob(`/exports/${exportId}/download`),
  getExportPreview: (exportId: string) => requestText(`/exports/${exportId}/preview`),
  createAiTask: (
    projectId: string,
    inputAssetId: string,
    operation: 'upscale' | 'remove_background',
  ) =>
    generatedRequest<AiTask>(() =>
      generatedClient.POST('/api/v1/projects/{project_id}/ai-tasks', {
        params: { path: { project_id: projectId } },
        body: {
          operation,
          provider: 'local',
          input_asset_id: inputAssetId,
          options: operation === 'upscale' ? { scale: 2 } : {},
        },
      }),
    ),
  getAiTask: (taskId: string) =>
    generatedRequest<AiTask>(() => generatedClient.GET('/api/v1/ai-tasks/{task_id}', { params: { path: { task_id: taskId } } })),
  listAiTasks: (projectId: string) =>
    generatedRequest<{ items: AiTask[]; next_cursor: string | null }>(() => generatedClient.GET('/api/v1/projects/{project_id}/ai-tasks', { params: { path: { project_id: projectId } } })),
  cancelAiTask: (taskId: string) =>
    generatedRequest<AiTask>(() => generatedClient.POST('/api/v1/ai-tasks/{task_id}/cancel', { params: { path: { task_id: taskId } } })),
}
