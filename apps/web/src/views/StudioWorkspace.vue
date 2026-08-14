<script setup lang="ts">
import {
  AlertTriangle,
  ArrowLeft,
  Check,
  Download,
  Eye,
  EyeOff,
  FileArchive,
  FileImage,
  Layers3,
  Lock,
  LockOpen,
  Maximize2,
  Pencil,
  Plus,
  Scissors,
  Trash2,
  Upload,
  X,
} from 'lucide-vue-next'
import { computed, nextTick, ref, watch } from 'vue'

import { useStudioStore } from '@/stores/studio'
import type { Asset, SceneNode } from '@/types'
import SceneCanvas from '@/components/SceneCanvas.vue'

const studio = useStudioStore()
const project = computed(() => studio.currentProject)
const editingName = ref(false)
const nameDraft = ref('')
const fileInput = ref<HTMLInputElement | null>(null)
const selectedAssetId = ref<string | null>(null)
const saveState = ref<'idle' | 'saving' | 'saved'>('saved')
const exportError = ref<string | null>(null)
const previewCloseButton = ref<HTMLButtonElement | null>(null)
let previewReturnFocus: HTMLElement | null = null

const selectedAsset = computed<Asset | null>(
  () => studio.assets.find((asset) => asset.id === selectedAssetId.value) ?? null,
)
const selectedAssetIsPhotoshop = computed(() => selectedAsset.value?.media_type === 'image/vnd.adobe.photoshop')
const selectedAssetIsRaster = computed(() =>
  selectedAsset.value ? ['image/png', 'image/jpeg', 'image/webp'].includes(selectedAsset.value.media_type) : false,
)
const selectedAssetIsSvg = computed(() => selectedAsset.value?.media_type === 'image/svg+xml')
const selectedAssetIsImportable = computed(() => selectedAssetIsPhotoshop.value || selectedAssetIsRaster.value || selectedAssetIsSvg.value)
const selectedAssetImportAdapter = computed<'psd' | 'raster' | 'svg'>(() => {
  if (selectedAssetIsPhotoshop.value) return 'psd'
  if (selectedAssetIsSvg.value) return 'svg'
  return 'raster'
})
const hasExportableNodes = computed(() => studio.nodes.some((node) => node.type !== 'root'))
const layerRows = computed(() => {
  const rows: Array<{ node: SceneNode; depth: number }> = []
  const walk = (parentId: string | null, depth: number) => {
    const children = studio.nodes
      .filter((node) => node.type !== 'root' && node.parent_id === parentId)
      .sort((a, b) => a.order_index - b.order_index)
    for (const child of children) {
      rows.push({ node: child, depth })
      walk(child.id, depth + 1)
    }
  }
  walk(studio.scene?.root_node_id ?? null, 0)
  return rows
})

watch(
  () => project.value?.name,
  (name) => {
    if (!editingName.value) nameDraft.value = name ?? ''
  },
  { immediate: true },
)

watch(
  () => studio.exportPreviewHtml,
  async (html) => {
    if (html) {
      previewReturnFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null
      await nextTick()
      previewCloseButton.value?.focus()
      return
    }
    previewReturnFocus?.focus()
    previewReturnFocus = null
  },
)

function startRename() {
  if (!project.value) return
  nameDraft.value = project.value.name
  editingName.value = true
}

function handleActionError(error: unknown) {
  studio.error = error instanceof Error ? error.message : 'An unexpected error occurred.'
}

async function runAction(action: () => Promise<unknown>) {
  try {
    await action()
  } catch (error) {
    handleActionError(error)
  }
}

async function saveName() {
  if (!project.value || !nameDraft.value.trim()) {
    editingName.value = false
    return
  }
  saveState.value = 'saving'
  try {
    await studio.renameProject(project.value.id, nameDraft.value.trim())
    editingName.value = false
    saveState.value = 'saved'
  } catch (error) {
    saveState.value = 'idle'
    handleActionError(error)
  }
}

