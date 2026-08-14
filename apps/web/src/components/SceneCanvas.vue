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

type Matrix = [number, number, number, number, number, number]

interface Point {
  x: number
  y: number
}

interface AbsTransform {
  matrix: Matrix
  inverse: Matrix
  parentMatrix: Matrix
  corners: [Point, Point, Point, Point]
  width: number
  height: number
}

const studio = useStudioStore()
const viewportRef = ref<HTMLElement | null>(null)
const canvasRef = ref<HTMLCanvasElement | null>(null)
const canvasKit = shallowRef<CanvasKit | null>(null)
const surface = shallowRef<SkSurface | null>(null)
const canvasError = ref<string | null>(null)
const imageError = ref<string | null>(null)
const imagesReady = ref(false)
const zoom = ref(1)
const pan = ref({ x: 0, y: 0 })
const spacePressed = ref(false)
const images = new Map<string, SkImage>()
const absTransforms = new Map<string, AbsTransform>()

const IDENTITY_MATRIX: Matrix = [1, 0, 0, 1, 0, 0]

let drawQueued = false
let resizeObserver: ResizeObserver | null = null
let interaction:
  | {
      type: 'move' | 'resize' | 'pan'
      nodeId?: string
      startSceneX: number
      startSceneY: number
      startTransform?: Record<string, number>
      startLocalX?: number
      startLocalY?: number
      startParentInverse?: Matrix
      startNodeInverse?: Matrix
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
  if (typeof ResizeObserver !== 'undefined' && viewportRef.value) {
    resizeObserver = new ResizeObserver(resizeCanvas)
    resizeObserver.observe(viewportRef.value)
  }
  await initCanvasKit()
  resizeCanvas()
  fitView()
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', handleKeyDown)
  window.removeEventListener('keyup', handleKeyUp)
  window.removeEventListener('resize', resizeCanvas)
  resizeObserver?.disconnect()
  resizeObserver = null
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
  imagesReady.value = false
  imageError.value = null
  try {
    for (const node of nodes.value) {
      if (!node.asset_id || images.has(node.asset_id)) continue
      const asset = studio.assets.find((item) => item.id === node.asset_id)
      if (!asset) continue
      try {
        const blob = await api.getAssetContent(asset.id)
        const bytes = new Uint8Array(await blob.arrayBuffer())
        const image = ck.MakeImageFromEncoded(bytes)
        if (image) images.set(asset.id, image)
        else imageError.value = 'One or more asset previews could not be decoded.'
      } catch {
        imageError.value = 'One or more asset previews could not be loaded.'
      }
    }
  } finally {
    imagesReady.value = true
    scheduleDraw()
  }
}

