import { defineStore } from 'pinia'

import { api, ensureSession } from '@/services/api'
import type { AiTask, Asset, ExportJob, ImportJob, Profile, Project, Scene, SceneNode } from '@/types'

interface StudioState {
  booted: boolean
  profile: Profile | null
  projects: Project[]
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
  exportPreviewUrl: string | null
  activePanel: 'layers' | 'assets'
  loading: boolean
  error: string | null
}

export const useStudioStore = defineStore('studio', {
  state: (): StudioState => ({
    booted: false,
    profile: null,
    projects: [],
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
    exportPreviewUrl: null,
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
      const result = await api.listProjects()
      this.projects = result.items
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
      const project = await api.updateProject(projectId, { name })
      const index = this.projects.findIndex((item) => item.id === projectId)
      if (index >= 0) this.projects[index] = project
      this.error = null
    },
    async archiveProject(projectId: string) {
      await api.archiveProject(projectId)
      await this.loadProjects()
      if (this.currentProjectId === projectId) this.currentProjectId = null
    },
    async restoreProject(projectId: string) {
      await api.restoreProject(projectId)
      await this.loadProjects()
    },
    async deleteProject(projectId: string) {
      await api.deleteProject(projectId)
      await this.loadProjects()
      if (this.currentProjectId === projectId) this.currentProjectId = null
    },
    async openProject(projectId: string) {
      this.currentProjectId = projectId
      this.scene = null
      this.nodes = []
      this.selectedNodeId = null
      this.past = []
      this.future = []
      this.assets = []
      try {
        const [scene, assets] = await Promise.all([api.getScene(projectId), api.listAssets(projectId)])
        this.scene = scene
        this.assets = assets
        if (scene.id) this.nodes = await api.listNodes(scene.id)
        this.error = null
      } catch (error) {
        this.error = toMessage(error)
      }
    },
    async loadAssets(projectId: string) {
      this.assets = await api.listAssets(projectId)
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
    async importSourceAsset(projectId: string, sourceAssetId: string) {
      this.importing = true
      this.error = null
      try {
        this.activeImportJob = await api.createImport(projectId, sourceAssetId)
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
      while (true) {
        const job = await api.getImport(importId)
        this.activeImportJob = job
        if (['succeeded', 'failed', 'cancelled'].includes(job.status)) return job
        await new Promise((resolve) => window.setTimeout(resolve, 350))
      }
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
      while (true) {
        const job = await api.getExport(exportId)
        this.activeExportJob = job
        if (['succeeded', 'failed', 'cancelled'].includes(job.status)) return job
        await new Promise((resolve) => window.setTimeout(resolve, 350))
      }
    },
    async loadExportPreview(exportId: string) {
      const html = await api.getExportPreview(exportId)
      if (this.exportPreviewUrl) URL.revokeObjectURL(this.exportPreviewUrl)
      this.exportPreviewUrl = URL.createObjectURL(new Blob([html], { type: 'text/html' }))
    },
    async downloadExport(exportId: string) {
      const blob = await api.downloadExport(exportId)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `ubiqx-html5-export.zip`
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
      while (true) {
        const task = await api.getAiTask(taskId)
        this.activeAiTask = task
        if (['succeeded', 'failed', 'cancelled'].includes(task.status)) return task
        await new Promise((resolve) => window.setTimeout(resolve, 350))
      }
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
        const updated = await api.updateNode(node.scene_id, nodeId, patch)
        this.updateNodeLocal(nodeId, updated)
        await api.updateProject(this.currentProjectId, {})
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
          await api.updateNode(node.scene_id, node.id, {
            name: node.name,
            visible: node.visible,
            locked: node.locked,
            opacity: node.opacity,
            transform: node.transform,
          })
        }
        await api.updateProject(this.currentProjectId, {})
      } catch (error) {
        this.error = toMessage(error)
        throw error
      } finally {
        this.saving = false
      }
    },
    closeExportPreview() {
      if (this.exportPreviewUrl) URL.revokeObjectURL(this.exportPreviewUrl)
      this.exportPreviewUrl = null
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
