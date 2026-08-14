import path from 'node:path'

import { expect, test, type Page } from '@playwright/test'


async function createProject(page: Page, name: string) {
  await page.goto('/')
  await page.getByRole('button', { name: 'New project' }).first().click()
  await page.getByLabel('New project name').fill(name)
  await page.getByRole('button', { name: 'Create' }).click()
  await expect(page.getByRole('heading', { name })).toBeVisible({ timeout: 15000 })
}


test('empty projects provide import and asset recovery actions', async ({ page }) => {
  await createProject(page, `Empty ${Date.now()}`)

  await expect(page.getByRole('button', { name: 'Import design' })).toBeVisible()
  await page.getByRole('button', { name: 'Open assets' }).click()
  await expect(page.getByText('Project assets')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Import asset' })).toBeVisible()
})


test('asset placement clears asset selection and creates a keyboard-selectable layer', async ({ page }) => {
  await createProject(page, `Asset workflow ${Date.now()}`)

  const fixture = path.join(process.cwd(), 'apps/api/tests/fixtures/transparent.png')
  await page.locator('input[type="file"]').setInputFiles(fixture)
  await page.locator('.panel-tabs button').filter({ hasText: 'Assets' }).click()
  await page.locator('.asset-row').first().click()

  await expect(page.locator('.asset-properties h3')).toHaveText('transparent.png')
  await page.getByRole('button', { name: 'Add to canvas' }).click()
  await page.locator('.panel-tabs button').filter({ hasText: 'Layers' }).click()

  const layer = page.getByRole('button', { name: 'Select layer transparent' })
  await expect(layer).toBeVisible()
  await layer.focus()
  await page.keyboard.press('Enter')
  await expect(page.getByText('Layer', { exact: true })).toBeVisible()
})


test('mobile users can reach the layer and asset panels', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await createProject(page, `Mobile workflow ${Date.now()}`)

  await expect(page.getByRole('button', { name: 'Import', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Open assets' }).first().click()
  await expect(page.locator('.left-panel.mobile-open')).toBeVisible()
  await expect(page.getByText('Project assets')).toBeVisible()

  await page.getByRole('button', { name: 'Close layer and asset panel' }).click()
  await page.getByRole('button', { name: 'Open layers' }).click()
  await expect(page.locator('.left-panel.mobile-open')).toBeVisible()
  await expect(page.getByText('No layers')).toBeVisible()
})
