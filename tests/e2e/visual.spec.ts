import path from 'node:path'

import { expect, test } from '@playwright/test'

// Full-page captures remain available for visual review. The CanvasKit surface
// also has committed pixel baselines because its fixture-driven rendering is
// deterministic across the supported browser projects.
test('captures imported and selected canvas states', async ({ page }) => {
  const projectName = 'Visual ' + Date.now()
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
  await expect(page.locator('.canvas-viewport')).toHaveAttribute('data-images-ready', 'true', { timeout: 15000 })

  const imported = await page.screenshot({ path: 'test-results/visual/imported.png', animations: 'disabled' })
  expect(imported.length).toBeGreaterThan(5000)
  await expect(page.locator('canvas[data-testid="canvaskit-canvas"]')).toHaveScreenshot('imported-canvas.png', {
    animations: 'disabled',
    maxDiffPixelRatio: 0.03,
  })

  await page.locator('.panel-tabs button').filter({ hasText: 'Layers' }).click()
  await page.locator('.layer-row').filter({ hasText: 'Button' }).click()
  const selected = await page.screenshot({ path: 'test-results/visual/selected.png', animations: 'disabled' })
  expect(selected.length).toBeGreaterThan(5000)
  await expect(page.locator('canvas[data-testid="canvaskit-canvas"]')).toHaveScreenshot('selected-canvas.png', {
    animations: 'disabled',
    maxDiffPixelRatio: 0.03,
  })
})
