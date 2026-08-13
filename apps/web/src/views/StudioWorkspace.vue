<script setup lang="ts">
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  Download,
  Eye,
  FileArchive,
  FileImage,
  Layers3,
  Pencil,
  Plus,
  Trash2,
  Upload,
  X,
} from 'lucide-vue-next'
import { computed, onMounted, ref, watch } from 'vue'

import { useStudioStore } from '@/stores/studio'
import type { Asset } from '@/types'

const studio = useStudioStore()
const project = computed(() => studio.currentProject)
const editingName = ref(false)
const nameDraft = ref('')
const activePanel = ref<'layers' | 'assets'>('layers')
const fileInput = ref<HTMLInputElement | null>(null)
const selectedAssetId = ref<string | null>(null)
const saveState = ref<'idle' | 'saving' | 'saved'>('saved')
const exportError = ref<string | null>(null)

const selectedAsset = computed<Asset | null>(
  () => studio.assets.find((asset) => asset.id === selectedAssetId.value) ?? null,
)
const selectedAssetIsPhotoshop = computed(() => selectedAsset.value?.media_type === 'image/vnd.adobe.photoshop')
const hasExportableNodes = computed(() => studio.nodes.some((node) => node.type !== 'root'))

watch(
  () => project.value?.name,
  (name) => {
    if (!editingName.value) nameDraft.value = name ?? ''
  },
  { immediate: true },
)

onMounted(async () => {
  if (project.value?.id) await studio.openProject(project.value.id)
})

function startRename() {
  if (!project.value) return
  nameDraft.value = project.value.name
  editingName.value = true
}

async function saveName() {
  if (!project.value || !nameDraft.value.trim()) {
    editingName.value = false
    return
  }
  saveState.value = 'saving'
  await studio.renameProject(project.value.id, nameDraft.value.trim())
  editingName.value = false
  saveState.value = 'saved'
}

async function saveProject() {
  if (!project.value) return
  saveState.value = 'saving'
  await studio.renameProject(project.value.id, project.value.name)
  saveState.value = 'saved'
}

function triggerUpload() {
  fileInput.value?.click()
}

async function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !project.value) return
  await studio.uploadAsset(project.value.id, file)
  input.value = ''
}

async function removeSelectedAsset() {
  if (!selectedAsset.value) return
  await studio.deleteAsset(selectedAsset.value.id)
  selectedAssetId.value = null
}

async function importSelectedAsset() {
  if (!project.value || !selectedAsset.value) return
  await studio.importSourceAsset(project.value.id, selectedAsset.value.id)
}

function cancelImport() {
  void studio.cancelImport()
}

async function exportProject() {
  if (!project.value) return
  exportError.value = null
  if (!hasExportableNodes.value) {
    exportError.value = 'No layers to export. Import a PSD or PSB asset as a scene first.'
    return
  }
  try {
    await studio.exportProject(project.value.id)
  } catch {
    exportError.value = studio.error
  }
}

async function previewExport() {
  if (!studio.activeExportJob) return
  await studio.loadExportPreview(studio.activeExportJob.id)
}