function retryImageLoads() {
  imageError.value = null
  void loadImages()
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
  const rootTransform = makeAbsTransform(IDENTITY_MATRIX, IDENTITY_MATRIX, 0, 0)
  const children = childrenOf(currentScene.root_node_id)
  for (const node of children) drawNode(canvas, node, rootTransform)

  const selected = selectedNode.value
  const selectedAbs = selected ? absTransforms.get(selected.id) : null
  if (selected && selectedAbs) {
    drawSelection(canvas, selectedAbs, !selected.locked)
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
  const localMatrix = matrixFromTransform(transform)
  const abs = makeAbsTransform(parentAbs.matrix, localMatrix, width, height)
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

function matrixFromTransform(transform: Record<string, number>): Matrix {
  const rotation = ((transform.rotation ?? 0) * Math.PI) / 180
  const cos = Math.cos(rotation)
  const sin = Math.sin(rotation)
  const scaleX = transform.scale_x ?? 1
  const scaleY = transform.scale_y ?? 1
  return [
    cos * scaleX,
    sin * scaleX,
    -sin * scaleY,
    cos * scaleY,
    transform.x ?? 0,
    transform.y ?? 0,
  ]
}

function multiplyMatrix(left: Matrix, right: Matrix): Matrix {
  return [
    left[0] * right[0] + left[2] * right[1],
    left[1] * right[0] + left[3] * right[1],
    left[0] * right[2] + left[2] * right[3],
    left[1] * right[2] + left[3] * right[3],
    left[0] * right[4] + left[2] * right[5] + left[4],
    left[1] * right[4] + left[3] * right[5] + left[5],
  ]
}

function invertMatrix(matrix: Matrix): Matrix {
  const [a, b, c, d, e, f] = matrix
  const determinant = a * d - b * c
  if (Math.abs(determinant) < 1e-8) return [...IDENTITY_MATRIX]
  const inverse = 1 / determinant
  return [
    d * inverse,
    -b * inverse,
    -c * inverse,
    a * inverse,
    (c * f - d * e) * inverse,
    (b * e - a * f) * inverse,
  ]
}

function applyMatrix(matrix: Matrix, point: Point): Point {
  return {
    x: matrix[0] * point.x + matrix[2] * point.y + matrix[4],
    y: matrix[1] * point.x + matrix[3] * point.y + matrix[5],
  }
}

function applyVector(matrix: Matrix, vector: Point): Point {
  return {
    x: matrix[0] * vector.x + matrix[2] * vector.y,
    y: matrix[1] * vector.x + matrix[3] * vector.y,
  }
}

function makeAbsTransform(parentMatrix: Matrix, localMatrix: Matrix, width: number, height: number): AbsTransform {
  const matrix = multiplyMatrix(parentMatrix, localMatrix)
  return {
    matrix,
    inverse: invertMatrix(matrix),
    parentMatrix,
    corners: [
      applyMatrix(matrix, { x: 0, y: 0 }),
      applyMatrix(matrix, { x: width, y: 0 }),
      applyMatrix(matrix, { x: width, y: height }),
      applyMatrix(matrix, { x: 0, y: height }),
    ],
    width,
    height,
  }
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

function drawSelection(canvas: Canvas, abs: AbsTransform, showHandles: boolean) {
  const ck = canvasKit.value
  if (!ck) return
  const outline = new ck.Paint()
  outline.setColor(ck.Color(14, 157, 145, 255))
  outline.setStyle(ck.PaintStyle.Stroke)
  outline.setStrokeWidth(1.5 / zoom.value)
  for (let index = 0; index < abs.corners.length; index += 1) {
    const start = abs.corners[index]!
    const end = abs.corners[(index + 1) % abs.corners.length]!
    canvas.drawLine(start.x, start.y, end.x, end.y, outline)
  }
  outline.delete()

  if (!showHandles) return

  const fill = new ck.Paint()
  fill.setColor(ck.Color(255, 255, 255, 255))
  const handle = new ck.Paint()
  handle.setColor(ck.Color(14, 157, 145, 255))
  const size = 6 / zoom.value
  for (const corner of abs.corners) {
    canvas.drawRect(ck.XYWHRect(corner.x - size / 2, corner.y - size / 2, size, size), fill)
    canvas.drawRect(ck.XYWHRect(corner.x - size / 2, corner.y - size / 2, size, size), handle)
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
    const local = applyMatrix(abs.inverse, point)
    if (local.x >= 0 && local.x <= abs.width && local.y >= 0 && local.y <= abs.height) {
      return node
    }
  }
  return null
}

function resizeHandleAt(point: { x: number; y: number }, abs: AbsTransform): ResizeHandle | null {
  const tolerance = 8 / zoom.value
  const toleranceSquared = tolerance * tolerance
  const distanceSquared = (a: Point, b: Point) => (a.x - b.x) ** 2 + (a.y - b.y) ** 2
  const distanceToSegmentSquared = (pointA: Point, start: Point, end: Point) => {
    const dx = end.x - start.x
    const dy = end.y - start.y
    if (dx === 0 && dy === 0) return distanceSquared(pointA, start)
    const lengthSquared = dx * dx + dy * dy
    const projection = Math.max(0, Math.min(1, ((pointA.x - start.x) * dx + (pointA.y - start.y) * dy) / lengthSquared))
    return distanceSquared(pointA, { x: start.x + projection * dx, y: start.y + projection * dy })
  }

  const cornerHandles: Array<[ResizeHandle, Point]> = [
    ['nw', abs.corners[0]],
    ['ne', abs.corners[1]],
    ['se', abs.corners[2]],
    ['sw', abs.corners[3]],
  ]
  for (const [handle, corner] of cornerHandles) {
    if (distanceSquared(point, corner) <= toleranceSquared) return handle
  }

  const edgeHandles: Array<[ResizeHandle, Point, Point]> = [
    ['n', abs.corners[0], abs.corners[1]],
    ['e', abs.corners[1], abs.corners[2]],
    ['s', abs.corners[2], abs.corners[3]],
    ['w', abs.corners[3], abs.corners[0]],
  ]
  for (const [handle, start, end] of edgeHandles) {
    if (distanceToSegmentSquared(point, start, end) <= toleranceSquared) return handle
  }
  return null
}

function onPointerDown(event: PointerEvent) {
  const target = event.currentTarget as HTMLElement | null
  target?.setPointerCapture?.(event.pointerId)
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
        startLocalX: applyMatrix(selectedAbs.inverse, point).x,
        startLocalY: applyMatrix(selectedAbs.inverse, point).y,
        startNodeInverse: selectedAbs.inverse,
        handle,
      }
      event.preventDefault()
      return
    }
  }
  const hit = hitTest(point)
  if (hit) {
    studio.selectNode(hit.id)
    if (hit.locked) {
      event.preventDefault()
      return
    }
    studio.startMutation()
    interaction = {
      type: 'move',
      nodeId: hit.id,
      startSceneX: point.x,
      startSceneY: point.y,
      startTransform: { ...hit.transform },
      startParentInverse: invertMatrix(absTransforms.get(hit.id)?.parentMatrix ?? IDENTITY_MATRIX),
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
    const delta = applyVector(active.startParentInverse ?? IDENTITY_MATRIX, {
      x: point.x - active.startSceneX,
      y: point.y - active.startSceneY,
    })
    next.x = (active.startTransform.x ?? 0) + delta.x
    next.y = (active.startTransform.y ?? 0) + delta.y
  } else if (active.handle) {
    const localPoint = applyMatrix(active.startNodeInverse ?? IDENTITY_MATRIX, point)
    applyResize(next, active.handle, localPoint, active.startLocalX ?? 0, active.startLocalY ?? 0)
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

function isTrackpadScroll(event: WheelEvent) {
  // Mouse wheels report integer (or line-mode) deltas; trackpad two-finger
  // scroll reports pixel-mode deltas with a horizontal component and/or a
  // fractional vertical component.
  if (event.deltaMode !== 0) return false
  if (Math.abs(event.deltaX) > 0) return true
  return Math.abs(event.deltaY) % 1 !== 0
}

function zoomAt(clientX: number, clientY: number, factor: number) {
  const rect = canvasRef.value?.getBoundingClientRect()
  if (!rect) return
  const nextZoom = Math.min(8, Math.max(0.1, zoom.value * factor))
  const point = toScene(clientX, clientY)
  pan.value = {
    x: clientX - rect.left - point.x * nextZoom,
    y: clientY - rect.top - point.y * nextZoom,
  }
  zoom.value = nextZoom
}

function onWheel(event: WheelEvent) {
  event.preventDefault()
  if (event.ctrlKey || event.metaKey) {
    // Pinch gesture (or Ctrl/Cmd + wheel) zooms around the cursor.
    zoomAt(event.clientX, event.clientY, event.deltaY < 0 ? 1.12 : 0.9)
    return
  }
  if (isTrackpadScroll(event)) {
    // Two-finger trackpad scroll pans the canvas.
    pan.value = { x: pan.value.x - event.deltaX, y: pan.value.y - event.deltaY }
    scheduleDraw()
    return
  }
  // Mouse wheel keeps zooming around the cursor (preserved behavior).
  zoomAt(event.clientX, event.clientY, event.deltaY < 0 ? 1.12 : 0.9)
}

function zoomBy(factor: number) {
  const rect = viewportRef.value?.getBoundingClientRect()
  if (!rect) return
  zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, factor)
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
  const walk = (parentId: string | null, parentMatrix: Matrix) => {
    for (const node of children.get(parentId) ?? []) {
      const t = node.transform || {}
      const w = t.width ?? 0
      const h = t.height ?? 0
      const abs = makeAbsTransform(parentMatrix, matrixFromTransform(t), w, h)
      if (node.visible !== false) {
        for (const corner of abs.corners) {
          minX = Math.min(minX, corner.x)
          minY = Math.min(minY, corner.y)
          maxX = Math.max(maxX, corner.x)
          maxY = Math.max(maxY, corner.y)
        }
      }
      walk(node.id, abs.matrix)
    }
  }
  walk(rootId, IDENTITY_MATRIX)
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
      :data-images-ready="imagesReady ? 'true' : 'false'"
      @pointerdown="onPointerDown"
      @pointermove="onPointerMove"
      @pointerup="onPointerUp"
      @pointercancel="onPointerUp"
      @wheel="onWheel"
    >
      <div v-if="imageError" class="canvas-inline-error" role="alert">
        <span>{{ imageError }}</span>
        <button class="secondary-button compact" type="button" @click="retryImageLoads">Retry</button>
      </div>
      <canvas ref="canvasRef" data-testid="canvaskit-canvas" />
      <div v-if="canvasError" class="canvas-fallback">
        <Layers3 :size="22" />
        <span>{{ canvasError }}</span>
      </div>
    </div>
  </div>
</template>
