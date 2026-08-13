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

  await expect(page.locator('#node-x')).toHaveValue('24', { timeout: 10000 })

  const box = await page.locator('canvas[data-testid="canvaskit-canvas"]').boundingBox()
  expect(box).not.toBeNull()
  if (!box) return

  const startX = box.x + (box.width - 160) / 2 + 24 + 36
  const startY = box.y + (box.height - 100) / 2 + 36 + 13
  await page.mouse.move(startX, startY)
  await page.mouse.down()
  await page.mouse.move(startX + 12, startY + 6, { steps: 4 })
  await page.mouse.up()

  await expect(page.locator('#node-x')).toHaveValue('36', { timeout: 10000 })
  await expect(page.locator('#node-y')).toHaveValue('24', { timeout: 10000 })
})
