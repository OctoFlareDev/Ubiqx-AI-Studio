<script setup lang="ts">
import type { Canvas, CanvasKit } from 'canvaskit-wasm'
import { Layers3, Maximize, Minus, Plus, Redo2, Undo2 } from 'lucide-vue-next'
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'

import { api } from '@/services/api'
import { getCanvasKit } from '@/services/canvaskit'
import { useStudioStore } from '@/stores/studio'
import type { SceneNode } from '@/types'

type SkSurface = NonNullable<ReturnType<CanvasKit['MakeSWCanvasSurface']>>
type SkImage = NonNullable<ReturnType<CanvasKit['MakeImageFromEncoded']>>

interface AbsTransform {
  x: number
  y: number
  width: number
  height: number
}

const studio = useStudioStore()
const viewportRef = ref<HTMLElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasKit = shallowRef<CanvasKit | null>(null)
const surface = shallowRef<SkSurface | null>(null)
const canvasError = ref<string | null>(null)
const zoom = ref(1)
const pan = ref({ x: 0, y: 0 })
const spacePressed = ref(false)
const images = new Map<string, SkImage>()
const absTransforms = new Map<string, AbsTransform>()

let drawQueued = false
let interaction:
  | {
      type: 'move' | 'resize' | 'pan'
      nodeId?: string
      startSceneX: number
      startSceneY: number
      startTransform?: Record<string, number>
      handle?: ResizeHandle
    }
  | null = null

type ResizeHandle = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w'

const scene = computed(() => studio.scene)
const nodes = computed(() => studio.nodes)
const selectedNode = computed(() => studio.selectedNode)
const canUndo = computed(() => studio.past.length > 0)
const canRedo = computed(() => studio.future.length > 0)

watch(
  () => studio.nodes,
  () => {
    void loadImages()
    scheduleDraw()
  },
  { deep: true },
)

watch(
  () => studio.assets,
  () => {
    void loadImages()
  },
  { deep: true },
)

watch(zoom, scheduleDraw)
watch(
  () => pan.value,
  scheduleDraw,
  { deep: true },
)
watch(() => studio.selectedNodeId, scheduleDraw)

onMounted(async () => {
  window.addEventListener('keydown', handleKeyDown)
  window.addEventListener('keyup', handleKeyUp)
  window.addEventListener('resize', resizeCanvas)
  await initCanvasKit()
  resizeCanvas()
  fitView()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('keyup', handleKeyUp)
  window.removeEventListener('resize', resizeCanvas)
  surface.value?.dispose()
  surface.value = null
  for (const image of images.values()) image.delete()
  images.clear()
})

async function initCanvasKit() {
  canvasError.value = null
  try {
    canvasKit.value = await getCanvasKit()
  } catch (error) {
    canvasError.value = error instanceof Error ? error.message : 'CanvasKit failed to load.'
    return
  }
  await loadImages()
  scheduleDraw()
}

function resizeCanvas() {
  const viewport = viewportRef.value
  const canvas = canvasRef.value
  const ck = canvasKit.value
  if (!viewport || !canvas || !ck) return
  const dpr = window.devicePixelRatio || 1
  const width = viewport.clientWidth
  const height = viewport.clientHeight
  canvas.width = Math.max(1, Math.round(width * dpr))
  canvas.height = Math.max(1, Math.round(height * dpr))
  canvas.style.width = `${width}px`
  canvas.style.height = `${height}px`
  surface.value?.dispose()
  surface.value = ck.MakeSWCanvasSurface(canvas)
  scheduleDraw()
}

async function loadImages() {
  const ck = canvasKit.value
  if (!ck) return
  for (const node of nodes.value) {
    if (!node.asset_id || images.has(node.asset_id)) continue
    const asset = studio.assets.find((item) => item.id === node.asset_id)
    if (!asset) continue
    try {
      const blob = await api.getAssetContent(asset.id)
      const bytes = new Uint8Array(await blob.arrayBuffer())
      const image = ck.MakeImageFromEncoded(bytes)
      if (image) images.set(asset.id, image)
    } catch {
      // The node still renders as a placeholder until its image is available.
    }
  }
  scheduleDraw()
}

function scheduleDraw() {
  if (drawQueued) return
  drawQueued = true
  requestAnimationFrame(() => {
    drawQueued = false
    draw()
  })
}

function draw() {
  const ck = canvasKit.value
  const currentSurface = surface.value
  const currentScene = scene.value
  if (!ck || !currentSurface || !currentScene) return

  const canvas = currentSurface.getCanvas()
  canvas.clear(ck.Color(238, 241, 244, 255))
  canvas.save()
  canvas.translate(pan.value.x, pan.value.y)
  canvas.scale(zoom.value, zoom.value)

  drawOriginMarker(canvas)

  absTransforms.clear()
  const rootTransform = { x: 0, y: 0, width: 0, height: 0 }
  const children = childrenOf(currentScene.root_node_id)
  for (const node of children) drawNode(canvas, node, rootTransform)

  const selected = selectedNode.value
  const selectedAbs = selected ? absTransforms.get(selected.id) : null
  if (selected && selectedAbs && !selected.locked) {
    drawSelection(canvas, selectedAbs)
  }

  canvas.restore()
  currentSurface.flush()
}