async function saveProject() {
  if (!project.value) return
  saveState.value = 'saving'
  let saved = false
  await runAction(async () => {
    await studio.renameProject(project.value!.id, project.value!.name)
    saved = true
  })
  saveState.value = saved ? 'saved' : 'idle'
}

function triggerUpload() {
  fileInput.value?.click()
}

async function onFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file || !project.value) return
  await runAction(() => studio.uploadAsset(project.value!.id, file))
  input.value = ''
}

async function removeSelectedAsset() {
  if (!selectedAsset.value) return
  if (!window.confirm(`Delete ${selectedAsset.value.original_name} from this project?`)) return
  const assetId = selectedAsset.value.id
  await runAction(async () => {
    await studio.deleteAsset(assetId)
    selectedAssetId.value = null
  })
}

async function importSelectedAsset() {
  if (!project.value || !selectedAsset.value) return
  await runAction(() => studio.importSourceAsset(project.value!.id, selectedAsset.value!.id, selectedAssetImportAdapter.value))
}

function cancelImport() {
  void runAction(() => studio.cancelImport())
}

async function runAiTask(operation: 'upscale' | 'remove_background') {
  if (!project.value || !selectedAsset.value) return
  await runAction(() => studio.runAiTask(project.value!.id, selectedAsset.value!.id, operation))
}

async function addSelectedAssetToCanvas() {
  if (!selectedAsset.value) return
  await runAction(async () => {
    const node = await studio.addAssetToCanvas(selectedAsset.value!.id)
    if (node) selectedAssetId.value = null
  })
}

function cancelAiTask() {
  void runAction(() => studio.cancelAiTask())
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
  await runAction(() => studio.loadExportPreview(studio.activeExportJob!.id))
}

async function downloadExport() {
  if (!studio.activeExportJob) return
  await runAction(() => studio.downloadExport(studio.activeExportJob!.id))
}

function selectLayer(node: SceneNode) {
  selectedAssetId.value = null
  studio.selectNode(node.id)
}

function selectAsset(assetId: string) {
  selectedAssetId.value = assetId
  studio.selectNode(null)
}

async function toggleLayerVisible(node: SceneNode) {
  await runAction(() => studio.toggleNodeVisibility(node.id))
}

async function toggleLayerLocked(node: SceneNode) {
  await runAction(() => studio.toggleNodeLocked(node.id))
}

function commitSelectedName(event: Event) {
  const node = studio.selectedNode
  if (!node) return
  const value = (event.target as HTMLInputElement).value.trim()
  if (!value) return
  void runAction(() => studio.commitNodeProperties(node.id, { name: value }))
}

function commitSelectedNumber(event: Event, field: 'opacity' | 'x' | 'y' | 'width' | 'height' | 'rotation') {
  const node = studio.selectedNode
  if (!node) return
  const value = Number((event.target as HTMLInputElement).value)
  if (!Number.isFinite(value)) return
  const patch =
    field === 'opacity'
      ? { opacity: Math.min(1, Math.max(0, value)) }
      : { transform: { ...node.transform, [field]: value } }
  void runAction(() => studio.commitNodeProperties(node.id, patch))
}

