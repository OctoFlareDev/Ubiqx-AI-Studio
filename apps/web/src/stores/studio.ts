import { defineStore } from 'pinia'

import { api, ensureSession } from '@/services/api'
import type { Asset, ImportJob, Profile, Project, Scene, SceneNode } from '@/types'

interface StudioState {
  booted: boolean
  profile: Profile | null
  projects: Project[]
  currentProjectId: string | null
  scene: Scene | null
  nodes: SceneNode[]
  assets: Asset[]
  activeImportJob: ImportJob | null
  importing: boolean
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
    assets: [],
    activeImportJob: null,
    importing: false,
    loading: false,
    error: null,
  }),
  getters: {
    currentProject: (state) => state.projects.find((project) => project.id === state.currentProjectId) ?? null,
    currentAssets: (state) => state.assets,
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
    closeProject() {
      this.currentProjectId = null
      this.scene = null
      this.nodes = []
      this.assets = []
    },
  },
})

function toMessage(error: unknown): string {
  if (error instanceof Error) return error.message
  return 'An unexpected error occurred.'
}