function childrenOf(parentId: string | null): SceneNode[] {
  return nodes.value
    .filter((node) => node.type !== 'root' && node.parent_id === parentId)
    .sort((a, b) => a.order_index - b.order_index)
}

function drawNode(canvas: Canvas, node: SceneNode, parentAbs: AbsTransform) {
  const ck = canvasKit.value
  if (!ck || !node.visible) return
  const transform = node.transform || {}
  const width = transform.width ?? 0
  const height = transform.height ?? 0
  const abs = {
    x: parentAbs.x + (transform.x ?? 0),
    y: parentAbs.y + (transform.y ?? 0),
    width,
    height,
  }
  absTransforms.set(node.id, abs)

  canvas.save()
  canvas.translate(transform.x ?? 0, transform.y ?? 0)
  if (transform.rotation) canvas.rotate(transform.rotation, 0, 0)
  if (transform.scale_x !== undefined && transform.scale_y !== undefined) {
    canvas.scale(transform.scale_x, transform.scale_y)
  }

  if (node.asset_id && images.has(node.asset_id)) {
    const image = images.get(node.asset_id)
    if (image) {
      const paint = new ck.Paint()
      paint.setAlphaf(node.opacity)
      const source = ck.XYWHRect(0, 0, image.width(), image.height())
      const destination = ck.XYWHRect(0, 0, width, height)
      canvas.drawImageRect(image, source, destination, paint, false)
      paint.delete()
    }
  } else if (node.type === 'text') {
    drawText(canvas, node, width, height)
  } else if (node.type !== 'group') {
    const paint = new ck.Paint()
    paint.setColor(ck.Color(204, 224, 220, 160))
    paint.setAlphaf(node.opacity)
    canvas.drawRect(ck.XYWHRect(0, 0, width, height), paint)
    paint.delete()
  }

  for (const child of childrenOf(node.id)) drawNode(canvas, child, abs)
  canvas.restore()
}

function drawText(canvas: Canvas, node: SceneNode, width: number, height: number) {
  const ck = canvasKit.value
  if (!ck) return
  const props = (node.text_properties ?? {}) as Record<string, unknown>
  const fontSize = Number(props.font_size ?? 14)
  const typeface = ck.Typeface.GetDefault()
  if (!typeface) return
  const font = new ck.Font(typeface, fontSize)
  const paint = new ck.Paint()
  paint.setColor(ck.Color(23, 32, 42, Math.round((node.opacity ?? 1) * 255)))
  const text = String(props.text ?? node.name ?? '')
  canvas.drawText(text, 4, Math.min(fontSize + 4, Math.max(fontSize, height)), paint, font)
  paint.delete()
  font.delete()
  typeface.delete()
}

function drawOriginMarker(canvas: Canvas) {
  const ck = canvasKit.value
  if (!ck) return
  const marker = new ck.Paint()
  marker.setColor(ck.Color(0, 0, 0, 28))
  marker.setStrokeWidth(1 / zoom.value)
  const span = 18 / zoom.value
  canvas.drawLine(-span, 0, span, 0, marker)
  canvas.drawLine(0, -span, 0, span, marker)
  marker.delete()
}

function drawSelection(canvas: Canvas, abs: AbsTransform) {
  const ck = canvasKit.value
  if (!ck) return
  const outline = new ck.Paint()
  outline.setColor(ck.Color(14, 157, 145, 255))
  outline.setStyle(ck.PaintStyle.Stroke)
  outline.setStrokeWidth(1.5 / zoom.value)
  canvas.drawRect(ck.XYWHRect(abs.x, abs.y, abs.width, abs.height), outline)
  outline.delete()

  const fill = new ck.Paint()
  fill.setColor(ck.Color(255, 255, 255, 255))
  const handle = new ck.Paint()
  handle.setColor(ck.Color(14, 157, 145, 255))
  const size = 6 / zoom.value
  const corners: Array<[number, number]> = [
    [abs.x, abs.y],
    [abs.x + abs.width, abs.y],
    [abs.x, abs.y + abs.height],
    [abs.x + abs.width, abs.y + abs.height],
  ]
  for (const [x, y] of corners) {
    canvas.drawRect(ck.XYWHRect(x - size / 2, y - size / 2, size, size), fill)
    canvas.drawRect(ck.XYWHRect(x - size / 2, y - size / 2, size, size), handle)
  }
  fill.delete()
  handle.delete()
}