function previewSelectedOpacity(event: Event) {
  const node = studio.selectedNode
  if (!node) return
  const value = Number((event.target as HTMLInputElement).value)
  if (!Number.isFinite(value)) return
  studio.updateNodeLocal(node.id, { opacity: Math.min(1, Math.max(0, value)) })
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`
  return `${(value / (1024 * 1024)).toFixed(1)} MB`
}

function handlePreviewKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    event.preventDefault()
    studio.closeExportPreview()
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

    <div v-if="studio.error && !exportError" class="studio-status-banner error" role="alert">
      <AlertTriangle :size="16" />
      <span>{{ studio.error }}</span>
      <button class="icon-button subtle" type="button" aria-label="Dismiss message" @click="studio.error = null">
        <X :size="14" />
      </button>
    </div>

    <div class="studio-body">
      <aside class="left-panel">
        <div class="panel-tabs">
          <button type="button" :class="{ active: studio.activePanel === 'layers' }" @click="studio.setActivePanel('layers')">
            <Layers3 :size="16" />
            Layers
          </button>
          <button type="button" :class="{ active: studio.activePanel === 'assets' }" @click="studio.setActivePanel('assets')">
            <FileImage :size="16" />
            Assets
          </button>
        </div>

        <div v-if="studio.activePanel === 'layers'" class="panel-content">
          <div v-if="layerRows.length" class="layer-list">
            <div
              v-for="row in layerRows"
              :key="row.node.id"
              class="layer-row"
              :class="{ selected: studio.selectedNodeId === row.node.id }"
              :style="{ paddingLeft: `${10 + row.depth * 14}px` }"
              role="button"
              tabindex="0"
              :aria-label="`Select layer ${row.node.name}`"
              @click="selectLayer(row.node)"
              @keydown.enter="selectLayer(row.node)"
              @keydown.space.prevent="selectLayer(row.node)"
            >
              <button
                class="icon-button layer-toggle"
                type="button"
                :aria-label="row.node.visible ? 'Hide layer' : 'Show layer'"
                :title="row.node.visible ? 'Hide layer' : 'Show layer'"
                @click.stop="toggleLayerVisible(row.node)"
              >
                <Eye v-if="row.node.visible" :size="14" />
                <EyeOff v-else :size="14" />
              </button>
              <button
                class="icon-button layer-toggle"
                type="button"
                :aria-label="row.node.locked ? 'Unlock layer' : 'Lock layer'"
                :title="row.node.locked ? 'Unlock layer' : 'Lock layer'"
                @click.stop="toggleLayerLocked(row.node)"
              >
                <LockOpen v-if="row.node.locked" :size="14" />
                <Lock v-else :size="14" />
              </button>
              <Layers3 :size="14" />
              <span class="layer-name">{{ row.node.name }}</span>
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
              @click="selectAsset(asset.id)"
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
        <SceneCanvas v-if="studio.scene && hasExportableNodes" />
        <div v-else-if="studio.scene" class="canvas-empty-state">
          <span class="empty-icon"><Upload :size="28" /></span>
          <h3>Start your scene</h3>
          <p>Import a PSD, PSB, or image asset to begin building the canvas.</p>
          <div class="canvas-empty-actions">
            <button class="primary-button" type="button" @click="triggerUpload">
              <Upload :size="16" />
              Import design
            </button>
            <button class="secondary-button" type="button" @click="studio.setActivePanel('assets')">
              <FileImage :size="16" />
              Open assets
            </button>
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
        <div v-if="studio.selectedNode" class="property-group node-properties">
          <label>Layer</label>
          <input class="property-input" type="text" :value="studio.selectedNode.name" aria-label="Layer name" @change="commitSelectedName" />
          <dl>
            <dt>Type</dt>
            <dd>{{ studio.selectedNode.type }}</dd>
            <dt>Visible</dt>
            <dd>
              <input type="checkbox" :checked="studio.selectedNode.visible" @change="toggleLayerVisible(studio.selectedNode)" />
            </dd>
            <dt>Locked</dt>
            <dd>
              <input type="checkbox" :checked="studio.selectedNode.locked" @change="toggleLayerLocked(studio.selectedNode)" />
            </dd>
          </dl>
          <div class="property-field">
            <label for="node-x">X</label>
            <input id="node-x" class="property-input" type="number" :value="studio.selectedNode.transform.x ?? 0" @change="commitSelectedNumber($event, 'x')" />
            <label for="node-y">Y</label>
            <input id="node-y" class="property-input" type="number" :value="studio.selectedNode.transform.y ?? 0" @change="commitSelectedNumber($event, 'y')" />
          </div>
          <div class="property-field">
            <label for="node-width">W</label>
            <input id="node-width" class="property-input" type="number" :value="studio.selectedNode.transform.width ?? 0" @change="commitSelectedNumber($event, 'width')" />
            <label for="node-height">H</label>
            <input id="node-height" class="property-input" type="number" :value="studio.selectedNode.transform.height ?? 0" @change="commitSelectedNumber($event, 'height')" />
          </div>
          <div class="property-field rotation-opacity-field">
            <label for="node-rotation">Rot</label>
            <input id="node-rotation" class="property-input" type="number" :value="studio.selectedNode.transform.rotation ?? 0" @change="commitSelectedNumber($event, 'rotation')" />
            <label for="node-opacity">Opacity</label>
            <input
              id="node-opacity"
              class="property-input opacity-input"
              type="range"
              min="0"
              max="1"
              step="0.01"
              :value="studio.selectedNode.opacity"
              @input="previewSelectedOpacity"
              @change="commitSelectedNumber($event, 'opacity')"
            />
            <span class="property-value">{{ Math.round((studio.selectedNode.opacity ?? 1) * 100) }}%</span>
          </div>
        </div>
        <div v-else-if="selectedAsset" class="property-group asset-properties">
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
          <button class="icon-button danger" type="button" aria-label="Delete asset" title="Delete asset" @click="removeSelectedAsset">
            <Trash2 :size="15" />
          </button>
          <div v-if="selectedAssetIsRaster" class="ai-action">
            <button
              class="secondary-button compact-action"
              type="button"
              :disabled="studio.aiProcessing"
              @click="runAiTask('upscale')"
            >
              <Maximize2 :size="15" />
              Upscale
            </button>
            <button
              class="secondary-button compact-action"
              type="button"
              :disabled="studio.aiProcessing"
              @click="runAiTask('remove_background')"
            >
              <Scissors :size="15" />
              Remove background
            </button>
          </div>
          <button class="primary-button compact-action" type="button" @click="addSelectedAssetToCanvas">
            <Plus :size="15" />
            Add to canvas
          </button>
          <div v-if="studio.activeAiTask && studio.activeAiTask.input_asset_id === selectedAsset.id" class="ai-task-status">
            <span>{{ studio.aiProcessing ? 'Processing' : studio.activeAiTask.status }}</span>
            <span v-if="studio.activeAiTask.status === 'running' || studio.activeAiTask.status === 'queued'">
              {{ Math.round(studio.activeAiTask.progress * 100) }}%
            </span>
            <button
              v-if="studio.activeAiTask.status === 'running' || studio.activeAiTask.status === 'queued'"
              class="secondary-button compact-action"
              type="button"
              @click="cancelAiTask"
            >
              Cancel
            </button>
          </div>
          <div v-if="selectedAssetIsImportable" class="import-action">
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
          <p v-if="studio.activeAiTask?.status === 'failed' && studio.activeAiTask.input_asset_id === selectedAsset.id" class="import-error">
            {{ studio.error }}
          </p>
          <p v-if="studio.activeImportJob?.status === 'failed'" class="import-error">{{ studio.error }}</p>
        </div>
        <div v-else class="property-group">
          <label>Selection</label>
          <p>Nothing selected</p>
        </div>
      </aside>
    </div>

    <input ref="fileInput" class="visually-hidden" type="file" accept=".psd,.psb,.png,.jpg,.jpeg,.webp,.svg" @change="onFileSelected" />

    <div v-if="studio.exportPreviewHtml" class="preview-modal-backdrop" @click.self="studio.closeExportPreview">
      <section
        class="preview-modal"
        role="dialog"
        aria-modal="true"
        aria-label="HTML5 export preview"
        tabindex="-1"
        @keydown="handlePreviewKeydown"
      >
        <header class="preview-modal-header">
          <div>
            <p class="eyebrow">M3 package preview</p>
            <h3>{{ project.name }}</h3>
          </div>
          <button
            ref="previewCloseButton"
            class="icon-button"
            type="button"
            aria-label="Close export preview"
            title="Close preview"
            @click="studio.closeExportPreview"
          >
            <X :size="18" />
          </button>
        </header>
        <iframe :srcdoc="studio.exportPreviewHtml" title="HTML5 export preview" />
      </section>
    </div>
  </div>
</template>
