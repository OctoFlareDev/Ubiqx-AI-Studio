import CanvasKitInit, { type CanvasKit } from 'canvaskit-wasm'
import wasmUrl from 'canvaskit-wasm/bin/canvaskit.wasm?url'

let pending: Promise<CanvasKit> | null = null

export function getCanvasKit(): Promise<CanvasKit> {
  if (!pending) {
    pending = CanvasKitInit({
      locateFile: () => wasmUrl,
    })
  }
  return pending
}