function toScene(clientX: number, clientY: number) {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return { x: 0, y: 0 }
  return {
    x: (clientX - rect.left - pan.value.x) / zoom.value,
    y: (clientY - rect.top - pan.value.y) / zoom.value,
  }
}

function hitTest(point: { x: number; y: number }) {
  const ordered = nodes.value
    .filter((node) => node.type !== 'root')
    .sort((a, b) => b.order_index - a.order_index)
  for (const node of ordered) {
    const abs = absTransforms.get(node.id)
    if (!abs) continue
    if (
      point.x >= abs.x &&
      point.x <= abs.x + abs.width &&
      point.y >= abs.y &&
      point.y <= abs.y + abs.height
    ) {
      return node
    }
  }
  return null
}

function resizeHandleAt(point: { x: number; y: number }, abs: AbsTransform): ResizeHandle | null {
  const tolerance = 8 / zoom.value
  const near = (a: number, b: number) => Math.abs(a - b) <= tolerance
  const left = near(point.x, abs.x)
  const right = near(point.x, abs.x + abs.width)
  const top = near(point.y, abs.y)
  const bottom = near(point.y, abs.y + abs.height)
  if (left && top) return 'nw'
  if (right && top) return 'ne'
  if (left && bottom) return 'sw'
  if (right && bottom) return 'se'
  if (left) return 'w'
  if (right) return 'e'
  if (top) return 'n'
  if (bottom) return 's'
  return null
}

function onPointerDown(event: PointerEvent) {
  if (event.button === 1 || spacePressed.value) {
    interaction = { type: 'pan', startSceneX: event.clientX, startSceneY: event.clientY }
    event.preventDefault()
    return
  }
  const point = toScene(event.clientX, event.clientY)
  const selectedAbs = selectedNode.value ? absTransforms.get(selectedNode.value.id) : null
  if (selectedNode.value && selectedAbs && !selectedNode.value.locked) {
    const handle = resizeHandleAt(point, selectedAbs)
    if (handle) {
      studio.startMutation()
      interaction = {
        type: 'resize',
        nodeId: selectedNode.value.id,
        startSceneX: point.x,
        startSceneY: point.y,
        startTransform: { ...selectedNode.value.transform },
        handle,
      }
      event.preventDefault()
      return
    }
  }
  const hit = hitTest(point)
  if (hit) {
    studio.selectNode(hit.id)
    studio.startMutation()
    interaction = {
      type: 'move',
      nodeId: hit.id,
      startSceneX: point.x,
      startSceneY: point.y,
      startTransform: { ...hit.transform },
    }
    event.preventDefault()
  } else {
    studio.selectNode(null)
  }
}

function onPointerMove(event: PointerEvent) {
  if (!interaction) return
  const active = interaction
  event.preventDefault()
  if (active.type === 'pan') {
    pan.value = {
      x: pan.value.x + event.movementX,
      y: pan.value.y + event.movementY,
    }
    scheduleDraw()
    return
  }
  if (!active.nodeId || !active.startTransform) return
  const point = toScene(event.clientX, event.clientY)
  const node = nodes.value.find((item) => item.id === active.nodeId)
  if (!node) return
  const next = { ...active.startTransform }
  if (active.type === 'move') {
    next.x = (active.startTransform.x ?? 0) + point.x - active.startSceneX
    next.y = (active.startTransform.y ?? 0) + point.y - active.startSceneY
  } else if (active.handle) {
    applyResize(next, active.handle, point, active.startSceneX, active.startSceneY)
  }
  studio.updateNodeLocal(node.id, { transform: next })
  scheduleDraw()
}

function applyResize(
  transform: Record<string, number>,
  handle: ResizeHandle,
  point: { x: number; y: number },
  startX: number,
  startY: number,
) {
  const startWidth = transform.width ?? 0
  const startHeight = transform.height ?? 0
  const minSize = 4
  const left = handle.includes('w')
  const right = handle.includes('e')
  const top = handle.includes('n')
  const bottom = handle.includes('s')
  const dx = point.x - startX
  const dy = point.y - startY
  if (left) {
    transform.x = (transform.x ?? 0) + dx
    transform.width = Math.max(minSize, startWidth - dx)
  }
  if (right) transform.width = Math.max(minSize, startWidth + dx)
  if (top) {
    transform.y = (transform.y ?? 0) + dy
    transform.height = Math.max(minSize, startHeight - dy)
  }
  if (bottom) transform.height = Math.max(minSize, startHeight + dy)
}

async function onPointerUp() {
  if (!interaction) return
  const current = interaction
  interaction = null
  if ((current.type === 'move' || current.type === 'resize') && current.nodeId) {
    const node = nodes.value.find((item) => item.id === current.nodeId)
    if (node) {
      try {
        await studio.saveNode(node.id, { transform: node.transform })
      } catch {
        // The error is surfaced through the store.
      }
    }
  }
}

