import path from 'node:path'

import { expect, test } from '@playwright/test'


test('imports a PSD and moves a selected layer on the CanvasKit canvas', async ({ page }) => {
  const projectName = `Canvas ${Date.now()}`
  await page.goto('/')

  await page.getByRole('button', { name: 'New project' }).first().click()
  await page.getByLabel('New project name').fill(projectName)
  await page.getByRole('button', { name: 'Create' }).click()

  const fixture = path.join(process.cwd(), 'apps/api/tests/fixtures/basic.psd')
  await page.locator('input[type="file"]').setInputFiles(fixture)
  await page.locator('.panel-tabs button').filter({ hasText: 'Assets' }).click()
  await page.locator('.asset-row').first().click()
  await page.getByRole('button', { name: 'Import as scene' }).click()

  await expect(page.locator('canvas[data-testid="canvaskit-canvas"]')).toBeVisible({ timeout: 15000 })
  await page.locator('.panel-tabs button').filter({ hasText: 'Layers' }).click()
  await page.locator('.layer-row').filter({ hasText: 'Button' }).click()

  const nodeX = Number(await page.locator('#node-x').inputValue())
  const nodeY = Number(await page.locator('#node-y').inputValue())

  const box = await page.locator('canvas[data-testid="canvaskit-canvas"]').boundingBox()
  expect(box).not.toBeNull()
  if (!box) return

  const viewport = page.locator('.canvas-viewport')
  await expect.poll(async () => Number(await viewport.getAttribute('data-pan-x')), { timeout: 10000 }).not.toBe(0)
  await expect.poll(async () => Number(await viewport.getAttribute('data-pan-y')), { timeout: 10000 }).not.toBe(0)
  const panX = Number(await viewport.getAttribute('data-pan-x'))
  const panY = Number(await viewport.getAttribute('data-pan-y'))
  const zoom = Number(await viewport.getAttribute('data-zoom'))
  // The fixture's nested Button overlaps the fitted scene center. Using the
  // rendered center keeps this assertion independent of the layer's parent
  // transform while still exercising CanvasKit hit testing and movement.
  const startX = box.x + panX + (box.width / 2 - panX) / zoom
  const startY = box.y + panY + (box.height / 2 - panY) / zoom
  await page.mouse.move(startX, startY)
  await page.mouse.down()
  await page.mouse.move(startX + 12, startY + 6, { steps: 4 })
  await page.mouse.up()

  await expect(page.locator('#node-x')).toHaveValue(String(nodeX + 12), { timeout: 10000 })
  await expect(page.locator('#node-y')).toHaveValue(String(nodeY + 6), { timeout: 10000 })
})