async function downloadExport() {
  if (!studio.activeExportJob) return
  await studio.downloadExport(studio.activeExportJob.id)
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function nodeStyle(node: { transform: Record<string, number>; opacity: number; visible: boolean }) {
  const transform = node.transform
  return {
    left: `${transform.x ?? 0}px`,
    top: `${transform.y ?? 0}px`,
    width: `${transform.width ?? 100}px`,
    height: `${transform.height ?? 100}px`,
    opacity: `${node.opacity ?? 1}`,
    display: node.visible ? 'block' : 'none',
  }
}
</script>

<template>
  <div v-if="project" class="studio-workspace">
    <header class="studio-topbar">
      <button class="icon-button" type="button" aria-label="Back to projects" title="Back to projects" @click="studio.closeProject">
        <ArrowLeft :size="18" />
      </button>
      <div class="project-title">
        <template v-if="editingName">
          <input v-model="nameDraft" type="text" aria-label="Project name" @keyup.enter="saveName" />
          <button class="icon-button" type="button" aria-label="Save project name" @click="saveName">
            <Check :size="16" />
          </button>
        </template>
        <template v-else>
          <h2>{{ project.name }}</h2>
          <button class="icon-button subtle" type="button" aria-label="Rename project" title="Rename" @click="startRename">
            <Pencil :size="14" />
          </button>
        </template>
        <span class="save-state" :class="saveState">{{ saveState }}</span>
      </div>

      <div class="topbar-actions">
        <button class="secondary-button" type="button" @click="triggerUpload">
          <Upload :size="16" />
          Import
        </button>
        <button
          class="primary-button"
          type="button"
          :disabled="studio.exporting"
          :title="hasExportableNodes ? 'Export HTML5 package' : 'No layers to export'"
          @click="exportProject"
        >
          <Download :size="16" />
          {{ studio.exporting ? 'Exporting' : 'Export' }}
        </button>
      </div>
    </header>

    <div v-if="exportError" class="studio-status-banner error" role="alert">
      <AlertTriangle :size="16" />
      <span>{{ exportError }}</span>
      <button class="icon-button subtle" type="button" aria-label="Dismiss export message" @click="exportError = null">
        <X :size="14" />
      </button>
    </div>

    <div class="studio-body">
      <aside class="left-panel">
        <div class="panel-tabs">
          <button type="button" :class="{ active: activePanel === 'layers' }" @click="activePanel = 'layers'">
            <Layers3 :size="16" />
            Layers
          </button>
          <button type="button" :class="{ active: activePanel === 'assets' }" @click="activePanel = 'assets'">
            <FileImage :size="16" />
            Assets
          </button>
        </div>

        <div v-if="activePanel === 'layers'" class="panel-content">
          <div v-if="studio.nodes.length" class="layer-list">
            <div v-for="node in studio.nodes" :key="node.id" class="layer-row">
              <Layers3 :size="15" />
              <span>{{ node.name }}</span>
            </div>
          </div>
          <div v-else class="panel-empty">
            <Layers3 :size="20" />
            <span>No layers</span>
          </div>
        </div>

        <div v-else class="panel-content">
          <div class="panel-heading">
            <span>Project assets</span>
            <button class="icon-button" type="button" aria-label="Import asset" title="Import asset" @click="triggerUpload">
              <Plus :size="16" />
            </button>
          </div>
          <div v-if="studio.assets.length" class="asset-list">
            <button
              v-for="asset in studio.assets"
              :key="asset.id"
              class="asset-row"
              :class="{ selected: selectedAssetId === asset.id }"
              type="button"
              @click="selectedAssetId = asset.id"
            >
              <FileImage :size="16" />
              <span class="asset-name">{{ asset.original_name }}</span>
              <span class="asset-size">{{ formatBytes(asset.byte_size) }}</span>
            </button>
          </div>
          <div v-else class="panel-empty">
            <FileImage :size="20" />
            <span>No assets</span>
          </div>
        </div>
      </aside>

      <section class="canvas-panel" data-testid="studio-canvas">
        <div v-if="studio.scene" class="canvas-stage" :style="{ aspectRatio: `${studio.scene.width} / ${studio.scene.height}` }">
          <div v-for="node in studio.nodes.filter((item) => item.type !== 'root')" :key="node.id" class="canvas-node" :style="nodeStyle(node)">
            <span>{{ node.name }}</span>
          </div>
        </div>
        <div v-else class="canvas-panel-empty" />
      </section>

      <aside class="right-panel">
        <div class="properties-header">
          <span>Properties</span>
          <button class="secondary-button compact" type="button" @click="saveProject">Save</button>
        </div>
        <div class="property-group">
          <label>Project</label>
          <p>{{ project.name }}</p>
        </div>
        <div v-if="studio.scene" class="property-group">
          <label>Canvas</label>
          <p>{{ studio.scene.width }} x {{ studio.scene.height }}</p>
        </div>
        <div v-if="studio.activeExportJob || studio.exporting" class="property-group export-properties">
          <label>HTML5 export</label>
          <div class="export-status-row">
            <FileArchive :size="15" />
            <span>{{ studio.exporting ? 'Preparing package' : studio.activeExportJob?.status }}</span>
          </div>
          <dl v-if="studio.activeExportJob?.status === 'succeeded'" class="export-summary">
            <dt>Nodes</dt>
            <dd>{{ studio.activeExportJob.manifest.validation?.node_count ?? 0 }}</dd>
            <dt>Assets</dt>
            <dd>{{ studio.activeExportJob.manifest.validation?.asset_count ?? 0 }}</dd>
            <dt>Warnings</dt>
            <dd>{{ studio.activeExportJob.manifest.validation?.warning_count ?? 0 }}</dd>
          </dl>
          <div v-if="studio.activeExportJob?.warnings.length" class="export-warnings">
            <AlertTriangle :size="14" />
            <span>{{ studio.activeExportJob.warnings.length }} warning report item{{ studio.activeExportJob.warnings.length === 1 ? '' : 's' }}</span>
          </div>
          <div v-if="studio.activeExportJob?.status === 'succeeded'" class="import-action">
            <button class="secondary-button compact-action" type="button" @click="previewExport">
              <Eye :size="15" />
              Preview
            </button>
            <button class="primary-button compact-action" type="button" @click="downloadExport">
              <Download :size="15" />
              Download
            </button>
          </div>
          <p v-if="studio.activeExportJob?.status === 'failed'" class="import-error">{{ studio.error }}</p>
        </div>
        <div v-if="selectedAsset" class="property-group asset-properties">
          <label>Asset</label>
          <h3>{{ selectedAsset.original_name }}</h3>
          <dl>
            <dt>Type</dt>
            <dd>{{ selectedAsset.media_type }}</dd>
            <dt>Size</dt>
            <dd>{{ formatBytes(selectedAsset.byte_size) }}</dd>
            <dt>Hash</dt>
            <dd class="hash">{{ selectedAsset.content_hash.slice(0, 14) }}</dd>
          </dl>
          <button class="icon-button danger" type="button" aria-label="Remove asset reference" title="Remove asset reference" @click="removeSelectedAsset">
            <Trash2 :size="15" />
          </button>
          <div v-if="selectedAssetIsPhotoshop" class="import-action">
            <button
              class="primary-button compact-action"
              type="button"
              :disabled="studio.importing"
              @click="importSelectedAsset"
            >
              <Layers3 :size="15" />
              {{ studio.importing ? 'Importing' : 'Import as scene' }}
            </button>
            <button
              v-if="studio.importing && studio.activeImportJob"
              class="secondary-button compact-action"
              type="button"
              @click="cancelImport"
            >
              Cancel
            </button>
          </div>
          <p v-if="studio.activeImportJob?.status === 'failed'" class="import-error">{{ studio.error }}</p>
        </div>
        <div v-else class="property-group">
          <label>Selection</label>
          <p>Nothing selected</p>
        </div>
      </aside>
    </div>

    <input ref="fileInput" class="visually-hidden" type="file" accept=".psd,.psb,.png,.jpg,.jpeg,.webp,.svg" @change="onFileSelected" />

    <div v-if="studio.exportPreviewUrl" class="preview-modal-backdrop" @click.self="studio.closeExportPreview">
      <section class="preview-modal" role="dialog" aria-modal="true" aria-label="HTML5 export preview">
        <header class="preview-modal-header">
          <div>
            <p class="eyebrow">M3 package preview</p>
            <h3>{{ project.name }}</h3>
          </div>
          <button class="icon-button" type="button" aria-label="Close export preview" title="Close preview" @click="studio.closeExportPreview">
            <X :size="18" />
          </button>
        </header>
        <iframe :src="studio.exportPreviewUrl" title="HTML5 export preview" />
      </section>
    </div>
  </div>
</template>