function onWheel(event: WheelEvent) {
  event.preventDefault()
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  const factor = event.deltaY < 0 ? 1.12 : 0.9
  const nextZoom = Math.min(8, Math.max(0.1, zoom.value * factor))
  const point = toScene(event.clientX, event.clientY)
  pan.value = {
    x: event.clientX - rect.left - point.x * nextZoom,
    y: event.clientY - rect.top - point.y * nextZoom,
  }
  zoom.value = nextZoom
}

function zoomBy(factor: number) {
  zoom.value = Math.min(8, Math.max(0.1, zoom.value * factor))
}

function computeContentBounds() {
  const rootId = scene.value?.root_node_id ?? null
  const children = new Map<string | null, SceneNode[]>()
  for (const node of nodes.value) {
    if (node.type === 'root') continue
    const key = node.parent_id ?? rootId
    const list = children.get(key) ?? []
    list.push(node)
    children.set(key, list)
  }
  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity
  const walk = (parentId: string | null, px: number, py: number) => {
    for (const node of children.get(parentId) ?? []) {
      const t = node.transform || {}
      const x = px + (t.x ?? 0)
      const y = py + (t.y ?? 0)
      const w = t.width ?? 0
      const h = t.height ?? 0
      if (node.visible !== false) {
        minX = Math.min(minX, x)
        minY = Math.min(minY, y)
        maxX = Math.max(maxX, x + w)
        maxY = Math.max(maxY, y + h)
      }
      walk(node.id, x, y)
    }
  }
  walk(rootId, 0, 0)
  if (!Number.isFinite(minX)) return null
  return { minX, minY, maxX, maxY }
}

function fitView() {
  const viewport = viewportRef.value
  if (!viewport) return
  const bounds = computeContentBounds()
  const fallbackWidth = scene.value?.width ?? 1920
  const fallbackHeight = scene.value?.height ?? 1080
  let width = fallbackWidth
  let height = fallbackHeight
  let centerX = width / 2
  let centerY = height / 2
  if (bounds) {
    width = Math.max(1, bounds.maxX - bounds.minX)
    height = Math.max(1, bounds.maxY - bounds.minY)
    centerX = (bounds.minX + bounds.maxX) / 2
    centerY = (bounds.minY + bounds.maxY) / 2
  }
  zoom.value = Math.min(
    (viewport.clientWidth - 56) / width,
    (viewport.clientHeight - 56) / height,
    1,
  )
  pan.value = {
    x: viewport.clientWidth / 2 - centerX * zoom.value,
    y: viewport.clientHeight / 2 - centerY * zoom.value,
  }
}

function handleKeyDown(event: KeyboardEvent) {
  const target = event.target as HTMLElement | null
  if (target?.matches?.('input, textarea, select')) return
  if (event.code === 'Space') {
    spacePressed.value = true
    event.preventDefault()
  }
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'z') {
    event.preventDefault()
    if (event.shiftKey) void studio.redo()
    else void studio.undo()
  }
  if (event.key === 'Escape') studio.selectNode(null)
}

function handleKeyUp(event: KeyboardEvent) {
  if (event.code === 'Space') spacePressed.value = false
}
</script>

<template>
  <div class="scene-canvas">
    <div class="canvas-toolbar">
      <button
        class="icon-button"
        type="button"
        aria-label="Undo"
        title="Undo"
        :disabled="!canUndo"
        @click="studio.undo()"
      >
        <Undo2 :size="16" />
      </button>
      <button
        class="icon-button"
        type="button"
        aria-label="Redo"
        title="Redo"
        :disabled="!canRedo"
        @click="studio.redo()"
      >
        <Redo2 :size="16" />
      </button>
      <span class="toolbar-divider" />
      <button class="icon-button" type="button" aria-label="Zoom out" title="Zoom out" @click="zoomBy(0.8)">
        <Minus :size="16" />
      </button>
      <span class="zoom-label">{{ Math.round(zoom * 100) }}%</span>
      <button class="icon-button" type="button" aria-label="Zoom in" title="Zoom in" @click="zoomBy(1.25)">
        <Plus :size="16" />
      </button>
      <button class="icon-button" type="button" aria-label="Fit view" title="Fit view" @click="fitView">
        <Maximize :size="15" />
      </button>
    </div>
    <div
      ref="viewportRef"
      class="canvas-viewport"
      :data-zoom="zoom"
      :data-pan-x="pan.x"
      :data-pan-y="pan.y"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @wheel="onWheel"
    >
      <canvas ref="canvasRef" data-testid="canvaskit-canvas" />
      <div v-if="canvasError" class="canvas-fallback">
        <Layers3 :size="22" />
        <span>{{ canvasError }}</span>
      </div>
    </div>
  </div>
</template>
