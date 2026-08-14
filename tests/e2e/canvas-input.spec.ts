import path from 'node:path'

import { expect, test } from '@playwright/test'


test('trackpad two-finger scroll pans, ctrl+wheel zooms', async ({ page }) => {
  const projectName = 'Input ' + Date.now()
  await page.goto('/')

  await page.getByRole('button', { name: 'New project' }).first().click()
  await page.getByLabel('New project name').fill(projectName)
  await page.getByRole('button', { name: 'Create' }).click()

  const fixture = path.join(process.cwd(), 'apps/api/tests/fixtures/transparent.png')
  await page.locator('input[type="file"]').setInputFiles(fixture)
  await page.locator('.panel-tabs button').filter({ hasText: 'Assets' }).click()
  await page.locator('.asset-row').first().click()
  await page.getByRole('button', { name: 'Add to canvas' }).click()

  const viewport = page.locator('.canvas-viewport')
  await expect(viewport).toBeVisible()

  const panYBefore = Number(await viewport.getAttribute('data-pan-y'))
  const zoomBefore = Number(await viewport.getAttribute('data-zoom'))

  // Trackpad two-finger vertical scroll (fractional pixel delta) pans.
  await page.evaluate(() => {
    const el = document.querySelector('.canvas-viewport') as HTMLElement
    el.dispatchEvent(new WheelEvent('wheel', {
      deltaX: 0,
      deltaY: 42.5,
      deltaMode: 0,
      bubbles: true,
      cancelable: true,
      clientX: 200,
      clientY: 200,
    }))
  })
  await expect
    .poll(async () => Number(await viewport.getAttribute('data-pan-y')))
    .not.toBe(panYBefore)

  // Pinch / Ctrl+wheel zooms.
  await page.evaluate(() => {
    const el = document.querySelector('.canvas-viewport') as HTMLElement
    el.dispatchEvent(new WheelEvent('wheel', {
      deltaY: -100,
      deltaMode: 0,
      ctrlKey: true,
      bubbles: true,
      cancelable: true,
      clientX: 200,
      clientY: 200,
    }))
  })
  await expect
    .poll(async () => Number(await viewport.getAttribute('data-zoom')))
    .not.toBe(zoomBefore)
})
