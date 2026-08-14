import { defineStore } from 'pinia'

import { api, ensureSession } from '@/services/api'
import type { AiTask, Asset, ExportJob, ImportJob, Profile, Project, Scene, SceneNode } from '@/types'

const POLL_INTERVAL_MS = 350
const POLL_TIMEOUT_MS = 5 * 60 * 1000
const MAX_CONSECUTIVE_POLL_ERRORS = 3

interface StudioState {
  booted: boolean
  profile: Profile | null
  projects: Project[]
  archivedProjects: Project[]
  currentProjectId: string | null
  scene: Scene | null
  nodes: SceneNode[]
  selectedNodeId: string | null
  past: SceneNode[][]
  future: SceneNode[][]
  assets: Asset[]
  activeImportJob: ImportJob | null
  activeExportJob: ExportJob | null
  activeAiTask: AiTask | null
  importing: boolean
  exporting: boolean
  aiProcessing: boolean
  saving: boolean
  exportPreviewHtml: string | null
  activePanel: 'layers' | 'assets'
  loading: boolean
  error: string | null
}

export const useStudioStore = defineStore('studio', {
  state: (): StudioState => ({
    booted: false,
    profile: null,
    projects: [],
    archivedProjects: [],
    currentProjectId: null,
    scene: null,
    nodes: [],
    selectedNodeId: null,
    past: [],
    future: [],
    assets: [],
    activeImportJob: null,
    activeExportJob: null,
    activeAiTask: null,
    importing: false,
    exporting: false,
    aiProcessing: false,
    saving: false,
    exportPreviewHtml: null,
    activePanel: 'layers',
    loading: false,
    error: null,
  }),
  getters: {
    currentProject: (state) => state.projects.find((project) => project.id === state.currentProjectId) ?? null,
    currentAssets: (state) => state.assets,
    selectedNode: (state) => state.nodes.find((node) => node.id === state.selectedNodeId) ?? null,
  },
  actions: {
    async boot() {
      if (this.booted) return
      this.loading = true
      try {
        this.profile = await ensureSession()
        await this.loadProjects()
        this.booted = true
      } catch (error) {
        this.error = toMessage(error)
        this.booted = true
      } finally {
        this.loading = false
      }
    },
    async loadProjects() {
      const [active, archived] = await Promise.all([api.listProjects('active'), api.listProjects('archived')])
      this.projects = active.items
      this.archivedProjects = archived.items
      this.error = null
    },
    async createProject(name: string) {
      this.loading = true
      try {
        const project = await api.createProject({ name })
        this.projects.unshift(project)
        this.error = null
        return project
      } catch (error) {
        this.error = toMessage(error)
        throw error
      } finally {
        this.loading = false
      }
    },
    async renameProject(projectId: string, name: string) {
      this.saving = true
      try {
        const current = this.projects.find((item) => item.id === projectId)
        const project = await api.updateProject(projectId, { name }, current?.version)
        const index = this.projects.findIndex((item) => item.id === projectId)
        if (index >= 0) this.projects[index] = project
        this.error = null
      } catch (error) {
        this.error = toMessage(error)
        throw error
      } finally {
        this.saving = false
      }
    },
    async archiveProject(projectId: string) {
      try {
        const current = this.projects.find((item) => item.id === projectId)
        await api.archiveProject(projectId, current?.version)
        await this.loadProjects()
        if (this.currentProjectId === projectId) this.currentProjectId = null
      } catch (error) {
        this.error = toMessage(error)
        throw error
      }
    },
    async restoreProject(projectId: string) {
      try {
        const current = this.archivedProjects.find((item) => item.id === projectId)
        await api.restoreProject(projectId, current?.version)
        await this.loadProjects()
      } catch (error) {
        this.error = toMessage(error)
        throw error
      }
    },
    async deleteProject(projectId: string) {
      try {
        const current = this.projects.find((item) => item.id === projectId)
        await api.deleteProject(projectId, current?.version)
        await this.loadProjects()
        if (this.currentProjectId === projectId) this.currentProjectId = null
      } catch (error) {
        this.error = toMessage(error)
        throw error
      }
    },
    async openProject(projectId: string) {
      this.loading = true
      this.currentProjectId = null
      this.scene = null
      this.nodes = []
      this.selectedNodeId = null
      this.past = []
      this.future = []
      this.assets = []
      try {
        const [scene, assets] = await Promise.all([api.getScene(projectId), api.listAssets(projectId)])
        const loadedNodes = scene.id ? await api.listNodes(scene.id) : []
        this.currentProjectId = projectId
        this.scene = scene
        this.assets = assets
        this.nodes = loadedNodes
        this.error = null
      } catch (error) {
        this.error = toMessage(error)
        this.currentProjectId = null
      } finally {
        this.loading = false
      }
    },
    async loadAssets(projectId: string) {
      this.assets = await api.listAssets(projectId)
    },
    async addAssetToCanvas(assetId: string) {
      if (!this.currentProjectId || !this.scene) return null
      const asset = this.assets.find((item) => item.id === assetId)
      if (!asset) return null

      const maxWidth = Math.max(160, this.scene.width * 0.6)
      const maxHeight = Math.max(120, this.scene.height * 0.6)
      const sourceWidth = asset.width ?? 320
      const sourceHeight = asset.height ?? 180
      const scale = Math.min(1, maxWidth / sourceWidth, maxHeight / sourceHeight)
      const width = Math.max(1, Math.round(sourceWidth * scale))
      const height = Math.max(1, Math.round(sourceHeight * scale))
      const placementIndex = this.nodes.filter((node) => node.type !== 'root').length
      const x = Math.max(0, Math.round((this.scene.width - width) / 2 + (placementIndex % 5) * 24))
      const y = Math.max(0, Math.round((this.scene.height - height) / 2 + (placementIndex % 5) * 24))

      this.saving = true
      this.error = null
      try {
        const node = await api.createNode(this.currentProjectId, {
          parent_id: this.scene.root_node_id,
          type: 'image',
          name: asset.original_name.replace(/\.[^.]+$/, '') || 'Image',
          asset_id: asset.id,
          transform: { x, y, width, height, rotation: 0, scale_x: 1, scale_y: 1 },
        })
        this.nodes.push(node)
        this.selectedNodeId = node.id
        this.past = []
        this.future = []
        return node
      } catch (error) {
        this.error = toMessage(error)
        throw error
      } finally {
        this.saving = false
      }
    },
    async uploadAsset(projectId: string, file: File) {
      const asset = await api.uploadAsset(projectId, file)
      this.assets.unshift(asset)
      this.error = null
    },
    async deleteAsset(assetId: string) {
      await api.deleteAsset(assetId)
      this.assets = this.assets.filter((asset) => asset.id !== assetId)
    },
    async importSourceAsset(projectId: string, sourceAssetId: string, adapter: 'psd' | 'raster' | 'svg' = 'psd') {
      this.importing = true
      this.error = null
      try {
        this.activeImportJob = await api.createImport(projectId, sourceAssetId, adapter)
        const job = await this.pollImport(this.activeImportJob.id)
        if (job.status === 'succeeded') {
          await this.openProject(projectId)
        } else {
          const message = job.error ?? `Import ${job.status}`
          this.error = message
          throw new Error(message)
        }
      } catch (error) {
        this.error = toMessage(error)
        throw error
      } finally {
        this.importing = false
      }
    },
    async pollImport(importId: string): Promise<ImportJob> {
      return this.pollTask(
        () => api.getImport(importId),
        (job) => {
          this.activeImportJob = job
          return ['succeeded', 'failed', 'cancelled'].includes(job.status)
        },
        'Import',
      )
    },
    async cancelImport() {
      if (!this.activeImportJob || ['succeeded', 'failed', 'cancelled'].includes(this.activeImportJob.status)) return
      this.activeImportJob = await api.cancelImport(this.activeImportJob.id)
    },
    async exportProject(projectId: string) {
      this.exporting = true
      this.error = null
      try {
        this.activeExportJob = await api.createExport(projectId)
        const job = await this.pollExport(this.activeExportJob.id)
        if (job.status !== 'succeeded') {
          const message = job.error ?? `Export ${job.status}`
          this.error = message
          throw new Error(message)
        }
      } catch (error) {
        this.error = toMessage(error)
        throw error
      } finally {
        this.exporting = false
      }
    },
    async pollExport(exportId: string): Promise<ExportJob> {
      return this.pollTask(
        () => api.getExport(exportId),
        (job) => {
          this.activeExportJob = job
          return ['succeeded', 'failed', 'cancelled'].includes(job.status)
        },
        'Export',
      )
    },
    async loadExportPreview(exportId: string) {
      const html = await api.getExportPreview(exportId)
      this.exportPreviewHtml = html
    },
    async downloadExport(exportId: string) {
      const blob = await api.downloadExport(exportId)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `${safeDownloadName(this.currentProject?.name ?? 'ubiqx')}.html5.zip`
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.setTimeout(() => URL.revokeObjectURL(url), 0)
    },
    async runAiTask(projectId: string, inputAssetId: string, operation: 'upscale' | 'remove_background') {
      this.aiProcessing = true
      this.error = null
      try {
        this.activeAiTask = await api.createAiTask(projectId, inputAssetId, operation)
        const task = await this.pollAiTask(this.activeAiTask.id)
        if (task.status === 'succeeded') {
          await this.loadAssets(projectId)
        } else {
          const message = task.last_error ?? `AI task ${task.status}`
          this.error = message
          throw new Error(message)
        }
      } catch (error) {
        this.error = toMessage(error)
        throw error
      } finally {
        this.aiProcessing = false
      }
    },
    async pollAiTask(taskId: string): Promise<AiTask> {
      return this.pollTask(
        () => api.getAiTask(taskId),
        (task) => {
          this.activeAiTask = task
          return ['succeeded', 'failed', 'cancelled'].includes(task.status)
        },
        'AI task',
      )
    },
    async cancelAiTask() {
      if (!this.activeAiTask || ['succeeded', 'failed', 'cancelled'].includes(this.activeAiTask.status)) return
      this.activeAiTask = await api.cancelAiTask(this.activeAiTask.id)
    },
    selectNode(nodeId: string | null) {
      this.selectedNodeId = nodeId
    },
    setActivePanel(panel: 'layers' | 'assets') {
      this.activePanel = panel
    },
    startMutation() {
      this.past.push(cloneNodes(this.nodes))
      if (this.past.length > 50) this.past.shift()
      this.future = []
    },
    updateNodeLocal(nodeId: string, patch: NodePatch) {
      const index = this.nodes.findIndex((node) => node.id === nodeId)
      if (index < 0) return
      this.nodes[index] = Object.assign({}, this.nodes[index], patch)
    },
    async saveNode(nodeId: string, patch: NodePatch) {
      const node = this.nodes.find((item) => item.id === nodeId)
      if (!node || !this.currentProjectId) return
      this.saving = true
      this.error = null
      try {
        const updated = await api.updateNode(node.scene_id, nodeId, patch, node.version)
        this.updateNodeLocal(nodeId, updated)
        const project = await api.updateProject(this.currentProjectId, {}, this.currentProject?.version)
        const projectIndex = this.projects.findIndex((item) => item.id === project.id)
        if (projectIndex >= 0) this.projects[projectIndex] = project
      } catch (error) {
        this.error = toMessage(error)
        throw error
      } finally {
        this.saving = false
      }
    },
    async toggleNodeVisibility(nodeId: string) {
      const node = this.nodes.find((item) => item.id === nodeId)
      if (!node) return
      this.startMutation()
      this.updateNodeLocal(nodeId, { visible: !node.visible })
      await this.saveNode(nodeId, { visible: !node.visible })
    },
    async toggleNodeLocked(nodeId: string) {
      const node = this.nodes.find((item) => item.id === nodeId)
      if (!node) return
      this.startMutation()
      this.updateNodeLocal(nodeId, { locked: !node.locked })
      await this.saveNode(nodeId, { locked: !node.locked })
    },
    async commitNodeProperties(nodeId: string, patch: NodePatch) {
      this.startMutation()
      this.updateNodeLocal(nodeId, patch)
      await this.saveNode(nodeId, patch)
    },
    async undo() {
      if (!this.past.length) return
      const previous = this.past.pop()
      if (!previous) return
      this.future.push(cloneNodes(this.nodes))
      this.nodes = previous
      await this.persistNodes(this.nodes)
    },
    async redo() {
      if (!this.future.length) return
      const next = this.future.pop()
      if (!next) return
      this.past.push(cloneNodes(this.nodes))
      this.nodes = next
      await this.persistNodes(this.nodes)
    },
    async persistNodes(nodes: SceneNode[]) {
      if (!this.currentProjectId) return
      this.saving = true
      try {
        for (const node of nodes) {
          const current = this.nodes.find((item) => item.id === node.id)
          if (!current) continue
          const updated = await api.updateNode(node.scene_id, node.id, {
            name: node.name,
            visible: node.visible,
            locked: node.locked,
            opacity: node.opacity,
            transform: node.transform,
          }, current.version)
          this.updateNodeLocal(node.id, updated)
        }
        const project = await api.updateProject(this.currentProjectId, {}, this.currentProject?.version)
        const projectIndex = this.projects.findIndex((item) => item.id === project.id)
        if (projectIndex >= 0) this.projects[projectIndex] = project
      } catch (error) {
        this.error = toMessage(error)
        throw error
      } finally {
        this.saving = false
      }
    },
    closeExportPreview() {
      this.exportPreviewHtml = null
    },
    closeProject() {
      this.currentProjectId = null
      this.scene = null
      this.nodes = []
      this.selectedNodeId = null
      this.past = []
      this.future = []
      this.assets = []
      this.activeImportJob = null
      this.activeExportJob = null
      this.activeAiTask = null
      this.closeExportPreview()
    },

    async pollTask<T>(
      fetcher: () => Promise<T>,
      observe: (value: T) => boolean,
      label: string,
    ): Promise<T> {
      const deadline = Date.now() + POLL_TIMEOUT_MS
      let consecutiveErrors = 0
      while (Date.now() < deadline) {
        try {
          const value = await fetcher()
          consecutiveErrors = 0
          if (observe(value)) return value
        } catch (error) {
          consecutiveErrors += 1
          if (consecutiveErrors >= MAX_CONSECUTIVE_POLL_ERRORS) throw error
        }
        const remaining = deadline - Date.now()
        if (remaining <= 0) break
        await new Promise((resolve) => window.setTimeout(resolve, Math.min(POLL_INTERVAL_MS, remaining)))
      }
      throw new Error(`${label} polling timed out. Retry the operation or check the job status.`)
    },
  },
})

type NodePatch = Partial<Pick<SceneNode, 'name' | 'visible' | 'locked' | 'opacity' | 'transform'>>

function cloneNodes(nodes: SceneNode[]): SceneNode[] {
  return JSON.parse(JSON.stringify(nodes)) as SceneNode[]
}

function toMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'An unexpected error occurred.'
}

function safeDownloadName(name: string): string {
  const cleaned = name.replace(/[^a-zA-Z0-9._ -]/g, '').trim().replace(/\s+/g, '_')
  return (cleaned || 'ubiqx').slice(0, 120)
}
